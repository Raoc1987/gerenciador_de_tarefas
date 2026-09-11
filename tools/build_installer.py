"""Compila o instalador Windows a partir de ``installer/setup.iss``.

Requer o **Inno Setup 6** instalado (``ISCC.exe``). O caminho é procurado nos
locais habituais, na variável ``ISCC`` e no ``PATH``.

Uso::

    python tools/build.py              # primeiro: gera dist/GerenciadorDeTarefas
    python tools/build_installer.py    # depois: gera o Setup.exe

A versão vem de ``core/version.py`` e é passada ao compilador, para que o
instalador nunca fique com uma versão diferente da do executável.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
SCRIPT_ISS = RAIZ / "installer" / "setup.iss"
SAIDA = RAIZ / "installer" / "Output"

sys.path.insert(0, str(SRC))

from core.version import (  # noqa: E402
    APP_ID,
    APP_NAME,
    APP_PUBLISHER,
    APP_URL,
    APP_VERSION,
)

CAMINHOS_ISCC = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
]


def localizar_iscc() -> Path | None:
    """Procura o compilador do Inno Setup; ``None`` se não estiver instalado."""
    do_ambiente = os.environ.get("ISCC")
    if do_ambiente and Path(do_ambiente).is_file():
        return Path(do_ambiente)

    no_path = shutil.which("ISCC")
    if no_path:
        return Path(no_path)

    for caminho in CAMINHOS_ISCC:
        if Path(caminho).is_file():
            return Path(caminho)
    return None


def verificar_build() -> Path:
    """Confirma que o executável empacotado existe antes de criar o instalador."""
    pasta = RAIZ / "dist" / APP_ID
    executavel = pasta / f"{APP_ID}.exe"
    if not executavel.is_file():
        raise SystemExit(
            f"{executavel} não existe.\nCorra primeiro: python tools/build.py"
        )
    return pasta


def compilar(iscc: Path) -> Path:
    """Corre o ISCC e devolve o caminho do instalador gerado."""
    SAIDA.mkdir(parents=True, exist_ok=True)
    comando = [
        str(iscc),
        f"/DAppVersion={APP_VERSION}",
        f"/DAppName={APP_NAME}",
        f"/DAppId={APP_ID}",
        f"/DAppPublisher={APP_PUBLISHER}",
        f"/DAppUrl={APP_URL}",
        str(SCRIPT_ISS),
    ]
    print("$", " ".join(comando))
    subprocess.run(comando, cwd=SCRIPT_ISS.parent, check=True)

    instalador = SAIDA / f"{APP_ID}-Setup.exe"
    if not instalador.is_file():
        raise SystemExit(f"O ISCC terminou mas {instalador} não existe.")
    return instalador


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description="Compila o instalador Windows.")
    analisador.add_argument(
        "--verificar",
        action="store_true",
        help="apenas confirma se o Inno Setup está disponível",
    )
    opcoes = analisador.parse_args(argumentos)

    iscc = localizar_iscc()
    if opcoes.verificar:
        print(f"ISCC: {iscc}" if iscc else "Inno Setup 6 não encontrado.")
        return 0 if iscc else 1

    if iscc is None:
        raise SystemExit(
            "Inno Setup 6 não encontrado.\n"
            "Instale de https://jrsoftware.org/isdl.php "
            "(ou `winget install JRSoftware.InnoSetup`) e volte a correr.\n"
            "Se estiver noutro local, aponte a variável ISCC para o ISCC.exe."
        )

    verificar_build()
    instalador = compilar(iscc)
    tamanho = instalador.stat().st_size / (1024 * 1024)
    print(f"\nInstalador gerado: {instalador} ({tamanho:.1f} MiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
