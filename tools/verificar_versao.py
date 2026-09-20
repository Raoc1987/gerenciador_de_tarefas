"""Confere que a etiqueta de uma release diz o mesmo que ``core/version.py``.

Existe porque a alternativa silenciosa é pior do que um erro: marcar `v1.0.1`
com o código ainda em `1.0.0` publica um instalador chamado 1.0.1 que instala
uma aplicação que se diz 1.0.0. Fica nos atalhos, no "Adicionar ou remover
programas" e no que a pessoa vê no ecrã do Sobre — três sítios a discordar do
nome do ficheiro que ela descarregou.

**A versão continua a ser de ``core/version.py``**, que o inventário do Core
descreve como "fonte única lida pela app, pelo PyInstaller e pelo Inno Setup;
duplicá-la é garantir que divergem". A etiqueta não define a versão: **confirma-a**.
Deixar a etiqueta mandar faria dela uma segunda fonte, que é o que isto evita.

Uso::

    python tools/verificar_versao.py v1.0.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from core.version import APP_VERSION  # noqa: E402


def normalizar(etiqueta: str) -> str:
    """Tira o ``v`` da frente. ``v1.0.1`` e ``1.0.1`` são a mesma versão."""
    etiqueta = (etiqueta or "").strip()
    return etiqueta[1:] if etiqueta[:1].lower() == "v" else etiqueta


def conferir(etiqueta: str, versao: str = APP_VERSION) -> str:
    """Devolve a versão confirmada, ou explica porque não bate certo.

    Raises:
        ValueError: etiqueta vazia ou diferente da versão do código. A
            mensagem diz **as duas**, porque quem a lê está a meio de uma
            publicação e precisa de saber qual delas mudar.
    """
    limpa = normalizar(etiqueta)
    if not limpa:
        raise ValueError("Não veio etiqueta nenhuma para conferir.")
    if limpa != versao:
        raise ValueError(
            f"A etiqueta diz {limpa!r} e o código diz {versao!r}.\n"
            f"Corrija APP_VERSION em src/core/version.py, ou marque a etiqueta "
            f"certa. A versão é do código; a etiqueta só a confirma."
        )
    return limpa


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Confere que a etiqueta bate certo com core/version.py."
    )
    analisador.add_argument("etiqueta", help="a etiqueta da release, ex.: v1.0.1")
    opcoes = analisador.parse_args(argumentos)

    try:
        versao = conferir(opcoes.etiqueta)
    except ValueError as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    print(f"Etiqueta e código concordam: {versao}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
