"""Testes da janela de pesquisa (Ctrl+F)."""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface grafica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

import banco_de_dados as db  # noqa: E402
import pesquisa  # noqa: E402
import pesquisas_incluidas  # noqa: E402
from core import permissoes  # noqa: E402
from pesquisa import Resultado  # noqa: E402


@pytest.fixture
def raiz():
    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture
def com_dados():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    db.adicionar_tarefa("Preparar orcamento anual", "2030-01-01", criada_por="ana")
    pesquisas_incluidas.registar_incluidas()
    yield
    pesquisa.limpar()


@pytest.fixture
def janela(com_dados, raiz):
    from pesquisa_ui import JanelaPesquisa

    tela = JanelaPesquisa(raiz)
    yield tela
    tela.destroy()


def escrever(janela, termo: str) -> None:
    janela.entrada.delete(0, tk.END)
    janela.entrada.insert(0, termo)


def test_comeca_com_uma_instrucao_e_nao_vazia(janela):
    """Um ecra vazio sem explicacao nao diz o que fazer."""
    assert janela.mensagem.cget("text")
    assert janela.arvore.get_children() == ()


def test_encontra_e_agrupa(janela):
    escrever(janela, "orcamento")
    resultados = janela.procurar()

    assert [r.titulo for r in resultados] == ["Preparar orcamento anual"]
    grupos = janela.arvore.get_children()
    assert len(grupos) == 1
    assert "1" in janela.arvore.item(grupos[0], "text"), "o grupo mostra quantos"


def test_um_termo_curto_nao_procura(janela):
    escrever(janela, "o")
    assert janela.procurar() == []
    assert janela.arvore.get_children() == ()


def test_sem_resultados_diz_o_que_procurou(janela):
    escrever(janela, "inexistente")
    assert janela.procurar() == []
    assert "inexistente" in janela.mensagem.cget("text")


def test_procurar_de_novo_limpa_o_anterior(janela):
    escrever(janela, "orcamento")
    janela.procurar()
    assert janela.arvore.get_children()

    escrever(janela, "inexistente")
    janela.procurar()
    assert janela.arvore.get_children() == ()


def test_escrever_nao_procura_a_cada_tecla(janela):
    """Procurar a cada letra faz o trabalho cinco vezes para deitar fora quatro.

    Verificado pelo mecanismo e nao pelo relogio: tres teclas seguidas deixam
    **uma** pesquisa agendada, nao tres, e procurar consome-a.
    """
    chamadas = []
    pesquisa.registar("conta", lambda t, l: chamadas.append(t) or [])
    escrever(janela, "orc")

    agendados = []
    for _ in range(3):
        janela._ao_escrever()
        agendados.append(janela._agendado)

    assert chamadas == [], "ainda nao devia ter procurado"
    assert len(set(agendados)) == 3, "cada tecla substitui o agendamento anterior"
    assert janela._agendado is not None

    janela.procurar()
    assert chamadas == ["orc"], "procurou uma vez so"
    assert janela._agendado is None, "o agendamento foi consumido"


def test_as_fontes_vazias_nao_criam_grupos(janela):
    """Um grupo vazio e ruido: diz que ha um sitio onde nao ha nada."""
    pesquisa.registar("vazia", lambda t, l: [])
    escrever(janela, "orcamento")
    janela.procurar()

    textos = [janela.arvore.item(g, "text") for g in janela.arvore.get_children()]
    assert not any("vazia" in t.lower() for t in textos)


def test_a_janela_respeita_as_permissoes(com_dados, raiz):
    from pesquisa_ui import JanelaPesquisa

    db.adicionar_tarefa("Orcamento do Bruno", "2030-01-02", criada_por="bruno")
    permissoes.definir_sessao("ana", "colaborador", persistir=False)

    tela = JanelaPesquisa(raiz)
    try:
        escrever(tela, "orcamento")
        titulos = [r.titulo for r in tela.procurar()]
        assert "Orcamento do Bruno" not in titulos
    finally:
        tela.destroy()
