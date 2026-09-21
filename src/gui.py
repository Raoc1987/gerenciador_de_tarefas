"""Ponto de compatibilidade para quem ainda importa iniciar_interface."""

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import TaskManagerApp


def iniciar_interface() -> None:
    TaskManagerApp().run()
