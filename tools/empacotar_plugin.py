"""Empacota uma pasta de plugin num ``.zip`` instalável.

Uso::

    python tools/empacotar_plugin.py plugins/available/calendar
    python tools/empacotar_plugin.py plugins/available/calendar --saida dist/plugins

O arquivo gerado chama-se ``<id>-<versao>.zip`` e contém uma única pasta de
topo com o id do plugin — exatamente o formato que o Plugin Manager espera.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA_PADRAO = RAIZ / "dist" / "plugins"

#: Nomes que nunca entram no pacote.
IGNORADOS = {"__pycache__", ".git", ".pytest_cache", ".DS_Store"}


def empacotar(pasta: Path, saida: Path = SAIDA_PADRAO) -> Path:
    """Cria o ``.zip`` do plugin em ``pasta`` e devolve o caminho gerado."""
    pasta = Path(pasta).resolve()
    manifesto_caminho = pasta / "plugin.json"
    if not manifesto_caminho.is_file():
        raise SystemExit(f"Não encontrei plugin.json em {pasta}")

    manifesto = json.loads(manifesto_caminho.read_text(encoding="utf-8"))
    plugin_id = manifesto["id"]
    versao = manifesto["version"]

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"{plugin_id}-{versao}.zip"

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        for arquivo in sorted(pasta.rglob("*")):
            if any(parte in IGNORADOS for parte in arquivo.relative_to(pasta).parts):
                continue
            if arquivo.is_file():
                interno = Path(plugin_id) / arquivo.relative_to(pasta)
                pacote.write(arquivo, interno.as_posix())

    return destino


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("pasta", help="pasta do plugin (a que contém plugin.json)")
    analisador.add_argument(
        "--saida", default=str(SAIDA_PADRAO), help="pasta onde gravar o .zip"
    )
    opcoes = analisador.parse_args(argumentos)

    destino = empacotar(Path(opcoes.pasta), Path(opcoes.saida))
    tamanho = destino.stat().st_size
    print(f"Pacote gerado: {destino} ({tamanho} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
