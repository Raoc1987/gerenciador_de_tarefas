# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para o Gerenciador de Tarefas.

Gera ``dist/GerenciadorDeTarefas/GerenciadorDeTarefas.exe`` (modo *onedir*:
arranca mais depressa que *onefile* e é o que o instalador Inno Setup copia).

Construir::

    python tools/build.py          # recomendado: valida o .exe no fim
    pyinstaller GerenciadorDeTarefas.spec --noconfirm

Nome, versão e ícone vêm de ``core/version.py`` — não são repetidos aqui.
"""

import sys
from pathlib import Path

RAIZ = Path(SPECPATH).resolve()
SRC = RAIZ / "src"

sys.path.insert(0, str(SRC))
from core.version import APP_ID, APP_VERSION  # noqa: E402

ICONE = RAIZ / "assets" / "icon.ico"
ARQUIVO_VERSAO = RAIZ / "build" / "file_version_info.txt"

# Recursos que a aplicação lê em tempo de execução. Os caminhos de destino
# correspondem ao que core.paths espera relativamente a sys._MEIPASS.
datas = [
    (str(RAIZ / "assets" / "idiomas"), "assets/idiomas"),
    (str(ICONE), "assets"),
    (str(RAIZ / "plugins" / "available"), "plugins/available"),
]

# Os plugins são módulos .py carregados em tempo de execução: o PyInstaller não
# lhes segue os imports, por isso nada do que eles usam é detetado sozinho.
#
# Esta lista é a "superfície de SDK" disponível aos plugins — módulos da
# aplicação que um plugin pode importar, mais módulos da biblioteca padrão de
# uso provável. Sem isto, um plugin que importe calendar_widget falha apenas
# na versão empacotada (foi assim que este caso apareceu: o plugin Calendar
# Integration usa CalendarioWidget, que mais nenhum módulo importa).
hiddenimports = [
    # módulos da aplicação que os plugins podem usar
    "calendar_widget",
    "core.plugin_api",
    "language_manager",
    "utils",
    # biblioteca padrão
    "calendar",
    "csv",
    "datetime",
    "json",
    "sqlite3",
    "textwrap",
    "tkinter.colorchooser",
    "tkinter.filedialog",
    "tkinter.font",
    "tkinter.messagebox",
    "tkinter.scrolledtext",
    "tkinter.simpledialog",
    "urllib.request",
    "webbrowser",
    "zipfile",
]

analise = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "PIL", "numpy", "pandas", "setuptools"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analise.pure)

exe = EXE(
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name=APP_ID,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # aplicação gráfica: sem janela de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICONE) if ICONE.exists() else None,
    version=str(ARQUIVO_VERSAO) if ARQUIVO_VERSAO.exists() else None,
)

col = COLLECT(
    exe,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_ID,
)
