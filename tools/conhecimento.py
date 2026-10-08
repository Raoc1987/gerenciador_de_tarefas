"""Analisa o catálogo de práticas partilhadas entre o Gerenciador de Tarefas e o ALKMIA.

    python tools/conhecimento.py validar
    python tools/conhecimento.py relatorio
    python tools/conhecimento.py triagem --alkmia /caminho/para/ALKMIA
    python tools/conhecimento.py alkmia [--escrever]

O catálogo (``docs/conhecimento/catalogo.json``) regista cada prática, regra,
agente, skill, hook ou prompt dos dois projetos, com os mesmos critérios e a
decisão tomada aqui. Os dois produtos são distintos: o critério que separa o
que serve aos dois do que é de um só é ``independente_do_dominio``.

``triagem`` lê o outro repositório e nunca escreve nele (o ``CLAUDE.md`` proíbe
alterar o ALKMIA). Só abre ficheiros para leitura e recusa um caminho que seja
este repositório.

Só biblioteca padrão, como o resto de ``tools/``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "docs" / "conhecimento" / "catalogo.json"

# ----------------------------------------------------------------- parâmetros
#
# Os parâmetros de decisão vivem aqui e só aqui; o METODO e o teste apontam
# para estes nomes.

TIPOS = {"regra", "protocolo", "prompt", "agente", "skill", "hook", "ferramenta", "pratica"}
ORIGENS = {"alkmia", "gdt", "ambos"}
DECISOES = {"adotado", "adaptado", "fundido", "recusado", "por_decidir"}
GUARDAS = {"teste", "ci", "hook", "agente", "skill", "prosa"}
CUSTOS = {"baixo", "medio", "alto"}
CRITERIOS = {
    "independente_do_dominio": bool,  # serve aos dois produtos, não só a um
    "nasceu_de_incidente": bool,  # há uma cicatriz real, num dos dois
    "guardavel_por_procedimento": bool,  # pode virar teste, hook, CI ou agente
    "duplica": (str, type(None)),  # o que já faz o mesmo aqui
    "custo": str,  # de manter, não de escrever
}
#: Guardas que são procedimento (correm sozinhas); "prosa" e "skill" dependem de alguém ler.
PROCEDIMENTO = {"teste", "ci", "hook", "agente"}
TRAZIDOS = {"adotado", "adaptado"}
#: Estado no ALKMIA de uma prática nascida aqui, medido lá (só leitura).
ESTADOS_LA = {"falta", "parcial", "existe", "nao_se_aplica", "por_medir"}
NOTA_ALKMIA = RAIZ / "docs" / "conhecimento" / "PARA-O-ALKMIA.md"


def carregar(caminho: Path = CATALOGO) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _existe(caminho: str | None, raiz: Path) -> bool:
    return bool(caminho) and (raiz / caminho.split("#", 1)[0]).exists()


def problemas(cat: dict, raiz: Path = RAIZ) -> list[str]:
    """Erros que invalidam o catálogo. Lista vazia = válido."""
    erros: list[str] = []
    vistos: set[str] = set()
    for i, e in enumerate(cat.get("entradas", [])):
        eid = e.get("id") or f"#{i}"
        if eid in vistos:
            erros.append(f"{eid}: id repetido")
        vistos.add(eid)
        for campo, valores in (("tipo", TIPOS), ("origem", ORIGENS), ("decisao", DECISOES)):
            if e.get(campo) not in valores:
                erros.append(f"{eid}: {campo} {e.get(campo)!r} fora de {sorted(valores)}")
        if not str(e.get("razao", "")).strip():
            erros.append(f"{eid}: sem razão (uma decisão sem porquê não foi pensada)")
        crit = e.get("criterios", {})
        for nome, tipo in CRITERIOS.items():
            if not isinstance(crit.get(nome, ...), tipo):
                erros.append(f"{eid}: critério {nome} em falta ou com o tipo errado")
        if crit.get("custo") not in CUSTOS:
            erros.append(f"{eid}: custo {crit.get('custo')!r} fora de {sorted(CUSTOS)}")
        if e.get("origem") in {"alkmia", "ambos"} and not e.get("fontes"):
            erros.append(f"{eid}: vem do ALKMIA e não diz de onde (fontes)")

        decisao = e.get("decisao")
        # As regras de decisão: os parâmetros têm consequência.
        if not crit.get("independente_do_dominio") and decisao in TRAZIDOS:
            erros.append(f"{eid}: depende do domínio de um produto e foi trazido ({decisao})")
        if crit.get("duplica") and decisao in TRAZIDOS:
            erros.append(f"{eid}: duplica {crit['duplica']} e foi trazido; funde-se ou recusa-se")
        if decisao == "fundido" and not crit.get("duplica"):
            erros.append(f"{eid}: fundido sem dizer em quê (criterios.duplica)")
        if decisao == "por_decidir" and not e.get("proximo_passo"):
            erros.append(f"{eid}: por decidir sem próximo passo")
        if decisao in TRAZIDOS | {"fundido"} and not _existe(e.get("destino"), raiz):
            erros.append(f"{eid}: o destino {e.get('destino')!r} não existe aqui")
        if decisao in TRAZIDOS:
            g = e.get("guarda") or {}
            if g.get("tipo") not in GUARDAS:
                erros.append(f"{eid}: trazido sem guarda (tipo {g.get('tipo')!r})")
            elif not _existe(g.get("caminho"), raiz):
                erros.append(f"{eid}: a guarda {g.get('caminho')!r} não existe")
        la = e.get("para_alkmia")
        if la is not None:
            if e.get("origem") == "alkmia":
                erros.append(f"{eid}: para_alkmia só faz sentido no que nasceu aqui")
            if la.get("estado_la") not in ESTADOS_LA:
                erros.append(f"{eid}: estado_la {la.get('estado_la')!r} fora de {sorted(ESTADOS_LA)}")
            if not str(la.get("medido", "")).strip() or not str(la.get("como_aplicar", "")).strip():
                erros.append(f"{eid}: para_alkmia sem a medição ou sem como aplicar")
    return erros


def inventario_local(raiz: Path = RAIZ) -> set[str]:
    """O que o Claude Code carrega deste repositório: skills, agentes e hooks."""
    c = raiz / ".claude"
    itens = {f".claude/skills/{p.name}/SKILL.md" for p in (c / "skills").iterdir() if p.is_dir()} if (c / "skills").is_dir() else set()
    if (c / "agents").is_dir():
        itens |= {f".claude/agents/{p.name}" for p in (c / "agents").glob("*.md")}
    if (c / "hooks").is_dir():
        itens |= {f".claude/hooks/{p.name}" for p in (c / "hooks").glob("*.mjs")}
    return itens


def nao_catalogados(cat: dict, raiz: Path = RAIZ) -> list[str]:
    """Skills, agentes e hooks que existem aqui e o catálogo não conhece."""
    destinos = {e.get("destino") for e in cat["entradas"] if e.get("decisao") in TRAZIDOS}
    return sorted(inventario_local(raiz) - destinos)


# ------------------------------------------------------------------ relatório

def relatorio(cat: dict) -> str:
    ents = cat["entradas"]
    trazidos = [e for e in ents if e["decisao"] in TRAZIDOS]
    por_proc = [e for e in trazidos if e["guarda"]["tipo"] in PROCEDIMENTO]
    so_prosa = [e for e in trazidos if e["guarda"]["tipo"] == "prosa" and e["criterios"]["guardavel_por_procedimento"]]
    linhas = [
        f"Catálogo de {cat['atualizado']}: {len(ents)} entradas",
        "",
        "Por decisão:  " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(e['decisao'] for e in ents).items())),
        "Por origem:   " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(e['origem'] for e in ents).items())),
        "",
        f"Do ALKMIA, trazido: {sum(e['origem'] == 'alkmia' and e['decisao'] in TRAZIDOS for e in ents)}"
        f" de {sum(e['origem'] == 'alkmia' for e in ents)}"
        f" (recusados por serem do domínio: {sum(e['origem'] == 'alkmia' and not e['criterios']['independente_do_dominio'] for e in ents)})",
        f"Guardado por procedimento (teste, CI, hook, agente): {len(por_proc)} de {len(trazidos)} trazidos"
        f" ({round(100 * len(por_proc) / len(trazidos)) if trazidos else 0}%)",
        "",
        "Só em prosa, mas dava para guardar por procedimento (R8):",
        *([f"  - {e['id']}: {e['titulo']}" for e in so_prosa] or ["  nenhum"]),
        "",
        "Dívidas registadas:",
        *([f"  - {e['id']}: {e['divida']}" for e in ents if e.get("divida")] or ["  nenhuma"]),
        "",
        "Por decidir, com o próximo passo:",
        *([f"  - {e['id']}: {e['proximo_passo']}" for e in ents if e["decisao"] == "por_decidir"] or ["  nada"]),
        "",
        "Nascido aqui e útil ao ALKMIA (informativo; o ALKMIA não se altera daqui):",
        *[f"  - {e['id']}: {e['titulo']}" for e in ents if e["origem"] == "gdt" and e["tipo"] == "pratica"],
    ]
    return "\n".join(linhas)


# ------------------------------------------------------- nota para o ALKMIA

ORDEM_LA = ["falta", "parcial", "por_medir", "existe", "nao_se_aplica"]
TITULO_LA = {
    "falta": "Falta lá, e serve",
    "parcial": "Existe em parte",
    "por_medir": "Por medir antes de decidir",
    "existe": "Já existe lá: nada a fazer",
    "nao_se_aplica": "Não se aplica hoje: só se a situação aparecer",
}


def nota_alkmia(cat: dict) -> str:
    """O que nasceu aqui e pode servir ao ALKMIA, gerado do catálogo. Não se edita à mão."""
    com = [e for e in cat["entradas"] if e.get("para_alkmia")]
    linhas = [
        "# Para o ALKMIA: o que nasceu no Gerenciador de Tarefas",
        "",
        "<!-- Gerado por `python tools/conhecimento.py alkmia --escrever` a partir de",
        "     docs/conhecimento/catalogo.json. Não editar à mão: o teste compara. -->",
        "",
        f"Catálogo de {cat['atualizado']}. Para ler no início de uma sessão no ALKMIA",
        "(`Raoc1987/ALKMIA`). Daqui nada se escreve lá: cada ponto é uma proposta, e",
        "entra pelo protocolo do ALKMIA (`docs/PROJETO-CRIACAO-SENIOR.md`), começando",
        "por **medir de novo**, porque a medição abaixo tem data e o ALKMIA muda.",
        "",
        "Os dois produtos são diferentes. Onde uma decisão do ALKMIA contraria a",
        "daqui (por exemplo o M18, direito de uso na aplicação), ganha a do ALKMIA.",
    ]
    for estado in ORDEM_LA:
        grupo = [e for e in com if e["para_alkmia"]["estado_la"] == estado]
        if not grupo:
            continue
        linhas += ["", f"## {TITULO_LA[estado]}"]
        for e in grupo:
            la = e["para_alkmia"]
            linhas += [
                "",
                f"### {e['titulo']}",
                "",
                f"- **Medido:** {la['medido']}",
                f"- **Como aplicar:** {la['como_aplicar']}",
                f"- **Onde ver aqui:** `{e['destino']}`"
                + (f", provado por `{e['guarda']['caminho']}`" if e.get("guarda") and e["guarda"]["caminho"] != e["destino"] else ""),
            ]
    return "\n".join(linhas) + "\n"


# -------------------------------------------------------------------- triagem

ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def inventario_alkmia(raiz: Path) -> set[str]:
    """Fontes candidatas no outro repositório, no formato das ``fontes`` do catálogo. Só lê."""
    fontes: set[str] = set()
    c = raiz / ".claude"
    for p in sorted((c / "agents").glob("*.md")) if (c / "agents").is_dir() else []:
        fontes.add(f"alkmia:.claude/agents/{p.name}")
    for p in sorted((c / "skills").iterdir()) if (c / "skills").is_dir() else []:
        if p.is_dir():
            fontes.add(f"alkmia:.claude/skills/{p.name}")
    for p in sorted((c / "hooks").glob("*.mjs")) if (c / "hooks").is_dir() else []:
        fontes.add(f"alkmia:.claude/hooks/{p.name}")
    for p in sorted((raiz / "docs").glob("PROMPT-*.md")):
        fontes.add(f"alkmia:docs/{p.name}")
    biblia = raiz / "docs" / "BIBLIA.md"
    if biblia.is_file():
        texto = biblia.read_text(encoding="utf-8")
        parte1 = texto.split("# PARTE II", 1)[0]
        for m in re.findall(r"^\*\*(M\d+(?:-[a-z]+)?)\.", parte1, re.M):
            fontes.add(f"alkmia:docs/BIBLIA.md#{m}")
        for m in re.findall(r"^\*\*([IVX]+)\. ", parte1, re.M):
            if m in ROMANOS:
                fontes.add(f"alkmia:docs/BIBLIA.md#{m}")
    return fontes


def por_triar(cat: dict, raiz_alkmia: Path) -> list[str]:
    raiz_alkmia = raiz_alkmia.resolve()
    if raiz_alkmia == RAIZ or RAIZ in raiz_alkmia.parents:
        raise SystemExit("O caminho do ALKMIA não pode ser este repositório.")
    conhecidas = {f.split("#")[0] if "PROMPT-" in f else f for e in cat["entradas"] for f in e.get("fontes", [])}
    return sorted(inventario_alkmia(raiz_alkmia) - conhecidas)


# ----------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("validar", help="valida o catálogo contra os parâmetros e o repositório")
    sub.add_parser("relatorio", help="o que está guardado por procedimento, dívidas e pendentes")
    t = sub.add_parser("triagem", help="práticas do ALKMIA ainda sem decisão (só leitura)")
    t.add_argument("--alkmia", type=Path, required=True)
    a = sub.add_parser("alkmia", help="o que nasceu aqui e serve ao ALKMIA (gera a nota)")
    a.add_argument("--escrever", action="store_true", help=f"grava em {NOTA_ALKMIA.relative_to(RAIZ)}")
    args = ap.parse_args(argv)

    cat = carregar()
    if args.comando == "validar":
        erros = problemas(cat) + [f"{c}: existe aqui e não está no catálogo" for c in nao_catalogados(cat)]
        for e in erros:
            print(f"ERRO  {e}")
        print("Catálogo válido." if not erros else f"{len(erros)} problema(s).")
        return 1 if erros else 0
    if args.comando == "relatorio":
        print(relatorio(cat))
        return 0
    if args.comando == "alkmia":
        texto = nota_alkmia(cat)
        if args.escrever:
            NOTA_ALKMIA.write_text(texto, encoding="utf-8")
            print(f"Escrito {NOTA_ALKMIA.relative_to(RAIZ)}.")
        else:
            print(texto, end="")
        return 0
    falta = por_triar(cat, args.alkmia)
    print("\n".join(f"  {f}" for f in falta) if falta else "Tudo o que o ALKMIA tem já foi triado.")
    return 1 if falta else 0


if __name__ == "__main__":
    sys.exit(main())
