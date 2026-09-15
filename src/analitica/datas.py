"""Conversão e intervalos de datas usados pela análise."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator, List, Optional


def para_data(valor) -> Optional[date]:
    """Converte para :class:`datetime.date` o que vier do banco.

    Aceita ``date``, ``datetime``, ``"AAAA-MM-DD"`` e ISO com hora. Devolve
    ``None`` para vazio ou formato desconhecido — nunca adivinha uma data.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


def intervalo_de_dias(fim: date, dias: int) -> tuple:
    """Intervalo ``(início, fim)`` com ``dias`` dias, terminando em ``fim``."""
    if dias < 1:
        raise ValueError("O intervalo tem de ter pelo menos um dia.")
    return fim - timedelta(days=dias - 1), fim


def periodo_anterior(inicio: date, fim: date) -> tuple:
    """O período imediatamente antes, com a mesma duração."""
    duracao = (fim - inicio).days + 1
    novo_fim = inicio - timedelta(days=1)
    return novo_fim - timedelta(days=duracao - 1), novo_fim


def dias_entre(inicio: date, fim: date) -> Iterator[date]:
    """Todos os dias de ``inicio`` a ``fim``, inclusive."""
    atual = inicio
    while atual <= fim:
        yield atual
        atual += timedelta(days=1)


def lista_de_dias(inicio: date, fim: date) -> List[date]:
    """Versão em lista de :func:`dias_entre`."""
    return list(dias_entre(inicio, fim))
