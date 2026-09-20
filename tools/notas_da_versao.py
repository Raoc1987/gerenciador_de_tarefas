"""Tira do CHANGELOG.md a secção de uma versão, para a página de download.

As notas de uma release vivem no repositório e são revistas como tudo o
resto — não escritas à pressa na caixa do GitHub no momento de publicar. Uma
versão sem secção no changelog sai só com a lista que o GitHub gera sozinho,
que é pouco mas não é errado.

Uso::

    python tools/notas_da_versao.py v1.1.0 --para notas.md

**Escreve sempre em UTF-8, explicitamente.** A primeira versao imprimia para o
ecra e rebentava numa consola cp1252 na primeira seta que aparecesse no texto
-- num runner Windows isso e uma release que falha depois de tudo construido,
por causa de um caractere nas notas.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CHANGELOG = RAIZ / "CHANGELOG.md"


def normalizar(etiqueta: str) -> str:
    etiqueta = (etiqueta or "").strip()
    return etiqueta[1:] if etiqueta[:1].lower() == "v" else etiqueta


def extrair(versao: str, texto: str) -> str:
    """O corpo da secção desta versão, sem o cabeçalho. ``""`` se não houver.

    O formato é o do *Keep a Changelog* que o ficheiro já usava:
    ``## [1.1.0] - 2026-09-20``. A secção acaba no ``##`` seguinte.
    """
    versao = normalizar(versao)
    linhas = texto.splitlines()
    inicio = None
    for numero, linha in enumerate(linhas):
        if re.match(rf"^## \[{re.escape(versao)}\]", linha):
            inicio = numero + 1
            break
    if inicio is None:
        return ""

    fim = len(linhas)
    for numero in range(inicio, len(linhas)):
        if linhas[numero].startswith("## "):
            fim = numero
            break
    return "\n".join(linhas[inicio:fim]).strip()


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description="Notas de uma versão.")
    analisador.add_argument("etiqueta", help="a etiqueta, ex.: v1.1.0")
    analisador.add_argument(
        "--para", help="ficheiro a escrever (UTF-8); sem isto, escreve no ecrã"
    )
    opcoes = analisador.parse_args(argumentos)

    texto = ""
    if CHANGELOG.is_file():
        texto = extrair(opcoes.etiqueta, CHANGELOG.read_text(encoding="utf-8"))

    if opcoes.para:
        Path(opcoes.para).write_text(texto, encoding="utf-8")
        print(f"{len(texto.splitlines())} linha(s) para {opcoes.para}")
        return 0

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # pragma: no cover - consola estranha
        pass
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
