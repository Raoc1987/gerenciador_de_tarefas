"""Testes da interface gráfica real (Tkinter), incluindo a tela de plugins.

A janela é construída de verdade e os botões são acionados com ``invoke()``;
apenas os diálogos modais são substituídos, porque bloqueariam os testes.
Se o ambiente não tiver um servidor gráfico, os testes são ignorados.
"""

import json

import pytest

from conftest import (
    CORPO_FALHA_ATIVAR,
    TKINTER_DISPONIVEL,
    criar_janela_com_retentativa,
    manifesto_valido,
)

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")
ttk = pytest.importorskip("tkinter.ttk", reason="ambiente sem Tkinter")


CORPO_COM_ABA = '''
from core.plugin_api import Plugin


class PluginComAba(Plugin):
    def ativar(self):
        from tkinter import ttk

        self.contexto.ui.registrar_aba(
            self.id,
            "Aba do Plugin",
            lambda pai: ttk.Label(pai, text="conteúdo do plugin"),
        )
'''


@pytest.fixture
def dialogos(monkeypatch):
    """Substitui os diálogos modais e regista o que foi mostrado."""
    from tkinter import filedialog, messagebox

    registo = {"info": [], "erro": [], "aviso": [], "resposta": True, "arquivo": ""}

    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: registo["info"].append(a))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: registo["erro"].append(a))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: registo["aviso"].append(a))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: registo["resposta"])
    monkeypatch.setattr(filedialog, "askopenfilename", lambda *a, **k: registo["arquivo"])

    import plugin_ui

    monkeypatch.setattr(plugin_ui, "messagebox", messagebox)
    monkeypatch.setattr(plugin_ui, "filedialog", filedialog)
    return registo


@pytest.fixture
def janela(dialogos, pasta_plugins, tmp_path, monkeypatch):
    """Janela principal real, com os diretórios de plugins isolados.

    Os plugins embutidos apontam para uma pasta inexistente: cada teste
    controla o que está instalado. A semeadura tem o seu próprio teste.
    """
    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    monkeypatch.setattr(gui, "diretorio_plugins_embutidos", lambda: tmp_path / "sem_embutidos")
    app = criar_janela_com_retentativa(gui.criar_janela)
    app.update_idletasks()
    yield app
    try:
        app.gerenciador_de_plugins.desativar_todos()
        app.destroy()
    except tk.TclError:  # pragma: no cover
        pass


def descendentes(widget):
    """Todos os widgets sob ``widget``, em profundidade."""
    for filho in widget.winfo_children():
        yield filho
        yield from descendentes(filho)


def botoes(widget):
    """Mapa ``texto -> botão`` dos botões visíveis sob ``widget``."""
    return {
        str(w.cget("text")): w
        for w in descendentes(widget)
        if isinstance(w, ttk.Button)
    }


def entradas(widget):
    """Campos de texto — exclui Combobox, que herda de ttk.Entry."""
    return [
        w
        for w in descendentes(widget)
        if isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox)
    ]


def listbox(widget):
    return next(w for w in descendentes(widget) if isinstance(w, tk.Listbox))


def notebook_de(janela):
    """O Notebook principal da janela."""
    return next(w for w in descendentes(janela) if isinstance(w, ttk.Notebook))


def titulos_das_abas(janela):
    """Rótulos das abas, pela ordem em que aparecem."""
    notebook = notebook_de(janela)
    return [notebook.tab(i, "text") for i in range(notebook.index("end"))]


def aba(janela, rotulo):
    """O conteúdo da aba com o rótulo indicado.

    Os testes dizem em que aba estão a mexer: a janela tem Dashboard, Tarefas
    e, quando há plugins ativos, as abas deles.
    """
    notebook = notebook_de(janela)
    for indice in range(notebook.index("end")):
        if notebook.tab(indice, "text") == rotulo:
            return janela.nametowidget(notebook.tabs()[indice])
    raise AssertionError(f"aba {rotulo!r} não encontrada em {titulos_das_abas(janela)}")


