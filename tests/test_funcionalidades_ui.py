"""Testes da tela *Configurações → Funcionalidades* e do efeito no arranque.

Um interruptor que não corresponde ao estado real é pior do que nenhum: quem
o vê ligado assume que está ligado. Metade destes testes é sobre isso.
"""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

from core import funcionalidades, permissoes  # noqa: E402


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
def janela(raiz):
    from funcionalidades_ui import JanelaFuncionalidades

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    tela = JanelaFuncionalidades(raiz)
    yield tela
    tela.destroy()


# ==================================================================== LISTA


def test_mostra_o_catalogo_todo(janela):
    assert {e.chave for e in janela.estados()} == set(funcionalidades.CATALOGO)


def test_os_interruptores_comecam_a_dizer_a_verdade(janela):
    for chave, variavel in janela._variaveis.items():
        assert bool(variavel.get()) == funcionalidades.ativa(chave)


def test_cada_linha_explica_o_que_se_perde(janela):
    """Nomes técnicos sem explicação obrigam a experimentar em produção."""
    textos = []

    def percorrer(widget):
        for filho in widget.winfo_children():
            texto = str(filho.cget("text")) if "text" in filho.keys() else ""
            if texto:
                textos.append(texto)
            percorrer(filho)

    percorrer(janela.lista)
    juntos = " ".join(textos)
    assert "indicadores" in juntos.lower(), "o painel devia estar explicado"
    assert "csv" in juntos.lower(), "os relatórios deviam dizer o que exportam"


def test_a_essencial_aparece_travada_e_nao_escondida(janela):
    """Quem a procura tem de perceber porque não a pode desligar."""
    from tkinter import ttk

    encontrados = []

    def percorrer(widget):
        for filho in widget.winfo_children():
            if isinstance(filho, ttk.Checkbutton):
                encontrados.append(filho)
            percorrer(filho)

    percorrer(janela.lista)
    assert len(encontrados) == len(funcionalidades.CATALOGO)
    travados = [c for c in encontrados if "disabled" in c.state()]
    assert len(travados) == 1


# ================================================================== ALTERNAR


def test_desligar_pela_janela(janela):
    janela._variaveis["painel"].set(False)
    assert janela.alternar("painel") is True
    assert funcionalidades.ativa("painel") is False


def test_voltar_a_ligar_pela_janela(janela):
    funcionalidades.definir("painel", False)
    janela._variaveis["painel"].set(True)
    assert janela.alternar("painel") is True
    assert funcionalidades.ativa("painel") is True


def test_avisa_que_so_tem_efeito_ao_reabrir(janela):
    janela._variaveis["painel"].set(False)
    janela.alternar("painel")
    assert "reabra" in janela.mensagem.cget("text").lower()


def test_um_interruptor_recusado_volta_atras(janela):
    """O interruptor não pode ficar a dizer uma coisa e o estado outra."""
    janela._variaveis["copia_seguranca"].set(False)
    assert janela.alternar("copia_seguranca") is False

    assert janela._variaveis["copia_seguranca"].get() is True
    assert funcionalidades.ativa("copia_seguranca") is True


def test_repor_volta_tudo_ao_inicio(janela):
    funcionalidades.definir("painel", False)
    funcionalidades.definir("relatorios", False)
    janela.repor()

    assert all(e.ativa for e in janela.estados())
    assert all(bool(v.get()) for v in janela._variaveis.values())


# ================================================================ PERMISSÕES


def test_quem_nao_administra_nao_mexe(raiz):
    from tkinter import ttk

    from funcionalidades_ui import JanelaFuncionalidades

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    tela = JanelaFuncionalidades(raiz)
    try:
        interruptores = []

        def percorrer(widget):
            for filho in widget.winfo_children():
                if isinstance(filho, ttk.Checkbutton):
                    interruptores.append(filho)
                percorrer(filho)

        percorrer(tela.lista)
        assert interruptores
        assert all("disabled" in c.state() for c in interruptores)
        assert "disabled" in tela.botao_repor.state()
    finally:
        tela.destroy()


# ======================================= O EFEITO REAL NA JANELA PRINCIPAL


def abas(janela) -> list:
    from tkinter import ttk

    notebook = next(
        f for f in janela.winfo_children() if isinstance(f, ttk.Notebook)
    )
    return [notebook.tab(aba, "text") for aba in notebook.tabs()]


def test_com_o_painel_ligado_a_aba_existe(raiz):
    import gui

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    app = gui.criar_janela(raiz)
    assert "Dashboard" in abas(app)


def test_com_o_painel_desligado_a_aba_nao_e_construida(raiz):
    """Desligada é desligada: não é uma aba escondida."""
    import gui

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    funcionalidades.definir("painel", False)

    app = gui.criar_janela(raiz)
    rotulos = abas(app)
    assert "Dashboard" not in rotulos
    assert "Tarefas" in rotulos, "o resto da aplicação continua a funcionar"


def test_com_a_estrutura_desligada_a_entrada_sai_do_menu(raiz):
    import gui

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    funcionalidades.definir("estrutura", False)
    app = gui.criar_janela(raiz)

    barra = app.nametowidget(app.cget("menu"))
    submenu = app.nametowidget(barra.entrycget(0, "menu"))
    rotulos = [
        submenu.entrycget(i, "label")
        for i in range(submenu.index("end") + 1)
        if submenu.type(i) == "command"
    ]
    assert "Estrutura..." not in rotulos
    assert "Funcionalidades..." in rotulos, "tem de haver caminho de volta"
