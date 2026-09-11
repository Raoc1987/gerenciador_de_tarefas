"""Testes das janelas de início de sessão e de gestão de contas."""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")
ttk = pytest.importorskip("tkinter.ttk", reason="ambiente sem Tkinter")

from core import permissoes, utilizadores  # noqa: E402
from core.permissoes import Permissao  # noqa: E402

SENHA = "plataforma2026"


@pytest.fixture
def raiz():
    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


def rotulos(widget):
    encontrados = []

    def percorrer(atual):
        for filho in atual.winfo_children():
            if isinstance(filho, ttk.Label):
                encontrados.append(str(filho.cget("text")))
            percorrer(filho)

    percorrer(widget)
    return encontrados


# ================================================= PRIMEIRO ADMINISTRADOR


def test_primeiro_arranque_pede_para_criar_administrador(raiz):
    from login_ui import JanelaPrimeiroAdministrador

    assert not utilizadores.existe_algum()
    janela = JanelaPrimeiroAdministrador(raiz)
    raiz.update()

    texto = " ".join(rotulos(janela))
    assert "não existe palavra-passe pré-definida" in texto
    janela.destroy()


def test_criar_o_primeiro_administrador(raiz):
    from login_ui import JanelaPrimeiroAdministrador

    janela = JanelaPrimeiroAdministrador(raiz)
    janela.entrada_nome.insert(0, "Rodrigo Costa")
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, SENHA)
    janela.entrada_confirmacao.insert(0, SENHA)
    janela.submeter()
    raiz.update()

    assert janela.resultado is not None
    assert janela.resultado.papel.pode(Permissao.SISTEMA_ADMIN)
    assert utilizadores.obter("rodrigo") is not None


def test_senhas_diferentes_nao_criam_conta(raiz):
    from login_ui import JanelaPrimeiroAdministrador

    janela = JanelaPrimeiroAdministrador(raiz)
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, SENHA)
    janela.entrada_confirmacao.insert(0, "outra-coisa-2026")
    janela.submeter()
    raiz.update()

    assert janela.resultado is None
    assert str(janela.mensagem.cget("text")) == "As palavras-passe não coincidem."
    assert not utilizadores.existe_algum()
    janela.destroy()


def test_senha_fraca_explica_o_que_falta(raiz):
    from login_ui import JanelaPrimeiroAdministrador

    janela = JanelaPrimeiroAdministrador(raiz)
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, "123")
    janela.entrada_confirmacao.insert(0, "123")
    janela.submeter()
    raiz.update()

    mensagem = str(janela.mensagem.cget("text"))
    assert "demasiado curta" in mensagem
    assert not utilizadores.existe_algum()
    janela.destroy()


def test_nome_de_utilizador_invalido_e_explicado(raiz):
    from login_ui import JanelaPrimeiroAdministrador

    janela = JanelaPrimeiroAdministrador(raiz)
    janela.entrada_utilizador.insert(0, "a b")
    janela.entrada_senha.insert(0, SENHA)
    janela.entrada_confirmacao.insert(0, SENHA)
    janela.submeter()
    raiz.update()

    assert "Nome de utilizador inválido" in str(janela.mensagem.cget("text"))
    janela.destroy()


# =========================================================== INÍCIO DE SESSÃO


@pytest.fixture
def com_conta():
    return utilizadores.criar("rodrigo", SENHA, "administrador", "Rodrigo Costa")


def test_entrar_com_credenciais_certas(raiz, com_conta):
    from login_ui import JanelaLogin

    janela = JanelaLogin(raiz)
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, SENHA)
    janela.submeter()
    raiz.update()

    assert janela.resultado is not None
    assert janela.resultado.nome_utilizador == "rodrigo"