def tarefas(janela):
    """Atalho para a aba de tarefas (o rótulo muda com o idioma)."""
    for rotulo in ("Tarefas", "Tasks", "Tareas"):
        try:
            return aba(janela, rotulo)
        except AssertionError:
            continue
    raise AssertionError(f"aba de tarefas não encontrada em {titulos_das_abas(janela)}")


# ============================================================ JANELA PRINCIPAL


def test_janela_abre_com_dashboard_e_tarefas(janela):
    assert titulos_das_abas(janela) == ["Dashboard", "Tarefas"]
    assert janela.title() == "Gerenciador de Tarefas"


def test_menu_de_configuracoes_tem_plugins(janela):
    barra = janela.nametowidget(janela.cget("menu"))
    assert barra.entrycget(0, "label") == "Configurações"
    submenu = janela.nametowidget(barra.entrycget(0, "menu"))
    assert submenu.entrycget(0, "label") == "Plugins..."


def test_adicionar_tarefa_pela_interface(janela):
    import banco_de_dados

    painel = tarefas(janela)
    campos = entradas(painel)
    campos[0].insert(0, "Tarefa da GUI")
    campos[1].insert(0, "2026-05-01")
    botoes(painel)["Adicionar"].invoke()
    janela.update()

    assert [t[1] for t in banco_de_dados.buscar_tarefas()] == ["Tarefa da GUI"]
    assert "Tarefa da GUI" in listbox(painel).get(0)


def test_data_invalida_avisa_e_nao_grava(janela, dialogos):
    import banco_de_dados

    painel = tarefas(janela)
    campos = entradas(painel)
    campos[0].insert(0, "Com data ruim")
    campos[1].insert(0, "01/05/2026")
    botoes(painel)["Adicionar"].invoke()
    assert dialogos["aviso"]
    assert banco_de_dados.buscar_tarefas() == []


def test_concluir_e_remover_pela_interface(janela, dialogos):
    import banco_de_dados

    painel = tarefas(janela)
    entradas(painel)[0].insert(0, "Para concluir")
    botoes(painel)["Adicionar"].invoke()
    lista = listbox(painel)
    lista.selection_set(0)
    botoes(painel)["Concluir"].invoke()
    assert banco_de_dados.buscar_tarefas()[0][3] == 1
    assert "✔" in lista.get(0)

    lista.selection_set(0)
    botoes(painel)["Remover"].invoke()
    assert banco_de_dados.buscar_tarefas() == []


def test_troca_de_idioma_atualiza_a_interface(janela):
    import language_manager as lm

    variavel = next(
        w for w in descendentes(janela) if isinstance(w, ttk.OptionMenu)
    )
    menu = janela.nametowidget(variavel.cget("menu"))
    menu.invoke(menu.index("Inglês 🇺🇸"))
    janela.update()

    assert lm.idioma_atual() == "en"
    assert janela.title() == "Task Manager"
    assert titulos_das_abas(janela) == ["Dashboard", "Tasks"]
    assert "Add" in botoes(tarefas(janela))
    barra = janela.nametowidget(janela.cget("menu"))
    assert barra.entrycget(0, "label") == "Settings"


# ============================================================ TELA DE PLUGINS


def abrir_plugins(janela):
    """Abre a tela de plugins pelo menu e devolve a janela criada."""
    barra = janela.nametowidget(janela.cget("menu"))
    submenu = janela.nametowidget(barra.entrycget(0, "menu"))
    submenu.invoke(0)
    janela.update()
    from plugin_ui import JanelaPlugins

    return next(f for f in janela.winfo_children() if isinstance(f, JanelaPlugins))


def test_tela_de_plugins_sem_plugins(janela):
    tela = abrir_plugins(janela)
    rotulos = [
        str(w.cget("text"))
        for w in descendentes(tela)
        if isinstance(w, ttk.Label)
    ]
    assert "Nenhum plugin instalado." in rotulos
    tela.destroy()


