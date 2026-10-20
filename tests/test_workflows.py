"""Regras dos workflows do CI (CLAUDE.md, Convenções).

Uma Action referida por etiqueta (``@v4``) pode passar a apontar para outro
código sem nada mudar aqui; fixada por SHA, só muda num diff que alguém lê.
E um workflow sem ``permissions:`` recebe as do repositório, que podem incluir
escrita.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$", re.M)
SHA = re.compile(r"@[0-9a-f]{40}$")


def usos_por_fixar(texto: str) -> list[str]:
    """As Actions de terceiros que não estão fixadas por SHA com a versão em comentário."""
    maus = []
    for alvo, resto in USES.findall(texto):
        if alvo.startswith("./") or alvo.startswith("docker://"):
            continue
        if not SHA.search(alvo) or not re.search(r"#\s*v?\d", resto):
            maus.append(alvo)
    return maus


def test_ha_workflows():
    assert WORKFLOWS


@pytest.mark.parametrize("caminho", WORKFLOWS, ids=lambda p: p.name)
def test_cada_action_esta_fixada_por_sha(caminho):
    assert usos_por_fixar(caminho.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("caminho", WORKFLOWS, ids=lambda p: p.name)
def test_cada_workflow_declara_as_permissoes(caminho):
    assert re.search(r"^permissions:", caminho.read_text(encoding="utf-8"), re.M)


@pytest.mark.parametrize("linha", [
    "      - uses: actions/checkout@v4",
    "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "      - uses: actions/checkout@main # v4",
])
def test_a_regra_recusa_etiquetas_e_sha_sem_versao(linha):
    assert usos_por_fixar(linha) == [linha.split("uses: ")[1].split(" ")[0]]


def test_a_regra_aceita_sha_com_versao_e_actions_locais():
    assert usos_por_fixar(
        "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
        "  - uses: ./.github/actions/local\n"
    ) == []


ENSAIO = RAIZ / ".github" / "workflows" / "ensaio-publicado.yml"


def test_o_ensaio_do_publicado_so_corre_em_deploys_do_vercel():
    """O base-de-dados.yml também cria deployments (ambiente producao) e o URL
    desses é a execução no GitHub: em 2026-10-19 o ensaio correu contra ela e
    deu 7 de 8 vermelhos. Só os deployments do vercel[bot] são a aplicação."""
    texto = ENSAIO.read_text(encoding="utf-8")
    assert "deployment_status.creator.login == 'vercel[bot]'" in texto
    assert "target_url" not in texto


def test_o_segredo_de_bypass_so_vai_para_hosts_do_projeto():
    """Um URL vindo de um evento ou de um input não recebe o segredo."""
    texto = ENSAIO.read_text(encoding="utf-8")
    assert "unset VERCEL_AUTOMATION_BYPASS_SECRET" in texto
    assert "gerenciador-de-tarefas-*-goethita.vercel.app" in texto


BASE_DE_DADOS = RAIZ / ".github" / "workflows" / "base-de-dados.yml"


def test_a_cli_do_supabase_fica_fora_do_checkout():
    """Na raiz do repositório há a pasta supabase/: extrair ali o binário com o
    mesmo nome falha ("tar: supabase: Cannot open: File exists"), e foi assim
    que a primeira aplicação à produção caiu a 2026-10-20."""
    texto = BASE_DE_DADOS.read_text(encoding="utf-8")
    assert (RAIZ / "supabase").is_dir()
    assert "./supabase" not in texto
    assert re.search(r"tar xzf \S+ supabase", texto)
    assert 'cd "$RUNNER_TEMP/cli"' in texto
    assert texto.count('"$RUNNER_TEMP/cli/supabase" db push') == 2
