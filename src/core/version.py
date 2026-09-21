"""Fonte única da identidade e da versão da aplicação.

Todos os componentes (GUI, PluginManager, PyInstaller e Inno Setup) devem ler
a versão daqui para evitar divergências entre eles.
"""

from __future__ import annotations

from typing import Tuple

APP_NAME: str = "Gerenciador de Tarefas"
"""Nome apresentado ao utilizador."""

APP_ID: str = "GerenciadorDeTarefas"
"""Identificador sem espaços, usado em caminhos, executável e instalador."""

APP_VERSION: str = "1.1.0"
"""Versão semântica da aplicação (MAJOR.MINOR.PATCH)."""

APP_PUBLISHER: str = "Rodrigo Costa"
APP_URL: str = "https://github.com/Raoc1987/gerenciador_de_tarefas"


class VersaoInvalidaError(ValueError):
    """Levantada quando uma string de versão não é semântica."""


def parse_version(versao: str) -> Tuple[int, int, int]:
    """Converte ``"1.2.3"`` em ``(1, 2, 3)``.

    Aceita versões com menos componentes (``"1"`` -> ``(1, 0, 0)``) e ignora
    sufixos de pré-lançamento (``"1.2.3-beta"`` -> ``(1, 2, 3)``).

    Raises:
        VersaoInvalidaError: se a string não for uma versão reconhecível.
    """
    if not isinstance(versao, str) or not versao.strip():
        raise VersaoInvalidaError(f"Versão inválida: {versao!r}")

    nucleo = versao.strip().split("+", 1)[0].split("-", 1)[0]
    partes = nucleo.split(".")
    if len(partes) > 3:
        raise VersaoInvalidaError(f"Versão inválida: {versao!r}")

    numeros = []
    for parte in partes:
        if not parte.isdigit():
            raise VersaoInvalidaError(f"Versão inválida: {versao!r}")
        numeros.append(int(parte))
    while len(numeros) < 3:
        numeros.append(0)
    return numeros[0], numeros[1], numeros[2]


def comparar_versoes(a: str, b: str) -> int:
    """Devolve -1 se ``a < b``, 0 se iguais e 1 se ``a > b``."""
    va, vb = parse_version(a), parse_version(b)
    return (va > vb) - (va < vb)


def versao_compativel(
    min_app_version: str,
    max_app_version: str | None = None,
    app_version: str = APP_VERSION,
) -> bool:
    """Indica se a aplicação satisfaz o intervalo de versões pedido.

    ``max_app_version`` é inclusivo e opcional (previsto para uso futuro).
    """
    if comparar_versoes(app_version, min_app_version) < 0:
        return False
    if max_app_version and comparar_versoes(app_version, max_app_version) > 0:
        return False
    return True