def test_tela_de_plugins_lista_o_plugin_instalado(janela, criar_plugin):
    criar_plugin("demo")
    tela = abrir_plugins(janela)
    textos = [
        str(w.cget("text"))
        for w in descendentes(tela)
        if isinstance(w, (ttk.Label, ttk.LabelFrame))
    ]
    assert "Demo  v1.0.0" in textos
    assert "Status: Inativo" in textos
    assert "Ativar" in botoes(tela)
    tela.destroy()


def test_ativar_e_desativar_pela_tela(janela, criar_plugin):
    criar_plugin("demo")
    tela = abrir_plugins(janela)
    botoes(tela)["Ativar"].invoke()
    janela.update()

    gerenciador = janela.gerenciador_de_plugins
    assert gerenciador.obter("demo").ativo
    textos = [str(w.cget("text")) for w in descendentes(tela) if isinstance(w, ttk.Label)]
    assert "Status: Ativo" in textos

    botoes(tela)["Desativar"].invoke()
    janela.update()
    assert not gerenciador.obter("demo").ativo
    tela.destroy()


def test_plugin_adiciona_aba_a_janela_principal(janela, criar_plugin):
    criar_plugin("comaba", corpo=CORPO_COM_ABA)
    tela = abrir_plugins(janela)
    botoes(tela)["Ativar"].invoke()
    janela.update()

    assert titulos_das_abas(janela) == ["Dashboard", "Tarefas", "Aba do Plugin"]

    botoes(tela)["Desativar"].invoke()
    janela.update()
    assert titulos_das_abas(janela) == ["Dashboard", "Tarefas"]
    tela.destroy()


def test_plugin_com_erro_mostra_mensagem_amigavel(janela, criar_plugin, dialogos):
    criar_plugin("quebrado", corpo=CORPO_FALHA_ATIVAR)
    tela = abrir_plugins(janela)
    botoes(tela)["Ativar"].invoke()
    janela.update()

    assert dialogos["erro"], "deveria ter mostrado um erro"
    titulo, texto = dialogos["erro"][-1][0], dialogos["erro"][-1][1]
    assert titulo == "Erro"
    assert texto.startswith("Não foi possível ativar o plugin.")
    assert "falha proposital" in texto  # detalhes técnicos incluídos
    assert "Traceback" not in texto
    tela.destroy()


def test_plugin_incompativel_nao_pode_ser_ativado(janela, criar_plugin):
    criar_plugin("futuro", min_app_version="99.0.0")
    tela = abrir_plugins(janela)
    assert "disabled" in botoes(tela)["Ativar"].state()
    textos = [str(w.cget("text")) for w in descendentes(tela) if isinstance(w, ttk.Label)]
    assert "Status: Incompatível" in textos
    tela.destroy()


def test_instalar_plugin_por_zip_pela_tela(janela, zip_valido, dialogos):
    dialogos["arquivo"] = str(zip_valido("novo"))
    dialogos["resposta"] = True  # responde "sim" a "ativar agora?"
    tela = abrir_plugins(janela)
    botoes(tela)["+ Instalar Plugin"].invoke()
    janela.update()

    gerenciador = janela.gerenciador_de_plugins
    assert gerenciador.obter("novo") is not None
    assert gerenciador.obter("novo").ativo
    assert any("Plugin instalado com sucesso." in a for a in dialogos["info"][-1])
    tela.destroy()


def test_instalar_zip_invalido_mostra_erro(janela, criar_zip, dialogos):
    dialogos["arquivo"] = str(criar_zip("mau.zip", {"leiame.txt": "nada"}))
    tela = abrir_plugins(janela)
    botoes(tela)["+ Instalar Plugin"].invoke()
    janela.update()

    assert dialogos["erro"]
    assert "não é um pacote de plugin válido" in dialogos["erro"][-1][1]
    tela.destroy()


