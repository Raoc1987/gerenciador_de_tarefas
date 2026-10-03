"""As skills do projeto (``.claude/skills/``) e o índice no ``CLAUDE.md``.

O Claude Code só carrega uma skill cujo cabeçalho tem ``name`` e
``description``, e o índice do ``CLAUDE.md`` é como uma sessão nova sabe que
ela existe. Estes testes apanham o desencontro que nenhum outro apanharia: uma
skill renomeada que deixou o índice a apontar para nada, ou uma skill que
manda para outra que já não existe.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SKILLS = RAIZ / ".claude" / "skills"
CLAUDE_MD = RAIZ / "CLAUDE.md"

#: Skills do próprio Claude Code a que as nossas podem mandar.
EMBUTIDAS = {"code-review", "security-review", "simplify", "init", "loop"}


def _cabecalho(texto: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", texto, re.S)
    assert m, "sem cabeçalho --- no início"
    campos = {}
    for linha in m.group(1).splitlines():
        chave, _, valor = linha.partition(":")
        if chave.strip() and valor.strip():
            campos[chave.strip()] = valor.strip()
    return campos


def _skills() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def test_ha_skills_no_projeto():
    assert _skills(), f"nenhuma skill em {SKILLS}"


@pytest.mark.parametrize("pasta", _skills(), ids=lambda p: p.name)
def test_cada_skill_tem_o_cabecalho_que_o_claude_code_le(pasta):
    ficheiro = pasta / "SKILL.md"
    assert ficheiro.is_file(), f"{pasta.name}: falta o SKILL.md"
    campos = _cabecalho(ficheiro.read_text(encoding="utf-8"))
    assert campos.get("name") == pasta.name, (
        f"{pasta.name}: o name do cabeçalho é {campos.get('name')!r}; tem de ser o nome da pasta"
    )
    descricao = campos.get("description", "")
    assert 40 <= len(descricao) <= 1024, (
        f"{pasta.name}: a description tem {len(descricao)} caracteres; "
        "é ela que decide quando a skill entra, e o limite é 1024"
    )


@pytest.mark.parametrize("pasta", _skills(), ids=lambda p: p.name)
def test_as_ligacoes_relativas_de_uma_skill_existem(pasta):
    for md in pasta.rglob("*.md"):
        for alvo in re.findall(r"\]\(([^)#:]+)\)", md.read_text(encoding="utf-8")):
            assert (md.parent / alvo).exists(), f"{md.relative_to(RAIZ)}: liga para {alvo}, que não existe"


def test_as_skills_so_mandam_para_skills_que_existem():
    existentes = {p.name for p in _skills()} | EMBUTIDAS
    for md in SKILLS.rglob("*.md"):
        for nome in re.findall(r"skill \*\*([a-z0-9-]+)\*\*|\*\*([a-z0-9-]+)\*\* \(skill", md.read_text(encoding="utf-8")):
            nome = next(n for n in nome if n)
            assert nome in existentes, f"{md.relative_to(RAIZ)}: manda para a skill {nome}, que não existe"


def test_o_indice_do_claude_md_bate_com_as_pastas():
    indice = set(re.findall(r"^\| `([a-z0-9-]+)` \|", CLAUDE_MD.read_text(encoding="utf-8"), re.M))
    pastas = {p.name for p in _skills()}
    assert indice - pastas == set(), f"o CLAUDE.md lista skills que não existem: {sorted(indice - pastas)}"
    assert pastas - indice == set(), f"skills que faltam no índice do CLAUDE.md: {sorted(pastas - indice)}"
