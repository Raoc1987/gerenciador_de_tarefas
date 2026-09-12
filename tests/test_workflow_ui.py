"""Testes da tela *Configurações → Automações*.

O que interessa aqui é que ninguém consiga escrever uma regra que nunca
dispara: os eventos e as ações vêm do sistema, não de uma caixa de texto. Uma
regra ligada a um evento que não existe é o pior tipo de avaria, porque parece
que está tudo bem.
"""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

import database as db  # noqa: E402
from core import eventos, permissoes  # noqa: E402
from workflow import acoes, repositorio  # noqa: E402
from workflow.modelo import Acao, Condicao, Operador  # noqa: E402


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
def com_acoes():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    acoes.registar("registar", lambda d, a: None)
    acoes.registar("tarefa.criar", lambda d, a: None)
    yield
    acoes.limpar()


@pytest.fixture
def janela(com_acoes, raiz):
    from workflow_ui import JanelaAutomacoes

    tela = JanelaAutomacoes(raiz)
    yield tela
    tela.destroy()


# ==================================================================== LISTA


def test_sem_regras_explica_o_que_fazer(janela):
    """Um ecrã vazio sem exemplo é um beco."""
    assert janela.regras() == []
    assert janela.vazio.winfo_manager()


def test_as_regras_aparecem_com_o_que_fazem(com_acoes, raiz):
    from workflow_ui import JanelaAutomacoes

    repositorio.criar(
        "Repor material",
        "estoque.em_falta",
        condicoes=[Condicao("saldo", Operador.MENOR, 5)],
        acoes=[Acao("tarefa.criar", {"descricao": "Encomendar {id}"})],
    )
    tela = JanelaAutomacoes(raiz)
    try:
        valores = tela.tabela.item(tela.tabela.get_children()[0], "values")
        assert valores[0] == "Repor material"
        assert valores[1] == "estoque.em_falta"
        assert "saldo" in valores[2]
        assert "tarefa.criar" in valores[3]
    finally:
        tela.destroy()


def test_uma_regra_sem_condicoes_diz_sempre(com_acoes, raiz):
    from workflow_ui import JanelaAutomacoes

    repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    tela = JanelaAutomacoes(raiz)
    try:
        valores = tela.tabela.item(tela.tabela.get_children()[0], "values")
        assert valores[2] == "sempre"
    finally:
        tela.destroy()


# ================================================================== ESCOLHAS


def test_os_eventos_vem_do_sistema(janela):
    """Escrever o nome à mão daria regras que nunca disparam."""
    import workflow_ui

    disponiveis = workflow_ui.eventos_disponiveis()
    assert "tarefa.criada" in disponiveis
    assert "tarefa.*" in disponiveis


def test_os_eventos_do_motor_nao_sao_oferecidos(janela):
    """Uma regra sobre os eventos do motor seria um ciclo à espera de acontecer."""
    import workflow_ui

    assert not [e for e in workflow_ui.eventos_disponiveis() if e.startswith("workflow.")]


def test_so_as_acoes_registadas_sao_oferecidas(com_acoes, janela):
    from workflow_ui import DialogoRegra

    dialogo = DialogoRegra(janela)
    try:
        assert set(dialogo.seletor_acao["values"]) == {"registar", "tarefa.criar"}
    finally:
        dialogo.destroy()


def test_sem_acoes_registadas_avisa_em_vez_de_abrir(janela):
    """Um formulário que não dá para submeter é pior do que uma mensagem."""
    acoes.limpar()
    assert janela.nova_regra() is None
    assert janela.mensagem.cget("text")


# =================================================================== CRIAR


def test_criar_uma_regra_pela_janela(com_acoes, janela):
    from workflow_ui import DialogoRegra

    dialogo = DialogoRegra(janela)
    dialogo.entrada_nome.insert(0, "Repor material")
    dialogo.evento_var.set("estoque.em_falta")
    dialogo.entrada_campo.insert(0, "saldo")
    dialogo.operador_var.set(Operador.MENOR.value)
    dialogo.entrada_valor.insert(0, "5")
    dialogo.acao_var.set("tarefa.criar")
    dialogo.entrada_texto.insert(0, "Encomendar item {id}")

    regra = dialogo.guardar()
    assert regra is not None
    assert regra.evento == "estoque.em_falta"
    assert regra.condicoes[0].campo == "saldo"
    assert regra.acoes[0].argumentos["descricao"] == "Encomendar item {id}"


def test_uma_regra_sem_nome_fica_na_janela_e_nao_rebenta(com_acoes, janela):
    from workflow_ui import DialogoRegra

    dialogo = DialogoRegra(janela)
    try:
        dialogo.evento_var.set("tarefa.criada")
        dialogo.acao_var.set("registar")
        assert dialogo.guardar() is None
        assert dialogo.mensagem.cget("text")
        assert repositorio.listar() == []
    finally:
        dialogo.destroy()


def test_sem_condicao_a_regra_aplica_se_sempre(com_acoes, janela):
    from workflow_ui import DialogoRegra

    dialogo = DialogoRegra(janela)
    dialogo.entrada_nome.insert(0, "Sempre")
    dialogo.evento_var.set("tarefa.criada")
    dialogo.acao_var.set("registar")

    regra = dialogo.guardar()
    assert regra.condicoes == ()


# ================================================================== GERIR


def test_ligar_e_desligar_uma_regra(com_acoes, janela):
    regra = repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    janela.recarregar()
    janela.tabela.selection_set(str(regra.id))

    janela.alternar()
    assert repositorio.obter(regra.id).ativa is False

    janela.tabela.selection_set(str(regra.id))
    janela.alternar()
    assert repositorio.obter(regra.id).ativa is True


def test_remover_pede_confirmacao(com_acoes, janela, monkeypatch):
    import workflow_ui

    regra = repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    janela.recarregar()
    monkeypatch.setattr(workflow_ui.messagebox, "askyesno", lambda *a, **k: False)
    janela.tabela.selection_set(str(regra.id))
    janela.remover()

    assert repositorio.obter(regra.id) is not None


def test_remover_a_serio(com_acoes, janela, monkeypatch):
    import workflow_ui

    regra = repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    janela.recarregar()
    monkeypatch.setattr(workflow_ui.messagebox, "askyesno", lambda *a, **k: True)
    janela.tabela.selection_set(str(regra.id))
    janela.remover()

    assert repositorio.obter(regra.id) is None


# ============================================================== PERMISSÕES


def test_quem_nao_administra_nao_mexe(com_acoes, raiz):
    from workflow_ui import JanelaAutomacoes

    repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    tela = JanelaAutomacoes(raiz)
    try:
        assert tela.regras() == []
        assert "disabled" in tela.botao_nova.state()
        for botao in tela._botoes.values():
            assert "disabled" in botao.state()
    finally:
        tela.destroy()
