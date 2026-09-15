"""Testes do plugin real Calendar Integration, do ``.zip`` até à aba na janela.

Estes testes usam a pasta ``plugins/available/calendar`` do repositório — não
um plugin fabricado — de modo a provar o percurso completo:
empacotar -> instalar -> validar -> registar -> carregar -> ativar -> usar.
"""

import sys

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa
from core.plugin_api import EstadoPlugin
from core.plugin_manager import PREFIXO_MODULO
from tools.empacotar_plugin import empacotar

# O plugin Calendar Integration constrói widgets: sem Tkinter não há o que testar.
tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")
ttk = pytest.importorskip("tkinter.ttk", reason="ambiente sem Tkinter")


@pytest.fixture
def pasta_do_plugin(raiz_projeto):
    """Pasta do plugin Calendar Integration no repositório."""
    pasta = raiz_projeto / "plugins" / "available" / "calendar"
    assert pasta.is_dir(), "o plugin calendar deve existir no repositório"
    return pasta


@pytest.fixture
def versao_do_plugin(pasta_do_plugin):
    """A versão que o manifesto declara, lida e não escrita à mão.

    Corrigir um plugin embutido obriga a subir-lhe a versão (ADR-0006): é ela
    que faz a correção chegar a quem já o tinha. Um teste que fixasse aqui o
    número transformava essa subida numa falha.
    """
    import json

    return json.loads((pasta_do_plugin / "plugin.json").read_text(encoding="utf-8"))["version"]


@pytest.fixture
def zip_calendar(pasta_do_plugin, tmp_path):
    """Empacota o plugin real num ``.zip`` temporário."""
    return empacotar(pasta_do_plugin, tmp_path / "pacotes")


# ------------------------------------------------------------ empacotamento


def test_pacote_tem_a_estrutura_esperada(zip_calendar):
    import zipfile

    with zipfile.ZipFile(zip_calendar) as pacote:
        nomes = pacote.namelist()
    assert "calendar/plugin.json" in nomes
    assert "calendar/plugin.py" in nomes
    assert "calendar/idiomas/pt.json" in nomes
    assert not any("__pycache__" in nome for nome in nomes)


def test_nome_do_pacote_usa_id_e_versao(zip_calendar, versao_do_plugin):
    assert zip_calendar.name == f"calendar-{versao_do_plugin}.zip"


# --------------------------------------------------------------- instalação


def test_instalar_o_plugin_real(gerenciador, zip_calendar, versao_do_plugin):
    resultado = gerenciador.instalar_zip(zip_calendar)
    assert resultado.sucesso, resultado.detalhes
    assert resultado.plugin_id == "calendar"

    registro = gerenciador.obter("calendar")
    assert registro.estado == EstadoPlugin.INSTALADO
    assert registro.nome == "Calendar Integration"
    assert registro.versao == versao_do_plugin
    assert (gerenciador.diretorio / "calendar" / "idiomas" / "pt.json").is_file()


def test_carregar_o_plugin_real_sem_interface(gerenciador, zip_calendar):
    """Sem GUI o plugin ativa na mesma, apenas sem registar a aba."""
    gerenciador.instalar_zip(zip_calendar)
    resultado = gerenciador.ativar("calendar")
    assert resultado.sucesso, resultado.detalhes
    assert gerenciador.obter("calendar").ativo


def test_idiomas_do_plugin_real(gerenciador, zip_calendar):
    import language_manager as lm

    gerenciador.instalar_zip(zip_calendar)
    gerenciador.ativar("calendar")

    lm.definir_idioma("pt", persistir=False)
    assert lm.carregar_texto_plugin("calendar", "aba") == "Calendário"
    lm.definir_idioma("en", persistir=False)
    assert lm.carregar_texto_plugin("calendar", "aba") == "Calendar"
    lm.definir_idioma("es", persistir=False)
    assert lm.carregar_texto_plugin("calendar", "aba") == "Calendario"


