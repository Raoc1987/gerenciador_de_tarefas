"""Utilitários gerais da interface e de formatação."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def formatar_data(data_str):
    """Converte ``"AAAA-MM-DD"`` em ``"DD/MM/AAAA"``."""
    if not data_str:
        return ""
    partes = data_str.split('-')
    return f"{partes[2]}/{partes[1]}/{partes[0]}"


def data_hoje_iso() -> str:
    """Data de hoje em ``AAAA-MM-DD``."""
    return date.today().isoformat()


def validar_data_iso(data_str: Optional[str]) -> bool:
    """``True`` se ``data_str`` for vazia ou uma data ``AAAA-MM-DD`` válida."""
    if not data_str:
        return True
    try:
        datetime.strptime(data_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def atualizar_relógio(label, formato: str = "%d/%m/%Y %H:%M:%S") -> None:
    """Mantém ``label`` a mostrar a hora corrente, atualizando a cada segundo.

    O agendamento é cancelado quando o widget é destruído: um temporizador
    pendente de uma janela já fechada dispararia mais tarde contra um
    interpretador Tk inexistente.
    """

    def cancelar(_evento=None) -> None:
        identificador = getattr(label, "_agendamento_relogio", None)
        if identificador:
            label._agendamento_relogio = None
            try:
                label.after_cancel(identificador)
            except Exception:
                pass

    def tique() -> None:
        try:
            label.config(text=datetime.now().strftime(formato))
            label._agendamento_relogio = label.after(1000, tique)
        except Exception:
            # Widget destruído — nada a fazer.
            return

    try:
        label.bind("<Destroy>", cancelar, add="+")
    except Exception:
        pass
    tique()


# Alias sem acento, conveniente para código novo.
atualizar_relogio = atualizar_relógio
