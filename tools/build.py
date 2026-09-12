"""Gera o executável Windows e valida-o de verdade.

Passos::

    1. escreve build/file_version_info.txt a partir de core/version.py
    2. corre o PyInstaller com GerenciadorDeTarefas.spec
    3. executa o .exe gerado com --version e --autoteste, num diretório de
       dados descartável, e só considera o build concluído se o autoteste
       passar

Uso::

    python tools/build.py
    python tools/build.py --sem-teste     # apenas empacota
    python tools/build.py --limpar        # apaga build/ e dist/ antes
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
SPEC = RAIZ / "GerenciadorDeTarefas.spec"

sys.path.insert(0, str(SRC))

from core.version import (  # noqa: E402
    APP_ID,
    APP_NAME,
    APP_PUBLISHER,
    APP_VERSION,
    parse_version,
)

MODELO_VERSAO = """# Gerado por tools/build.py — não editar à mão.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({maior}, {menor}, {correcao}, 0),
    prodvers=({maior}, {menor}, {correcao}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{publisher}'),
         StringStruct('FileDescription', '{nome}'),
         StringStruct('FileVersion', '{versao}'),
         StringStruct('InternalName', '{app_id}'),
         StringStruct('LegalCopyright', '{publisher}'),
         StringStruct('OriginalFilename', '{app_id}.exe'),
         StringStruct('ProductName', '{nome}'),
         StringStruct('ProductVersion', '{versao}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def escrever_info_de_versao() -> Path:
    """Cria o recurso de versão do Windows a partir de ``core/version.py``."""
    maior, menor, correcao = parse_version(APP_VERSION)
    destino = RAIZ / "build" / "file_version_info.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        MODELO_VERSAO.format(
            maior=maior,
            menor=menor,
            correcao=correcao,
            versao=APP_VERSION,
            nome=APP_NAME,
            app_id=APP_ID,
            publisher=APP_PUBLISHER,
        ),
        encoding="utf-8",
    )
    return destino


def empacotar() -> Path:
    """Corre o PyInstaller e devolve a pasta gerada em ``dist/``."""
    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--distpath",
        str(RAIZ / "dist"),
        "--workpath",
        str(RAIZ / "build"),
    ]
    print("$", " ".join(comando))
    subprocess.run(comando, cwd=RAIZ, check=True)

    pasta = RAIZ / "dist" / APP_ID
    executavel = pasta / f"{APP_ID}.exe"
    if not executavel.is_file():
        raise SystemExit(f"O PyInstaller terminou mas {executavel} não existe.")
    return pasta


def _decodificar(dados: bytes) -> str:
    """Descodifica a saída do processo filho, que pode não vir em UTF-8."""
    for codificacao in ("utf-8", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("utf-8", errors="replace")


def validar(pasta: Path) -> None:
    """Executa o ``.exe`` gerado e falha se o autoteste não passar.

    O executável é gráfico (sem consola), por isso o relatório do autoteste é
    lido de um arquivo em vez de depender do stdout.
    """
    executavel = pasta / f"{APP_ID}.exe"
    ambiente = dict(os.environ)
    dados = Path(tempfile.mkdtemp(prefix="gdt_build_"))
    ambiente["GDT_DATA_DIR"] = str(dados)
    relatorio = dados / "autoteste.txt"

    try:
        versao = subprocess.run(
            [str(executavel), "--version"],
            capture_output=True,
            env=ambiente,
            timeout=120,
        )
        saida = _decodificar(versao.stdout or b"").strip()
        print(f"--version -> {saida!r} (codigo {versao.returncode})")
        if versao.returncode != 0:
            raise SystemExit("O executável não respondeu corretamente a --version.")

        autoteste = subprocess.run(
            [str(executavel), "--autoteste", "--relatorio", str(relatorio)],
            capture_output=True,
            env=ambiente,
            timeout=300,
        )
        if relatorio.is_file():
            print(relatorio.read_text(encoding="utf-8"))
        else:
            print(_decodificar(autoteste.stdout or b""))
            print(_decodificar(autoteste.stderr or b"")[-2000:])
            raise SystemExit("O autoteste não produziu relatório.")
        if autoteste.returncode != 0:
            raise SystemExit("O autoteste do executável falhou.")
    finally:
        shutil.rmtree(dados, ignore_errors=True)


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description="Empacota a aplicação para Windows.")
    analisador.add_argument("--sem-teste", action="store_true", help="não valida o .exe")
    analisador.add_argument("--limpar", action="store_true", help="apaga build/ e dist/")
    opcoes = analisador.parse_args(argumentos)

    if opcoes.limpar:
        for pasta in (RAIZ / "build", RAIZ / "dist" / APP_ID):
            shutil.rmtree(pasta, ignore_errors=True)
            print(f"Removido: {pasta}")

    caminho_versao = escrever_info_de_versao()
    print(f"Recurso de versão: {caminho_versao}")

    pasta = empacotar()
    tamanho = sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file())
    print(f"\nBuild em {pasta} ({tamanho / (1024 * 1024):.1f} MiB)")

    if not opcoes.sem_teste:
        validar(pasta)
        print("Executável validado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