def test_remover_plugin_pela_tela(janela, criar_plugin, dialogos):
    pasta = criar_plugin("demo")
    dialogos["resposta"] = True  # confirma remoção e remoção de dados
    tela = abrir_plugins(janela)
    botoes(tela)["Remover"].invoke()
    janela.update()

    assert not pasta.exists()
    assert janela.gerenciador_de_plugins.obter("demo") is None
    tela.destroy()


def test_cancelar_remocao_mantem_o_plugin(janela, criar_plugin, dialogos):
    pasta = criar_plugin("demo")
    dialogos["resposta"] = False
    tela = abrir_plugins(janela)
    botoes(tela)["Remover"].invoke()
    janela.update()

    assert pasta.exists()
    tela.destroy()


def test_atualizar_plugin_pela_tela(janela, criar_plugin, zip_valido, dialogos):
    criar_plugin("demo", version="1.0.0")
    dialogos["arquivo"] = str(zip_valido("demo", version="2.0.0"))
    dialogos["resposta"] = False  # não ativar agora
    tela = abrir_plugins(janela)
    botoes(tela)["Atualizar"].invoke()
    janela.update()

    assert janela.gerenciador_de_plugins.versao_instalada("demo") == "2.0.0"
    tela.destroy()


def test_plugin_ativo_arranca_na_proxima_abertura(
    janela, criar_plugin, pasta_plugins, dialogos, monkeypatch
):
    criar_plugin("demo")
    tela = abrir_plugins(janela)
    botoes(tela)["Ativar"].invoke()
    tela.destroy()
    janela.gerenciador_de_plugins.desativar_todos()
    janela.destroy()

    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    nova = criar_janela_com_retentativa(gui.criar_janela)
    nova.update_idletasks()
    try:
        assert nova.gerenciador_de_plugins.obter("demo").ativo
    finally:
        nova.gerenciador_de_plugins.desativar_todos()
        nova.destroy()


def test_plugin_quebrado_nao_impede_a_janela_de_abrir(
    janela, criar_plugin, pasta_plugins, dialogos, monkeypatch
):
    """Um plugin habilitado que falha ao ativar não derruba a aplicação."""
    criar_plugin("quebrado", corpo=CORPO_FALHA_ATIVAR)
    janela.gerenciador_de_plugins.descobrir()
    janela.gerenciador_de_plugins.registro.definir_habilitado("quebrado", True)
    janela.destroy()

    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    nova = criar_janela_com_retentativa(gui.criar_janela)
    nova.update_idletasks()
    try:
        assert nova.winfo_exists()
        assert dialogos["aviso"], "deveria avisar sobre o plugin que falhou"
        assert "Quebrado" in dialogos["aviso"][-1][1]
        assert not nova.gerenciador_de_plugins.obter("quebrado").ativo
    finally:
        nova.destroy()


def test_manifesto_invalido_aparece_na_tela(janela, pasta_plugins):
    (pasta_plugins / "estragado").mkdir()
    (pasta_plugins / "estragado" / "plugin.json").write_text("{ mau", encoding="utf-8")
    tela = abrir_plugins(janela)
    textos = [str(w.cget("text")) for w in descendentes(tela) if isinstance(w, ttk.Label)]
    assert "Status: Inválido" in textos
    assert "disabled" in botoes(tela)["Ativar"].state()
    tela.destroy()


def test_id_divergente_e_reportado(janela, criar_plugin):
    criar_plugin("pasta_x", manifesto=json.dumps(manifesto_valido("outro")))
    tela = abrir_plugins(janela)
    textos = [str(w.cget("text")) for w in descendentes(tela) if isinstance(w, ttk.Label)]
    assert any("não corresponde" in t for t in textos)
    tela.destroy()


CORPO_ABA_TRADUZIDA = '''
from core.plugin_api import Plugin


class PluginAbaTraduzida(Plugin):
    def ativar(self):
        from tkinter import ttk

        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba"),
            lambda pai: ttk.Label(pai, text="x"),
        )
'''


