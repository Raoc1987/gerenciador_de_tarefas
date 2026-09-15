"""Testes do assistente de importacao.

O passo que interessa e o quarto: ver o que vai acontecer antes de acontecer.
Uma importacao escreve centenas de linhas de uma vez, e sem pre-visualizacao o
unico remedio para um mapeamento errado e apagar tudo a mao.
"""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface grafica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

import banco_de_dados as db  # noqa: E402
import importacoes_incluidas  # noqa: E402
from core import permissoes  # noqa: E402
from importacao import motor  # noqa: E402


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
def com_destinos():
    motor.limpar()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    importacoes_incluidas.registar_incluidos()
    yield
    motor.limpar()


@pytest.fixture
def janela(com_destinos, raiz):
    from importacao_ui import JanelaImportacao

    tela = JanelaImportacao(raiz)
    yield tela
    tela.destroy()


@pytest.fixture
def ficheiro(tmp_path):
    caminho = tmp_path / "tarefas.csv"
    caminho.write_bytes(
        "Descricao;Vencimento\n"
        "Rever contrato;31/01/2030\n"
        "Sem prazo;\n"
        ";2030-02-01\n".encode("utf-8")
    )
    return caminho


# ================================================================ FICHEIRO


def test_ler_um_ficheiro_mostra_o_que_tem(janela, ficheiro):
    assert janela.escolher(str(ficheiro)) is True
    assert "3" in janela.rotulo_ficheiro.cget("text"), "tres linhas de dados"


def test_um_ficheiro_ilegivel_vira_mensagem(janela, tmp_path):
    mau = tmp_path / "vazio.csv"
    mau.write_text("", encoding="utf-8")

    assert janela.escolher(str(mau)) is False
    assert janela.mensagem.cget("text")


def test_cancelar_a_escolha_nao_faz_nada(janela, monkeypatch):
    """Sem caminho, o assistente pergunta -- e desistir nao pode fazer nada."""
    import importacao_ui

    monkeypatch.setattr(importacao_ui.filedialog, "askopenfilename", lambda **k: "")
    assert janela.escolher() is False
    assert janela.tabela is None


# ================================================================ COLUNAS


def test_as_colunas_sao_sugeridas(janela, ficheiro):
    janela.escolher(str(ficheiro))
    assert janela.mapa() == {"descricao": "Descricao", "vencimento": "Vencimento"}


def test_o_mapeamento_pode_ser_corrigido(janela, ficheiro):
    janela.escolher(str(ficheiro))
    janela._seletores["vencimento"].set("")
    assert janela.mapa() == {"descricao": "Descricao"}


# =============================================================== PREVISAO


def test_a_previsao_nao_escreve_nada(janela, ficheiro):
    """O teste que define o assistente."""
    janela.escolher(str(ficheiro))
    previsao = janela.prever()

    assert len(previsao.aceites) == 2
    assert len(previsao.problemas) == 1
    assert db.buscar_tarefas() == [], "pre-visualizar nao pode criar"


def test_a_previsao_mostra_os_problemas_primeiro(janela, ficheiro):
    """E o que precisa de decisao; o resto e confirmacao."""
    janela.escolher(str(ficheiro))
    janela.prever()

    linhas = janela.tabela_previsao.get_children()
    primeira = janela.tabela_previsao.item(linhas[0], "values")
    assert primeira[-1], "a primeira linha mostrada tem um problema descrito"


def test_sem_previsao_nao_se_pode_importar(janela, ficheiro):
    """O botao so acorda depois de alguem ter visto o que vai entrar."""
    janela.escolher(str(ficheiro))
    assert "disabled" in janela.botao_importar.state()

    janela.prever()
    assert "disabled" not in janela.botao_importar.state()


def test_se_nada_entra_o_botao_fica_travado(janela, tmp_path):
    caminho = tmp_path / "so_erros.csv"
    caminho.write_text("Descricao;Vencimento\n;2030-01-01\n", encoding="utf-8")

    janela.escolher(str(caminho))
    janela.prever()
    assert "disabled" in janela.botao_importar.state()


# =============================================================== IMPORTAR


def test_importar_escreve_o_que_foi_previsto(janela, ficheiro):
    janela.escolher(str(ficheiro))
    janela.prever()
    resultado = janela.importar()

    assert resultado.criados == 2
    guardadas = {t[1]: t[2] for t in db.buscar_tarefas()}
    assert guardadas["Rever contrato"] == "2030-01-31", "data convertida"


def test_o_botao_trava_depois_de_importar(janela, ficheiro):
    """Importar duas vezes por engano e facil com o botao ainda ativo."""
    janela.escolher(str(ficheiro))
    janela.prever()
    janela.importar()

    assert "disabled" in janela.botao_importar.state()
    assert len(db.buscar_tarefas()) == 2


def test_o_resumo_diz_quantas_ficaram_de_fora(janela, ficheiro):
    janela.escolher(str(ficheiro))
    janela.prever()
    janela.importar()
    assert "1" in janela.mensagem.cget("text")


# ============================================================ PERMISSOES


def test_sem_destinos_o_assistente_diz_e_nao_finge(com_destinos, raiz):
    from importacao_ui import JanelaImportacao

    permissoes.definir_sessao("olga", "visualizador", persistir=False)
    tela = JanelaImportacao(raiz)
    try:
        assert tela.destino() is None
        assert "disabled" in tela.botao_escolher.state()
        assert tela.mensagem.cget("text")
    finally:
        tela.destroy()
