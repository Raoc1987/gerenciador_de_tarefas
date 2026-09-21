"""O sino na barra de topo e o centro onde as notificações se leem.

A caixa já está testada em ``test_notificacoes.py``. O que falta provar aqui é
a parte que só se vê no ecrã: que a frase é montada no idioma de agora, que o
sino diz um número que se pode explicar, e que o centro não é uma forma de ler
a caixa de outra pessoa.
"""

import tkinter as tk

import pytest

import notificacoes
from conftest import TKINTER_DISPONIVEL
from core import permissoes

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="sem interface gráfica disponível"
)


def como(utilizador: str, papel: str = "administrador") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


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


@pytest.fixture
def concha(raiz):
    import aparencia
    from navegacao import Concha, registo

    registo.limpar()
    aparencia.aplicar(raiz, "claro")
    janela = Concha(raiz)
    janela.pack(fill=tk.BOTH, expand=True)
    yield janela
    registo.limpar()


# ===================================================================== o sino


def test_sem_nada_por_ler_o_sino_nao_mostra_numero(concha):
    """Um "0" permanente é um contador que se aprende a ignorar.

    E no dia em que passar a 1, ninguém dá por ele.
    """
    from navegacao.concha import SINO

    concha.definir_por_ler(0)
    assert concha._botao_sino.cget("text") == SINO


def test_o_sino_mostra_quantas_estao_por_ler(concha):
    concha.definir_por_ler(3)
    assert "3" in concha._botao_sino.cget("text")
    assert concha.por_ler() == 3


def test_acima_de_noventa_e_nove_o_numero_deixa_de_crescer(concha):
    """Deixaria de informar e passaria a desalinhar a barra de topo."""
    concha.definir_por_ler(1200)
    assert "99+" in concha._botao_sino.cget("text")


def test_mudar_de_idioma_nao_apaga_o_numero_do_sino(concha):
    """A barra é redesenhada ao traduzir; o sino não se pode perder nisso."""
    concha.definir_por_ler(4)
    concha.atualizar_traducoes()
    assert "4" in concha._botao_sino.cget("text")


def test_o_sino_chama_quem_lhe_ligarem(concha):
    aberturas = []
    concha.ligar_notificacoes(lambda: aberturas.append(True))
    concha._botao_sino.invoke()
    assert aberturas == [True]


def test_um_sino_sem_ligacao_nao_rebenta(concha):
    """A barra de topo é a aplicação inteira; nada nela pode levantar."""
    concha._botao_sino.invoke()


# ================================================================== a frase


def test_a_frase_e_montada_agora_e_no_idioma_de_agora():
    import language_manager
    from notificacoes_ui import texto_da_notificacao

    como("ana")
    notificacoes.criar("insight_atrasadas", quantidade=15, percentagem=40)
    guardada = notificacoes.listar()[0]

    language_manager.definir_idioma("pt", persistir=False)
    em_portugues = texto_da_notificacao(guardada)
    language_manager.definir_idioma("en", persistir=False)
    em_ingles = texto_da_notificacao(guardada)
    language_manager.definir_idioma("pt", persistir=False)

    assert "15" in em_portugues and "15" in em_ingles
    assert em_portugues != em_ingles, "a frase ficou congelada num idioma"


def test_o_texto_livre_de_uma_regra_chega_intacto():
    """Não tem tradução para onde ir buscar: é a frase de quem a escreveu."""
    from notificacoes_ui import texto_da_notificacao

    como("ana")
    notificacoes.criar("Encomenda 42 em atraso", origem="regras")
    assert texto_da_notificacao(notificacoes.listar()[0]) == "Encomenda 42 em atraso"


def test_uma_chave_de_modulo_e_procurada_nos_textos_do_modulo():
    """É o que permite a um módulo anunciar nas suas próprias palavras."""
    import language_manager
    from notificacoes_ui import texto_da_notificacao

    language_manager.registrar_textos_plugin(
        "estoque", {"pt": {"estoque_stock_baixo": "Stock baixo: {quantidade}"}}
    )
    como("ana")
    notificacoes.criar("estoque_stock_baixo", origem="estoque", quantidade=3)

    assert texto_da_notificacao(notificacoes.listar()[0]) == "Stock baixo: 3"


# ================================================================== o centro