def test_senha_errada_mostra_mensagem_e_limpa_o_campo(raiz, com_conta):
    from login_ui import JanelaLogin

    janela = JanelaLogin(raiz)
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, "errada12345")
    janela.submeter()
    raiz.update()

    assert janela.resultado is None
    assert str(janela.mensagem.cget("text")) == "Utilizador ou palavra-passe incorretos."
    assert janela.entrada_senha.get() == "", "a senha errada não fica no campo"
    assert janela.winfo_exists(), "a janela continua aberta para nova tentativa"
    janela.destroy()


def test_mensagem_de_bloqueio(raiz, com_conta):
    from login_ui import JanelaLogin

    for _ in range(utilizadores.TENTATIVAS_ATE_BLOQUEAR):
        utilizadores.autenticar("rodrigo", "errada12345")

    janela = JanelaLogin(raiz)
    janela.entrada_utilizador.insert(0, "rodrigo")
    janela.entrada_senha.insert(0, SENHA)
    janela.submeter()
    raiz.update()

    assert "Demasiadas tentativas" in str(janela.mensagem.cget("text"))
    assert janela.resultado is None
    janela.destroy()


def test_campo_da_senha_e_oculto(raiz, com_conta):
    from login_ui import JanelaLogin

    janela = JanelaLogin(raiz)
    assert str(janela.entrada_senha.cget("show")) != ""
    janela.destroy()


def test_cancelar_nao_autentica(raiz, com_conta):
    from login_ui import JanelaLogin

    janela = JanelaLogin(raiz)
    janela.cancelar()
    assert janela.resultado is None


def test_autenticar_inicia_a_sessao(raiz, com_conta, monkeypatch):
    import login_ui

    class JanelaFalsa:
        def __init__(self, master):
            self.resultado = com_conta

    monkeypatch.setattr(login_ui, "JanelaLogin", JanelaFalsa)
    monkeypatch.setattr(raiz, "wait_window", lambda _: None)

    utilizador = login_ui.autenticar(raiz)
    assert utilizador.nome_utilizador == "rodrigo"
    assert permissoes.sessao().utilizador == "rodrigo"


# ========================================================== GESTÃO DE CONTAS


@pytest.fixture
def gestao(raiz, com_conta):
    from utilizadores_ui import JanelaUtilizadores

    utilizadores.iniciar_sessao(com_conta)
    janela = JanelaUtilizadores(raiz)
    raiz.update()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


def test_lista_as_contas(gestao):
    assert [c.nome_utilizador for c in gestao.contas()] == ["rodrigo"]
    linha = gestao.tabela.item("rodrigo", "values")
    assert linha[0] == "rodrigo"
    assert linha[1] == "Rodrigo Costa"
    assert linha[2] == "Administrador"
    assert linha[3] == "Ativa"


def test_criar_conta_pelo_dialogo(gestao, raiz):
    from utilizadores_ui import DialogoConta

    dialogo = DialogoConta(gestao)
    dialogo.entrada_nome.insert(0, "Ana Silva")
    dialogo.entrada_utilizador.insert(0, "ana")
    dialogo.entrada_senha.insert(0, SENHA)
    dialogo.seletor_papel.set("Colaborador")
    dialogo.submeter()
    raiz.update()

    assert dialogo.resultado.papel_nome == "colaborador"
    gestao.recarregar()
    assert [c.nome_utilizador for c in gestao.contas()] == ["ana", "rodrigo"]


def test_dialogo_recusa_senha_fraca(gestao):
    from utilizadores_ui import DialogoConta

    dialogo = DialogoConta(gestao)
    dialogo.entrada_utilizador.insert(0, "ana")
    dialogo.entrada_senha.insert(0, "123")
    dialogo.submeter()

    assert dialogo.resultado is None
    assert "curta" in str(dialogo.mensagem.cget("text"))
    dialogo.destroy()


def test_desativar_e_reativar_conta(gestao, raiz):
    utilizadores.criar("ana", SENHA, "colaborador")
    gestao.recarregar()
    gestao.tabela.selection_set("ana")

    gestao.alternar_estado()
    raiz.update()
    assert utilizadores.obter("ana").ativo is False
    assert gestao.tabela.item("ana", "values")[3] == "Inativa"

    gestao.tabela.selection_set("ana")
    gestao.alternar_estado()
    assert utilizadores.obter("ana").ativo is True


