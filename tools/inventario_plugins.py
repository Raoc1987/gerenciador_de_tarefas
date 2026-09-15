"""Reescreve o inventário dos plugins que acompanham a aplicação.

Uso::

    python tools/inventario_plugins.py

O inventário vive em ``docs/architecture/plugins-embutidos.json`` e guarda,
por plugin, a versão declarada e a impressão digital do seu conteúdo. O teste
de arquitetura falha quando o conteúdo de um plugin muda sem a versão subir —
que é exatamente o que torna a correção invisível para quem já tem o plugin
instalado (ADR-0006).

Depois de alterar um plugin embutido: suba-lhe a versão em ``plugin.json`` e
corra este comando.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

EMBUTIDOS = RAIZ / "plugins" / "available"
INVENTARIO = RAIZ / "docs" / "architecture" / "plugins-embutidos.json"

LEIA_ME = (
    "Inventário dos plugins que acompanham a aplicação (ver ADR-0006). A "
    "impressão é do conteúdo da pasta; a versão é a que o manifesto declara. "
    "tests/test_arquitetura.py falha quando a impressão muda e a versão não: "
    "um plugin embutido só chega a quem já o tem instalado se a versão subir, "
    "por isso corrigi-lo sem a subir é publicar uma correção que nunca sai do "
    "repositório. Regenerar com: python tools/inventario_plugins.py"
)


def levantar() -> dict:
    """Lê as pastas dos plugins embutidos e devolve o inventário atual."""
    from core.plugin_package import impressao_da_pasta

    plugins = {}
    for pasta in sorted(p for p in EMBUTIDOS.iterdir() if p.is_dir()):
        manifesto_caminho = pasta / "plugin.json"
        if not manifesto_caminho.is_file():
            continue
        manifesto = json.loads(manifesto_caminho.read_text(encoding="utf-8"))
        plugins[manifesto["id"]] = {
            "versao": manifesto["version"],
            "impressao": impressao_da_pasta(pasta),
        }
    return {"_leia_me": LEIA_ME, "plugins": plugins}


def main() -> int:
    """Ponto de entrada da linha de comandos."""
    inventario = levantar()
    INVENTARIO.write_text(
        json.dumps(inventario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Inventário escrito: {INVENTARIO}")
    for plugin_id, dados in inventario["plugins"].items():
        print(f"  {plugin_id} v{dados['versao']}  {dados['impressao'][:12]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
