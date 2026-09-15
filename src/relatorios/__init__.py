"""Geração e exportação de relatórios.

Separada da interface de propósito: a mesma função serve um botão na janela,
uma tarefa agendada ou um plugin. Ver ``docs/architecture/ADR-0003``.
"""

from relatorios.modelo import Indicadores, Lista, Relatorio, Tabela
from relatorios.servico import exportar, formatos_disponiveis, nome_sugerido

__all__ = [
    "Indicadores",
    "Lista",
    "Relatorio",
    "Tabela",
    "exportar",
    "formatos_disponiveis",
    "nome_sugerido",
]
