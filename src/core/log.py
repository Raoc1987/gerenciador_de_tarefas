"""Configuração central de logging da aplicação."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from core.paths import diretorio_logs

_configurado = False


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura o logger raiz (arquivo rotativo + console). Idempotente."""
    global _configurado
    logger = logging.getLogger()
    if _configurado:
        return logger

    logger.setLevel(nivel)
    formato = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        arquivo = RotatingFileHandler(
            diretorio_logs() / "app.log",
            maxBytes=512 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        arquivo.setFormatter(formato)
        logger.addHandler(arquivo)
    except OSError:
        # Sem permissão de escrita: a aplicação continua, apenas sem log em arquivo.
        pass

    if sys.stderr is not None:
        consola = logging.StreamHandler(sys.stderr)
        consola.setFormatter(formato)
        logger.addHandler(consola)

    _configurado = True
    return logger


def obter_logger(nome: str) -> logging.Logger:
    """Logger nomeado para um módulo ou plugin."""
    return logging.getLogger(nome)
