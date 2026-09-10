"""Configuração global dos testes.

Coloca ``src/`` no ``sys.path`` e isola cada teste num diretório de dados
próprio, para que nenhum teste toque no banco, na configuração ou nos plugins
reais do utilizador.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent
SRC = RAIZ / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ENV_DATA_DIR  # noqa: E402


@pytest.fixture(autouse=True)
def dados_isolados(tmp_path, monkeypatch):
    """Aponta o diretório de dados da aplicação para uma pasta temporária."""
    destino = tmp_path / "dados"
    destino.mkdir()
    monkeypatch.setenv(ENV_DATA_DIR, str(destino))

    import language_manager

    language_manager.limpar_cache()
    language_manager.definir_idioma("pt", persistir=False)
    yield destino


@pytest.fixture
def raiz_projeto():
    """Raiz do repositório."""
    return RAIZ