def test_ultimo_administrador_e_protegido_com_mensagem(gestao, monkeypatch):
    import utilizadores_ui

    erros = []
    monkeypatch.setattr(
        utilizadores_ui.messagebox, "showerror", lambda *a, **k: erros.append(a)
    )
    monkeypatch.setattr(utilizadores_ui.messagebox, "askyesno", lambda *a, **k: True)

    gestao.tabela.selection_set("rodrigo")
    gestao.remover()

    assert erros, "tem de explicar porque recusou"
    assert "última conta de administração" in erros[-1][1]
    assert utilizadores.obter("rodrigo") is not None


def test_sem_permissao_nao_lista_contas(raiz, com_conta):
    from utilizadores_ui import JanelaUtilizadores

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    janela = JanelaUtilizadores(raiz)
    raiz.update()

    assert janela.contas() == []
    assert janela.tabela.get_children() == ()
    janela.destroy()


# ============================================================= NA APLICAÇÃO


def test_janela_principal_mostra_a_sessao(raiz, com_conta, monkeypatch, tmp_path):
    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: tmp_path / "p")
    monkeypatch.setattr(gui, "diretorio_plugins_embutidos", lambda: tmp_path / "sem")
    utilizadores.iniciar_sessao(com_conta)

    app = gui.criar_janela(raiz=raiz)
    app.update_idletasks()
    try:
        assert "Sessão: rodrigo" in rotulos(app)
        barra = app.nametowidget(app.cget("menu"))
        submenu = app.nametowidget(barra.entrycget(0, "menu"))
        opcoes = [
            submenu.entrycget(i, "label")
            for i in range(submenu.index("end") + 1)
            if submenu.type(i) == "command"
        ]
        assert "Utilizadores..." in opcoes
    finally:
        app.gerenciador_de_plugins.desativar_todos()


def test_colaborador_nao_ve_gestao_de_contas(raiz, com_conta, monkeypatch, tmp_path):
    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: tmp_path / "p")
    monkeypatch.setattr(gui, "diretorio_plugins_embutidos", lambda: tmp_path / "sem")
    permissoes.definir_sessao("ana", "colaborador", persistir=False)

    app = gui.criar_janela(raiz=raiz)
    app.update_idletasks()
    try:
        barra = app.nametowidget(app.cget("menu"))
        submenu = app.nametowidget(barra.entrycget(0, "menu"))
        opcoes = [
            submenu.entrycget(i, "label")
            for i in range(submenu.index("end") + 1)
            if submenu.type(i) == "command"
        ]
        assert "Utilizadores..." not in opcoes
        assert "Auditoria..." not in opcoes
        assert "Plugins..." in opcoes
    finally:
        app.gerenciador_de_plugins.desativar_todos()


def test_arranque_pede_sessao_antes_de_abrir(monkeypatch, com_conta):
    """main.abrir_aplicacao só constrói a janela depois de haver sessão."""
    import main

    ordem = []

    class JanelaFalsa:
        def mainloop(self):
            ordem.append("janela")

    def autenticar_falso(raiz):
        ordem.append("login")
        utilizadores.iniciar_sessao(com_conta)
        return com_conta

    monkeypatch.setattr("login_ui.autenticar", autenticar_falso)
    monkeypatch.setattr("gui.criar_janela", lambda raiz=None: JanelaFalsa())

    assert main.abrir_aplicacao() == 0
    assert ordem == ["login", "janela"]


def test_cancelar_o_login_fecha_a_aplicacao(monkeypatch, com_conta):
    import main

    construiu = []
    monkeypatch.setattr("login_ui.autenticar", lambda raiz: None)
    monkeypatch.setattr("gui.criar_janela", lambda raiz=None: construiu.append(1))

    assert main.abrir_aplicacao() == 0
    assert construiu == [], "sem sessão, a janela principal não chega a existir"
