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


# ============================================ A JANELA TEM DE SER VISTA


@pytest.mark.parametrize(
    "classe_nome", ["JanelaPrimeiroAdministrador", "JanelaLogin"]
)
def test_a_janela_de_sessao_aparece_com_a_raiz_escondida(raiz, classe_nome):
    """No arranque a raiz está escondida — e é aí que isto tem de funcionar.

    O `main.py` esconde a raiz Tk até haver sessão: a janela principal só nasce
    depois. Uma janela `transient` de um dono escondido é escondida com ele
    pelo gestor de janelas, e o programa fica a correr à espera de uma janela
    que ninguém vê. Foi assim que o executável deixou de abrir.
    """
    import login_ui

    raiz.withdraw()
    janela = getattr(login_ui, classe_nome)(raiz)
    raiz.update()
    try:
        assert janela.winfo_viewable(), (
            "a janela de início de sessão não está visível: o programa "
            "arrancaria sem nada no ecrã"
        )
    finally:
        janela.destroy()


def test_a_janela_de_sessao_segue_a_principal_quando_ela_existe(raiz):
    """Com um dono visível, `transient` volta a fazer sentido e é usado."""
    import login_ui

    raiz.deiconify()
    raiz.update()
    janela = login_ui.JanelaLogin(raiz)
    raiz.update()
    try:
        assert janela.winfo_viewable()
        assert janela.wm_transient(), "devia estar presa à janela dona"
    finally:
        janela.destroy()


# ============================================ PRIMEIRO ARRANQUE


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

        def winfo_exists(self):
            return True

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


def celula(tabela, linha: str, coluna: str) -> str:
    """Uma célula pelo *nome* da coluna.

    Indexar por posição torna qualquer coluna nova numa falha de teste que não
    diz nada sobre o que se partiu.
    """
    valores = tabela.item(linha, "values")
    return valores[tabela.cget("columns").index(coluna)]


def test_lista_as_contas(gestao):
    assert [c.nome_utilizador for c in gestao.contas()] == ["rodrigo"]
    assert celula(gestao.tabela, "rodrigo", "utilizador") == "rodrigo"
    assert celula(gestao.tabela, "rodrigo", "nome") == "Rodrigo Costa"
    assert celula(gestao.tabela, "rodrigo", "papel") == "Administrador"
    assert celula(gestao.tabela, "rodrigo", "estado") == "Ativa"


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
    assert celula(gestao.tabela, "ana", "estado") == "Inativa"

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

        def after(self, *args):
            pass

    def autenticar_falso(raiz, ao_abrir=None):
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
    monkeypatch.setattr("login_ui.autenticar", lambda raiz, ao_abrir=None: None)
    monkeypatch.setattr("gui.criar_janela", lambda raiz=None: construiu.append(1))

    assert main.abrir_aplicacao() == 0
    assert construiu == [], "sem sessão, a janela principal não chega a existir"


# ================================ O AUTOTESTE PERCORRE O ARRANQUE VERDADEIRO


def test_autenticar_avisa_quem_quer_ver_a_janela(raiz, com_conta, monkeypatch):
    """O gancho é o que permite verificar o arranque sem o imitar."""
    import login_ui

    vistas = []
    monkeypatch.setattr(raiz, "wait_window", lambda janela: janela.destroy())
    login_ui.autenticar(raiz, ao_abrir=vistas.append)

    assert len(vistas) == 1
    assert isinstance(vistas[0], login_ui.JanelaLogin)


def test_autenticar_sobrevive_a_um_gancho_que_fecha_a_janela(raiz, com_conta):
    """Esperar por uma janela que já não existe é um erro de Tcl, não uma espera."""
    import login_ui

    resultado = login_ui.autenticar(raiz, ao_abrir=lambda janela: janela.destroy())
    assert resultado is None


def test_o_arranque_real_e_verificado_e_nao_imitado(monkeypatch):
    """O autoteste tem de passar pela mesma função que o duplo-clique usa."""
    import main

    chamadas = {}

    def falso(ao_abrir_sessao=None, ao_abrir_principal=None):
        chamadas["ganchos"] = (ao_abrir_sessao is not None, ao_abrir_principal is not None)
        return 0

    monkeypatch.setattr(main, "abrir_aplicacao", falso)
    main.verificar_arranque_real(lambda *a, **k: None)

    assert chamadas["ganchos"] == (True, True)


def test_o_arranque_real_nao_cria_contas_na_instalacao(monkeypatch):
    """Criar o administrador aqui trancaria o utilizador fora do seu programa.

    Se a verificação usasse a área de dados real, passaria a existir uma conta
    e o ecrã de primeira utilização nunca mais apareceria a quem instalou.
    """
    import main
    from core import utilizadores
    from core.paths import diretorio_dados_utilizador

    antes = diretorio_dados_utilizador()
    assert not utilizadores.existe_algum()

    usadas = []

    def falso(ao_abrir_sessao=None, ao_abrir_principal=None):
        usadas.append(diretorio_dados_utilizador())
        return 0

    monkeypatch.setattr(main, "abrir_aplicacao", falso)
    main.verificar_arranque_real(lambda *a, **k: None)

    assert usadas and usadas[0] != antes, "devia correr numa área isolada"
    assert not utilizadores.existe_algum(), "não pode deixar contas para trás"
    assert diretorio_dados_utilizador() == antes, "e devia devolver tudo como estava"


def test_o_arranque_real_relata_quando_nada_aparece(monkeypatch):
    """Sem janela visível, a verificação falha em vez de ficar a esperar."""
    import main

    monkeypatch.setattr(
        main, "abrir_aplicacao", lambda ao_abrir_sessao=None, ao_abrir_principal=None: 0
    )
    resultados = {}
    main.verificar_arranque_real(
        lambda nome, condicao, detalhe="": resultados.__setitem__(nome, condicao)
    )

    assert resultados["janela de início de sessão visível"] is False
    assert resultados["janela principal visível"] is False