def test_titulo_da_aba_do_plugin_segue_o_idioma(janela, criar_plugin):
    pasta = criar_plugin("traduzido", corpo=CORPO_ABA_TRADUZIDA)
    idiomas = pasta / "idiomas"
    idiomas.mkdir()
    (idiomas / "pt.json").write_text(json.dumps({"aba": "Calendário"}), encoding="utf-8")
    (idiomas / "en.json").write_text(json.dumps({"aba": "Calendar"}), encoding="utf-8")

    tela = abrir_plugins(janela)
    botoes(tela)["Ativar"].invoke()
    janela.update()
    tela.destroy()

    assert titulos_das_abas(janela) == ["Dashboard", "Tarefas", "Calendário"]

    variavel = next(w for w in descendentes(janela) if isinstance(w, ttk.OptionMenu))
    menu = janela.nametowidget(variavel.cget("menu"))
    menu.invoke(menu.index("Inglês 🇺🇸"))
    janela.update()

    assert titulos_das_abas(janela) == ["Dashboard", "Tasks", "Calendar"]


def test_plugins_embutidos_sao_semeados_no_arranque(
    dialogos, pasta_plugins, raiz_projeto, monkeypatch
):
    """No arranque, os plugins que acompanham a aplicação ficam instalados."""
    import core.plugin_manager as pm_modulo
    import gui

    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    monkeypatch.setattr(
        gui, "diretorio_plugins_embutidos", lambda: raiz_projeto / "plugins" / "available"
    )

    app = criar_janela_com_retentativa(gui.criar_janela)
    try:
        gerenciador = app.gerenciador_de_plugins
        registro = gerenciador.obter("calendar")
        assert registro is not None, "o plugin embutido deveria ter sido instalado"
        assert registro.estado.utilizavel
        # Instalado mas desativado: a decisão de ativar é do utilizador.
        assert not registro.ativo
        assert (pasta_plugins / "calendar" / "plugin.json").is_file()
    finally:
        app.gerenciador_de_plugins.desativar_todos()
        app.destroy()


def test_semeadura_nao_substitui_o_plugin_do_utilizador(
    dialogos, pasta_plugins, raiz_projeto, criar_plugin, monkeypatch
):
    """Uma versão já instalada pelo utilizador nunca é sobreposta."""
    import core.plugin_manager as pm_modulo
    import gui

    criar_plugin("calendar", version="0.9.0")
    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    monkeypatch.setattr(
        gui, "diretorio_plugins_embutidos", lambda: raiz_projeto / "plugins" / "available"
    )

    app = criar_janela_com_retentativa(gui.criar_janela)
    try:
        assert app.gerenciador_de_plugins.versao_instalada("calendar") == "0.9.0"
    finally:
        app.destroy()


# ========================================================== TELA DE AUDITORIA


def invocar_no_menu(janela, chave: str) -> None:
    """Clica na entrada de Configurações cujo rótulo vem de ``chave``.

    Procurar pelo rótulo e não pela posição: uma entrada nova no menu não
    devia partir um teste que nada tem a ver com ela.
    """
    from language_manager import carregar_texto

    procurado = carregar_texto(chave) + "..."
    barra = janela.nametowidget(janela.cget("menu"))
    submenu = janela.nametowidget(barra.entrycget(0, "menu"))
    for indice in range(submenu.index("end") + 1):
        if submenu.type(indice) == "command" and submenu.entrycget(indice, "label") == procurado:
            submenu.invoke(indice)
            janela.update()
            return
    raise AssertionError(f"Não há entrada {procurado!r} no menu Configurações.")


def abrir_auditoria(janela):
    """Abre Configurações → Auditoria e devolve a janela criada."""
    from auditoria_ui import JanelaAuditoria

    invocar_no_menu(janela, "auditoria")
    return next(f for f in janela.winfo_children() if isinstance(f, JanelaAuditoria))


def rotulos_do_menu(janela):
    """Os comandos do menu Configurações."""
    barra = janela.nametowidget(janela.cget("menu"))
    submenu = janela.nametowidget(barra.entrycget(0, "menu"))
    return [
        submenu.entrycget(i, "label")
        for i in range(submenu.index("end") + 1)
        if submenu.type(i) == "command"
    ]


