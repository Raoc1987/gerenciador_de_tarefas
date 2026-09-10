"""Ponto de entrada do Gerenciador de Tarefas."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Permite executar tanto `python src/main.py` como o executável empacotado.
_DIRETORIO_SRC = Path(__file__).resolve().parent
if str(_DIRETORIO_SRC) not in sys.path:
    sys.path.insert(0, str(_DIRETORIO_SRC))

from core.log import configurar_logging, obter_logger  # noqa: E402
from core.version import APP_NAME, APP_VERSION  # noqa: E402


def main() -> int:
    """Inicializa os serviços e abre a interface. Devolve o código de saída."""
    configurar_logging()
    logger = obter_logger("main")
    logger.info("%s %s a iniciar (pid=%s)", APP_NAME, APP_VERSION, os.getpid())

    try:
        from gui import iniciar_interface

        iniciar_interface()
    except Exception:
        logger.exception("Falha fatal na aplicação.")
        return 1

    logger.info("Aplicação encerrada normalmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
