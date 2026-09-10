"""Resolução de caminhos da aplicação.

Separa claramente três espaços distintos:

* **recursos**   – arquivos que acompanham a aplicação (assets, plugins
  embutidos). Em desenvolvimento ficam na árvore do projeto; empacotados pelo
  PyInstaller ficam em ``sys._MEIPASS`` ou junto do executável.
* **dados do utilizador** – banco de dados, configurações e plugins instalados.
  Nunca ficam em ``Program Files``: vão para ``%APPDATA%`` no Windows.
* **temporários** – área descartável usada durante a instalação de plugins.

A variável de ambiente ``GDT_DATA_DIR`` sobrepõe o diretório de dados do
utilizador (usada pelos testes e por instalações portáteis).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.version import APP_ID

ENV_DATA_DIR = "GDT_DATA_DIR"


def esta_congelado() -> bool:
    """``True`` quando a aplicação corre empacotada pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def diretorio_recursos() -> Path:
    """Raiz dos recursos somente-leitura que acompanham a aplicação."""
    if esta_congelado():
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
        return Path(sys.executable).parent
    # src/core/paths.py -> src/core -> src -> raiz do projeto
    return Path(__file__).resolve().parent.parent.parent


def caminho_recurso(*partes: str) -> Path:
    """Caminho de um recurso empacotado, ex.: ``caminho_recurso("assets", "idiomas")``."""
    return diretorio_recursos().joinpath(*partes)


def diretorio_dados_utilizador() -> Path:
    """Diretório onde ficam banco, configurações e plugins do utilizador."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / APP_ID
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / APP_ID


def garantir_diretorio(caminho: Path) -> Path:
    """Cria o diretório (e pais) se necessário e devolve-o."""
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def caminho_banco() -> Path:
    """Arquivo SQLite com as tarefas do utilizador."""
    return garantir_diretorio(diretorio_dados_utilizador()) / "tarefas.db"


def diretorio_config() -> Path:
    """Configurações da aplicação e dos plugins."""
    return garantir_diretorio(diretorio_dados_utilizador() / "config")


def diretorio_config_plugins() -> Path:
    """Configurações por plugin, isoladas da configuração geral."""
    return garantir_diretorio(diretorio_config() / "plugins")


def diretorio_plugins() -> Path:
    """Raiz dos plugins do utilizador."""
    return garantir_diretorio(diretorio_dados_utilizador() / "plugins")


def diretorio_plugins_instalados() -> Path:
    """Plugins instalados e disponíveis para carregamento."""
    return garantir_diretorio(diretorio_plugins() / "installed")


def diretorio_plugins_temp() -> Path:
    """Área temporária usada durante instalação/atualização de plugins."""
    return garantir_diretorio(diretorio_plugins() / "tmp")


def diretorio_plugins_embutidos() -> Path:
    """Plugins que acompanham a aplicação (somente leitura, podem não existir)."""
    return caminho_recurso("plugins", "available")


def diretorio_dados_plugin(plugin_id: str) -> Path:
    """Área de dados privada de um plugin."""
    return garantir_diretorio(diretorio_dados_utilizador() / "plugin_data" / plugin_id)


def diretorio_logs() -> Path:
    """Diretório dos arquivos de log."""
    return garantir_diretorio(diretorio_dados_utilizador() / "logs")
