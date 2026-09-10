"""Fixtures partilhadas pelos testes do sistema de plugins."""

import json
import zipfile
from pathlib import Path

import pytest

from core.plugin_manager import PluginManager

#: Plugin mínimo que regista os eventos do ciclo de vida numa lista do módulo.
CORPO_OK = '''
from core.plugin_api import Plugin

eventos = []


class PluginDeTeste(Plugin):
    def inicializar(self):
        eventos.append("inicializar")

    def ativar(self):
        eventos.append("ativar")

    def desativar(self):
        eventos.append("desativar")

    def finalizar(self):
        eventos.append("finalizar")
'''

#: Plugin que falha ao ativar.
CORPO_FALHA_ATIVAR = '''
from core.plugin_api import Plugin


class PluginQuebrado(Plugin):
    def ativar(self):
        raise RuntimeError("falha proposital na ativação")
'''

#: Plugin que falha logo ao importar.
CORPO_FALHA_IMPORT = '''
raise ImportError("módulo partido de propósito")
'''

#: Módulo sem nenhuma subclasse de Plugin.
CORPO_SEM_CLASSE = "VALOR = 1\n"


def manifesto_valido(plugin_id: str = "demo", **alteracoes) -> dict:
    """Manifesto correto, com os campos que os testes queiram trocar."""
    dados = {
        "id": plugin_id,
        "name": plugin_id.replace("_", " ").title(),
        "version": "1.0.0",
        "author": "Testes",
        "description": "Plugin usado nos testes.",
        "min_app_version": "1.0.0",
        "entry_point": "plugin.py",
    }
    dados.update(alteracoes)
    return dados


@pytest.fixture
def pasta_plugins(tmp_path) -> Path:
    """Diretório que faz de ``plugins/installed`` nos testes."""
    destino = tmp_path / "installed"
    destino.mkdir()
    return destino


@pytest.fixture
def criar_plugin(pasta_plugins):
    """Cria uma pasta de plugin já instalada.

    Uso: ``criar_plugin("demo", corpo=CORPO_OK, version="2.0.0")``.
    """

    def _criar(plugin_id="demo", corpo=CORPO_OK, manifesto=None, **alteracoes) -> Path:
        pasta = pasta_plugins / plugin_id
        pasta.mkdir(parents=True, exist_ok=True)
        dados = manifesto if manifesto is not None else manifesto_valido(plugin_id, **alteracoes)
        conteudo = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
        (pasta / "plugin.json").write_text(conteudo, encoding="utf-8")
        if corpo is not None:
            (pasta / "plugin.py").write_text(corpo, encoding="utf-8")
        return pasta

    return _criar


@pytest.fixture
def criar_zip(tmp_path):
    """Cria um ``.zip`` de plugin a partir de um mapa ``caminho -> conteúdo``."""

    def _criar(nome: str, arquivos: dict) -> Path:
        caminho = tmp_path / nome
        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as pacote:
            for interno, conteudo in arquivos.items():
                pacote.writestr(interno, conteudo)
        return caminho

    return _criar


@pytest.fixture
def zip_valido(criar_zip):
    """``.zip`` de um plugin correto, com pasta de topo."""

    def _criar(plugin_id="demo", corpo=CORPO_OK, nome=None, **alteracoes) -> Path:
        manifesto = manifesto_valido(plugin_id, **alteracoes)
        return criar_zip(
            nome or f"{plugin_id}-{manifesto['version']}.zip",
            {
                f"{plugin_id}/plugin.json": json.dumps(manifesto),
                f"{plugin_id}/plugin.py": corpo,
            },
        )

    return _criar


@pytest.fixture
def gerenciador(pasta_plugins) -> PluginManager:
    """PluginManager isolado, apontado ao diretório temporário de plugins."""
    return PluginManager(diretorio=pasta_plugins, app_version="1.0.0")


@pytest.fixture(autouse=True)
def limpar_modulos_de_plugin():
    """Garante que módulos de plugin não sobrevivem de um teste para o outro."""
    import sys

    from core.plugin_manager import PREFIXO_MODULO

    yield
    for nome in [n for n in sys.modules if n.startswith(PREFIXO_MODULO)]:
        del sys.modules[nome]
