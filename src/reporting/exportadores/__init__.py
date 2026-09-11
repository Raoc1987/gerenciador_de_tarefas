"""Formatos de saída dos relatórios.

Cada exportador expõe ``EXTENSAO``, ``DESCRICAO`` e
``exportar(relatorio, destino) -> Path``. Acrescentar um formato novo é
acrescentar um módulo e uma linha no registo — nada na interface muda.
"""

from __future__ import annotations

from typing import Dict

from reporting.exportadores import csv_, pdf, xlsx

#: Formato -> módulo exportador.
EXPORTADORES: Dict[str, object] = {
    "pdf": pdf,
    "xlsx": xlsx,
    "csv": csv_,
}

#: Ordem em que aparecem ao utilizador.
FORMATOS = tuple(EXPORTADORES)


def obter(formato: str):
    """Devolve o módulo exportador de um formato.

    Raises:
        ValueError: se o formato não existir.
    """
    chave = (formato or "").strip().lower().lstrip(".")
    if chave not in EXPORTADORES:
        raise ValueError(
            f"Formato desconhecido: {formato!r}. Disponíveis: {', '.join(FORMATOS)}."
        )
    return EXPORTADORES[chave]


def extensao(formato: str) -> str:
    """Extensão de arquivo de um formato (ex.: ``.pdf``)."""
    return obter(formato).EXTENSAO


def descricao(formato: str) -> str:
    """Nome apresentável de um formato."""
    return obter(formato).DESCRICAO
