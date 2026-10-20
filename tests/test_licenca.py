"""A divisão de licenças (ADR-0027, LICENSING.md, CONTRIBUTING.md › Licença).

A plataforma web é AGPL-3.0-only e o resto é MIT. Uma troca de ficheiro, um
`package.json` sem a licença ou um texto da AGPL alterado passam despercebidos
numa revisão; aqui falham.
"""

import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# sha256 do texto da AGPL-3.0-only do spdx/license-list-data (31ba1a5, 2026-09-16).
AGPL_SHA256 = "d8a6cc31abc16b6748c7a21f21611f5a1ec33f67d22ca23d7da1c19b95496bee"


def test_a_plataforma_web_e_agpl_com_o_texto_oficial():
    for caminho in (RAIZ / "web" / "LICENSE", RAIZ / "supabase" / "LICENSE"):
        # No Windows o git pode escrever o ficheiro com CRLF: o que se compara é o texto.
        dados = caminho.read_bytes().replace(b"\r\n", b"\n")
        assert dados.startswith(b"GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3"), caminho
        assert hashlib.sha256(dados).hexdigest() == AGPL_SHA256, f"{caminho} não é o texto oficial"


def test_o_package_json_da_web_declara_a_licenca():
    pacote = json.loads((RAIZ / "web" / "package.json").read_text(encoding="utf-8"))
    assert pacote.get("license") == "AGPL-3.0-only"


def test_o_resto_continua_mit():
    assert (RAIZ / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")


def test_licensing_e_contributing_dizem_a_mesma_divisao():
    licensing = (RAIZ / "LICENSING.md").read_text(encoding="utf-8")
    contributing = (RAIZ / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for texto in (licensing, contributing):
        assert "AGPL-3.0-only" in texto and "MIT" in texto
    assert "relicenciar" in contributing, "sem a concessão, o licenciamento duplo deixa de ser possível"