def test_atualizacao_do_plugin_real(gerenciador, pasta_do_plugin, tmp_path, monkeypatch):
    """Instala a versão do repositório e atualiza para uma v1.1.0 da hora."""
    import json
    import shutil

    gerenciador.instalar_zip(empacotar(pasta_do_plugin, tmp_path / "v1"))
    gerenciador.ativar("calendar")

    copia = tmp_path / "fonte_v11"
    shutil.copytree(pasta_do_plugin, copia)
    manifesto = json.loads((copia / "plugin.json").read_text(encoding="utf-8"))
    manifesto["version"] = "1.1.0"
    (copia / "plugin.json").write_text(json.dumps(manifesto), encoding="utf-8")

    resultado = gerenciador.instalar_zip(empacotar(copia, tmp_path / "v11"))
    assert resultado.sucesso
    assert resultado.chave_mensagem == "plugin_atualizado"
    assert gerenciador.versao_instalada("calendar") == "1.1.0"

    # Continua utilizável depois da atualização.
    assert gerenciador.ativar("calendar").sucesso


def test_remover_o_plugin_real(gerenciador, zip_calendar):
    gerenciador.instalar_zip(zip_calendar)
    gerenciador.ativar("calendar")
    assert gerenciador.remover("calendar").sucesso
    assert not (gerenciador.diretorio / "calendar").exists()
    assert gerenciador.obter("calendar") is None


# ------------------------------------------------------------------- na GUI


@pytest.mark.skipif(not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica")
def test_plugin_real_na_janela(pasta_plugins, zip_calendar, tmp_path, monkeypatch):
    """Percurso completo: instalar o zip, ativar e usar a aba do calendário."""
    from tkinter import messagebox

    import core.plugin_manager as pm_modulo
    import banco_de_dados
    import gui

    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(pm_modulo, "diretorio_plugins_instalados", lambda: pasta_plugins)
    monkeypatch.setattr(gui, "diretorio_plugins_embutidos", lambda: tmp_path / "sem_embutidos")

    banco_de_dados.criar_tabela()
    banco_de_dados.adicionar_tarefa("Reunião de equipa", "2026-06-15")

    app = criar_janela_com_retentativa(gui.criar_janela)
    try:
        gerenciador = app.gerenciador_de_plugins
        assert gerenciador.instalar_zip(zip_calendar).sucesso
        assert gerenciador.ativar("calendar").sucesso
        app.update()

        notebook = next(
            w for w in _todos(app) if isinstance(w, ttk.Notebook)
        )
        titulos = [notebook.tab(i, "text") for i in range(notebook.index("end"))]
        assert titulos == ["Dashboard", "Tarefas", "Calendário"]

        # O painel do plugin mostra as tarefas do dia selecionado.
        modulo = sys.modules[PREFIXO_MODULO + "calendar"]
        painel = next(w for w in _todos(app) if isinstance(w, modulo.PainelCalendario))
        painel.mostrar_dia("2026-06-15")
        app.update()
        lista = next(w for w in _todos(painel) if isinstance(w, tk.Listbox))
        assert "Reunião de equipa" in lista.get(0)

        painel.mostrar_dia("2026-06-16")
        assert lista.get(0) == "Nenhuma tarefa nesta data."

        # Criar uma tarefa pela aba do plugin chega ao banco da aplicação.
        entrada = next(w for w in _todos(painel) if isinstance(w, ttk.Entry))
        entrada.insert(0, "Tarefa criada no calendário")
        next(
            w
            for w in _todos(painel)
            if isinstance(w, ttk.Button) and str(w.cget("text")) == "Adicionar"
        ).invoke()
        app.update()

        descricoes = [t[1] for t in banco_de_dados.tarefas_por_data("2026-06-16")]
        assert descricoes == ["Tarefa criada no calendário"]
        assert "Tarefa criada no calendário" in lista.get(0)

        # Desativar remove a aba, sem tocar nas tarefas.
        gerenciador.desativar("calendar")
        app.update()
        assert notebook.index("end") == 2, "fica o Dashboard e as Tarefas"
        assert len(banco_de_dados.buscar_tarefas()) == 2
    finally:
        app.gerenciador_de_plugins.desativar_todos()
        app.destroy()


def _todos(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from _todos(filho)
