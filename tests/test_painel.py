"""Testes do motor do painel: registo, grelha e contexto.

O painel deixou de ser uma lista fixa de blocos e passou a desenhar o que
estiver registado. O que estes testes protegem é o que isso torna possível —
um módulo pôr um gráfico ao lado dos da aplicação — e o que isso torna
perigoso: um widget de um plugin que rebente não pode apagar o painel.
"""

import tkinter as tk
from tkinter import ttk

import pytest

from core import permissoes
from core.permissoes import Permissao
from painel import Contexto, Grelha, colunas_para, registar
from painel import limpar as limpar_widgets
from painel import registo


@pytest.fixture
def raiz():
    from conftest import criar_janela_com_retentativa

    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def registo_limpo():
    limpar_widgets()
    yield
    limpar_widgets()


@pytest.fixture
def grelha(raiz):
    import aparencia

    aparencia.aplicar(raiz, "claro")
    g = Grelha(raiz)
    g.pack(fill=tk.BOTH, expand=True)
    return g


class Espia(ttk.Frame):
    """Um widget que se lembra dos contextos que recebeu."""

    def __init__(self, pai):
        super().__init__(pai)
        self.recebidos = []

    def atualizar(self, contexto):
        self.recebidos.append(contexto)


class Mudo(ttk.Frame):
    """Um widget sem ``atualizar`` — desenha-se uma vez e fica quieto."""


# ===================================================================== registo


def test_um_widget_pede_as_colunas_que_quer():
    registar("a", "A", Espia, largura=2)
    assert registo.obter("a").largura == 2


def test_pedir_mais_colunas_do_que_existem_e_um_erro():
    with pytest.raises(ValueError):
        registar("a", "A", Espia, largura=9)


def test_um_widget_precisa_de_algo_que_o_construa():
    with pytest.raises(ValueError):
        registar("a", "A", construir=None)


def test_um_modulo_fica_no_seu_espaco_de_nomes():
    with pytest.raises(ValueError):
        registar("tarefas.meu", "X", Espia, dono="estoque")


def test_sem_permissao_o_widget_nem_e_construido(grelha):
    """Não é escondido: não existe.

    Um cartão vazio ainda diz que existe um número que a pessoa não pode ver.
    Não o construir não diz nada, que é o que se pretende.
    """
    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    registar("livre", "Livre", Espia)
    registar("fechado", "Fechado", Espia, permissao=Permissao.SISTEMA_ADMIN.value)
    grelha.montar()

    assert grelha.widget("livre") is not None
    assert grelha.widget("fechado") is None


def test_os_widgets_de_um_plugin_saem_com_ele():
    registar("estoque.grafico", "Estoque", Espia, dono="estoque")
    assert registo.esquecer_por_dono("estoque") == 1
    assert registo.disponiveis() == []


# ====================================================================== grelha


def test_a_ordem_e_a_declarada(grelha):
    registar("z", "Z", Espia, ordem=10)
    registar("a", "A", Espia, ordem=90)
    grelha.montar()
    assert [w.id for w in grelha._ordem] == ["z", "a"]


def test_o_contexto_chega_a_quem_o_saiba_receber(grelha):
    registar("espia", "E", Espia)
    registar("mudo", "M", Mudo)
    grelha.montar()

    grelha.atualizar_widgets(Contexto(dias=7))
    assert grelha.widget("espia").recebidos[-1].dias == 7
    # O mudo não rebentou por não ter ``atualizar``.
    assert grelha.widget("mudo") is not None


def test_um_widget_que_rebenta_a_construir_nao_leva_o_painel(grelha):
    """Vai haver widgets de plugins aqui dentro."""

    def explode(pai):
        raise RuntimeError("erro de quem escreveu o widget")

    registar("mau", "Mau", explode, ordem=10)
    registar("bom", "Bom", Espia, ordem=20)
    grelha.montar()

    assert grelha.widget("mau") is None
    assert grelha.widget("bom") is not None


def test_um_widget_que_rebenta_a_atualizar_nao_apaga_os_outros(grelha):
    class Partido(ttk.Frame):
        def atualizar(self, contexto):
            raise RuntimeError("erro ao desenhar")

    registar("partido", "P", Partido, ordem=10)
    registar("bom", "Bom", Espia, ordem=20)
    grelha.montar()
    grelha.atualizar_widgets(Contexto(dias=30))

    assert grelha.widget("bom").recebidos, "o widget seguinte não foi atualizado"


def test_a_grelha_reparte_se_com_a_largura():
    """A largura em causa é a **da grelha**, com a barra lateral já descontada.

    Escrevi este teste a pensar na largura da janela e ele reprovou uma
    grelha que estava certa. Num portátil a 1366×768 com escala a 125%
    sobram cerca de 1090px de janela — mas a grelha vê ~866, porque a barra
    lateral leva 224.
    """
    assert colunas_para(1400) == 4, "ecrã largo: quatro"
    assert colunas_para(866) == 2, "o portátil típico: duas"
    assert colunas_para(500) == 1, "janela estreita: uma"


def test_quem_pede_a_linha_inteira_continua_a_ter(grelha):
    """Um pedido de 4 colunas num arranjo de 2 vale 2 — a linha toda."""
    registar("largo", "L", Espia, largura=4)
    grelha.montar()
    grelha._colunas = 2
    grelha._arrumar()
    assert grelha.widget("largo").grid_info()["columnspan"] == 2


# ==================================================================== contexto


def test_sem_panorama_o_contexto_diz_que_nao_ha_dados():
    assert Contexto().tem_dados is False
    assert Contexto(panorama=object()).tem_dados is True


def test_acrescentar_um_filtro_nao_parte_quem_o_ignora():
    """É por isto que o contexto é um objeto e não uma lista de argumentos."""
    base = Contexto(dias=30)
    com_unidade = base.com(unidade=3)
    assert com_unidade.dias == 30 and com_unidade.unidade == 3
    assert base.unidade is None, "a cópia não pode mexer no original"