def test_menu_tem_auditoria_para_administrador(janela):
    assert "Auditoria..." in rotulos_do_menu(janela)


def test_menu_tem_estrutura_e_copia_para_administrador(janela):
    """As duas telas de administração chegam-se pelo mesmo sítio."""
    rotulos = rotulos_do_menu(janela)
    assert "Estrutura..." in rotulos
    assert "Cópia de segurança..." in rotulos


def test_abrir_a_copia_de_seguranca_pelo_menu(janela):
    from backup_ui import JanelaBackup

    invocar_no_menu(janela, "backup")
    assert any(isinstance(f, JanelaBackup) for f in janela.winfo_children())


def test_abrir_a_estrutura_pelo_menu(janela):
    from organizacao_ui import JanelaOrganizacao

    invocar_no_menu(janela, "estrutura")
    assert any(isinstance(f, JanelaOrganizacao) for f in janela.winfo_children())


def test_auditoria_mostra_o_que_aconteceu(janela):
    import banco_de_dados
    from core import auditoria

    auditoria.ativar()
    banco_de_dados.criar_tabela()
    tarefa_id = banco_de_dados.adicionar_tarefa("Tarefa auditada pela GUI")
    banco_de_dados.concluir_tarefa(tarefa_id)

    tela = abrir_auditoria(janela)
    eventos_mostrados = [r.evento for r in tela.registos()]
    assert "tarefa.criada" in eventos_mostrados
    assert "tarefa.concluida" in eventos_mostrados

    linhas = tela.tabela.get_children()
    assert len(linhas) == len(tela.registos())

    # A ordem é do mais recente para o mais antigo. Fixar *qual* é o mais
    # recente partiria sempre que a aplicação passasse a registar mais um
    # evento — como passou, com os alertas da análise.
    momentos = [tela.tabela.item(l, "values")[0] for l in linhas]
    assert momentos == sorted(momentos, reverse=True)

    mostrados = [r.evento for r in tela.registos()]
    assert mostrados.index("tarefa.concluida") < mostrados.index("tarefa.criada")
    tela.destroy()


def test_auditoria_filtra_por_familia(janela):
    import banco_de_dados
    from core import auditoria, eventos as eventos_modulo
    from core.eventos import Evento

    auditoria.ativar()
    banco_de_dados.criar_tabela()
    banco_de_dados.adicionar_tarefa("Uma tarefa")
    auditoria.registar(
        Evento(
            nome=eventos_modulo.PLUGIN_ATIVADO,
            dados={"id": "calendar"},
            momento="2026-01-01T10:00:00",
        )
    )

    tela = abrir_auditoria(janela)
    # A janela também regista app.iniciada: por isso se filtra em vez de contar.
    todos = [r.evento for r in tela.registos()]
    assert "tarefa.criada" in todos and "plugin.ativado" in todos

    tela._filtro_var.set("Plugins")
    tela.recarregar()
    assert [r.evento for r in tela.registos()] == ["plugin.ativado"]

    tela._filtro_var.set("Tarefas")
    tela.recarregar()
    assert [r.evento for r in tela.registos()] == ["tarefa.criada"]
    tela.destroy()


def test_auditoria_nao_apaga_nada(janela):
    """A tela é de leitura: nenhum botão remove registos."""
    import banco_de_dados
    from core import auditoria

    auditoria.ativar()
    banco_de_dados.criar_tabela()
    banco_de_dados.adicionar_tarefa("Fica registada")

    antes = auditoria.contar()
    tela = abrir_auditoria(janela)
    rotulos = set(botoes(tela))
    assert not {"Remover", "Apagar", "Limpar"} & rotulos
    assert auditoria.contar() == antes, "abrir a tela não pode mexer na trilha"
    assert "tarefa.criada" in [r.evento for r in tela.registos()]
    tela.destroy()
