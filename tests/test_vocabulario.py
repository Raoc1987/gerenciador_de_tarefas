"""O mesmo vocabulário em dois sítios: os enums do Postgres e as listas da web.

Regra R8 do ``docs/METODO.md`` (vinda do M5 do ALKMIA): uma lista que vive em
TypeScript e num ``create type ... as enum`` diverge em silêncio. A base recusa
o valor novo que a web manda, ou a web nunca mostra o que a base aceita. Este
teste compara-as.

Nos papéis a ORDEM também é regra: a base compara com ``>=`` pela ordem do enum
(``tem_papel``) e a web pela posição em ``PAPEIS`` (``pode``). Trocar a ordem num
só lado dava permissões diferentes nos dois.
"""

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MIGRACOES = RAIZ / "supabase" / "migrations"
WEB = RAIZ / "web"


def _enums_sql() -> dict[str, list[str]]:
    """Os enums no estado final: ``create type`` mais cada ``alter type ... add value``."""
    enums: dict[str, list[str]] = {}
    for f in sorted(MIGRACOES.glob("*.sql")):
        texto = re.sub(r"--[^\n]*", "", f.read_text(encoding="utf-8"))
        for nome, corpo in re.findall(r"create type public\.(\w+) as enum\s*\(([^)]*)\)", texto, re.I):
            enums[nome] = re.findall(r"'([^']+)'", corpo)
        for nome, valor, antes, depois in re.findall(
            r"alter type public\.(\w+) add value(?: if not exists)? '([^']+)'(?: before '([^']+)')?(?: after '([^']+)')?",
            texto, re.I,
        ):
            lista = enums.setdefault(nome, [])
            if antes:
                lista.insert(lista.index(antes), valor)
            elif depois:
                lista.insert(lista.index(depois) + 1, valor)
            else:
                lista.append(valor)
    return enums


def _lista_ts(ficheiro: str, constante: str) -> list[str]:
    texto = (WEB / ficheiro).read_text(encoding="utf-8")
    m = re.search(rf"export const {constante}\s*=\s*\[(.*?)\]", texto, re.S)
    assert m, f"{ficheiro}: não encontrei {constante}"
    return re.findall(r'"([^"]+)"', m.group(1))


def _uniao_ts(ficheiro: str, tipo: str) -> list[str]:
    texto = (WEB / ficheiro).read_text(encoding="utf-8")
    m = re.search(rf"export type {tipo}\s*=\s*([^;]+);", texto)
    assert m, f"{ficheiro}: não encontrei o tipo {tipo}"
    return re.findall(r'"([^"]+)"', m.group(1))


PARES = [
    ("papel", lambda: _lista_ts("lib/dominio/papeis.ts", "PAPEIS")),
    ("estado_tarefa", lambda: _lista_ts("lib/dominio/tarefas.ts", "ESTADOS")),
    ("prioridade", lambda: _lista_ts("lib/dominio/tarefas.ts", "PRIORIDADES")),
    ("tipo_dependencia", lambda: _lista_ts("lib/dominio/ligacoes.ts", "TIPOS_DEPENDENCIA")),
    ("plano", lambda: _uniao_ts("lib/faturacao/stripe.ts", "Plano")),
]


@pytest.mark.parametrize("enum, ler_web", PARES, ids=[p[0] for p in PARES])
def test_o_enum_da_base_e_a_lista_da_web_sao_iguais_e_pela_mesma_ordem(enum, ler_web):
    sql = _enums_sql()
    assert enum in sql, f"o enum public.{enum} desapareceu das migrações"
    assert ler_web() == sql[enum], (
        f"public.{enum} na base é {sql[enum]} e na web é {ler_web()}: "
        "acrescente o valor nos dois sítios, pela mesma ordem"
    )


def test_os_planos_pagos_sao_os_planos_menos_o_gratuito():
    pagos = _lista_ts("lib/faturacao/stripe.ts", "PLANOS_PAGOS")
    assert pagos == [p for p in _enums_sql()["plano"] if p != "gratuito"]


def test_o_leitor_de_alter_type_respeita_before_e_after(tmp_path, monkeypatch):
    """O próprio instrumento (R6): sem isto, um ``add value ... before`` lia-se mal e calado."""
    (tmp_path / "1.sql").write_text("create type public.x as enum ('a', 'c');", encoding="utf-8")
    (tmp_path / "2.sql").write_text(
        "alter type public.x add value 'b' before 'c';\nalter type public.x add value if not exists 'd';",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "MIGRACOES", tmp_path)
    assert _enums_sql()["x"] == ["a", "b", "c", "d"]