def test_o_centro_mostra_o_que_esta_na_caixa(raiz):
    import aparencia
    from notificacoes_ui import CentroDeNotificacoes

    aparencia.aplicar(raiz, "claro")
    como("ana")
    notificacoes.criar("insight_atrasadas", nivel="critico", quantidade=15)

    centro = CentroDeNotificacoes(raiz)
    try:
        assert len(centro._itens) == 1
        assert centro._itens[0].chave == "insight_atrasadas"
    finally:
        centro.destroy()


def test_o_centro_so_mostra_a_caixa_de_quem_esta_em_sessao(raiz):
    import aparencia
    from notificacoes_ui import CentroDeNotificacoes

    aparencia.aplicar(raiz, "claro")
    como("ana")
    notificacoes.criar("so_da_ana")

    como("bruno")
    centro = CentroDeNotificacoes(raiz)
    try:
        assert centro._itens == []
    finally:
        centro.destroy()


def test_marcar_todas_como_lidas_avisa_o_sino(raiz):
    """Senão o número ficava a dizer o contrário do que está no ecrã."""
    import aparencia
    from notificacoes_ui import CentroDeNotificacoes

    aparencia.aplicar(raiz, "claro")
    como("ana")
    notificacoes.criar("uma")
    notificacoes.criar("outra")

    avisos = []
    centro = CentroDeNotificacoes(raiz, ao_mudar=lambda: avisos.append(notificacoes.por_ler()))
    try:
        centro._marcar_todas()
        assert avisos == [0]
        assert all(n.lida for n in centro._itens)
    finally:
        centro.destroy()


def test_o_centro_vazio_nao_oferece_o_que_nao_da_para_fazer(raiz):
    """Oferecer para depois não acontecer nada é pior do que não oferecer."""
    import aparencia
    from notificacoes_ui import CentroDeNotificacoes

    aparencia.aplicar(raiz, "claro")
    como("ana")
    centro = CentroDeNotificacoes(raiz)
    try:
        assert "disabled" in centro._botao_todas.state()
        assert "disabled" in centro._botao_limpar.state()
    finally:
        centro.destroy()


def test_uma_caixa_ilegivel_nao_impede_o_centro_de_abrir(raiz, monkeypatch):
    import aparencia
    from notificacoes_ui import CentroDeNotificacoes

    aparencia.aplicar(raiz, "claro")
    como("ana")

    def rebenta(*args, **kwargs):
        raise RuntimeError("banco em baixo")

    monkeypatch.setattr(notificacoes, "listar", rebenta)
    centro = CentroDeNotificacoes(raiz)
    try:
        assert centro._itens == []
    finally:
        centro.destroy()


# ====================================================== a cor não pode ser tudo


def test_nenhuma_gravidade_se_distingue_de_outra_so_pela_cor():
    """Crítico e atenção partilhavam o "!" e separavam-se por vermelho contra
    âmbar — que é a mesma marca para quem não distingue as duas cores.

    O contraste do texto já era medido contra a WCAG. Isto é a outra metade
    da mesma regra, e é a que um teste apanha e um olho treinado não.
    """
    from dashboard_ui import MARCAS_POR_NIVEL

    marcas = list(MARCAS_POR_NIVEL.values())
    assert len(set(marcas)) == len(marcas), f"duas gravidades com a mesma marca: {marcas}"


def test_a_caixa_usa_as_marcas_do_painel_e_nao_uma_copia():
    """Uma cópia diverge no dia em que alguém mudar só uma das duas."""
    from analitica.insights import Nivel
    from dashboard_ui import MARCAS_POR_NIVEL, TOKEN_POR_NIVEL
    from notificacoes_ui import marca_e_cor

    for grau in Nivel:
        assert marca_e_cor(grau.value) == (
            MARCAS_POR_NIVEL[grau], TOKEN_POR_NIVEL[grau]
        )


def test_uma_gravidade_que_ja_nao_exista_mostra_se_na_mesma():
    """O valor está num banco e tem de sobreviver a um ``Nivel`` que mude."""
    from dashboard_ui import MARCAS_POR_NIVEL
    from analitica.insights import Nivel
    from notificacoes_ui import marca_e_cor

    assert marca_e_cor("uma_gravidade_de_2030")[0] == MARCAS_POR_NIVEL[Nivel.INFORMACAO]
