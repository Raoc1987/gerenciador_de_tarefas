"""A publicação de uma versão: o que tem de bater certo antes de sair.

Até aqui o projeto construía o programa, validava-o e **deitava-o fora**: o
executável ficava num artefacto de Actions que expira em sete dias, o
instalador só era construído no ensaio semanal e nem sequer era guardado, e
não havia uma única release. Quem quisesse o programa não tinha de onde o
tirar.

O que estes testes guardam é a parte que falha em silêncio — a versão. Marcar
`v1.0.1` com o código ainda em `1.0.0` publica um ficheiro chamado 1.0.1 que
instala uma aplicação que se diz 1.0.0, e isso aparece nos atalhos, no
"Adicionar ou remover programas" e no ecrã do Sobre. Três sítios a discordar
do nome do ficheiro que a pessoa descarregou.
"""

import re
from pathlib import Path

import pytest

from core.version import APP_VERSION

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "release.yml"


# ======================================================= a etiqueta e a versão


def test_a_etiqueta_certa_passa():
    from tools.verificar_versao import conferir

    assert conferir(f"v{APP_VERSION}") == APP_VERSION
    assert conferir(APP_VERSION) == APP_VERSION, "sem o v também é a mesma versão"


def test_uma_etiqueta_errada_nao_passa():
    """É a razão de isto existir."""
    from tools.verificar_versao import conferir

    with pytest.raises(ValueError):
        conferir("v9.9.9", versao="1.0.0")


def test_a_mensagem_diz_as_duas_versoes():
    """Quem a lê está a meio de uma publicação: precisa de saber qual mudar."""
    from tools.verificar_versao import conferir

    with pytest.raises(ValueError) as erro:
        conferir("v2.0.0", versao="1.0.0")
    assert "2.0.0" in str(erro.value) and "1.0.0" in str(erro.value)


def test_uma_etiqueta_vazia_nao_passa():
    from tools.verificar_versao import conferir

    for vazia in ("", "   ", "v"):
        with pytest.raises(ValueError):
            conferir(vazia)


# ============================================ o workflow aponta para o que existe


@pytest.fixture
def workflow() -> str:
    assert WORKFLOW.is_file(), "não há workflow de release"
    return WORKFLOW.read_text(encoding="utf-8")


def test_a_release_sai_de_uma_etiqueta_e_nao_de_cada_integracao(workflow):
    """Cada versão publicada é uma versão que alguém pode ter instalada."""
    assert 'tags:' in workflow and '"v*"' in workflow
    assert "branches" not in workflow, "uma release por integração seria a mais"


def test_os_comandos_do_workflow_existem_mesmo(workflow):
    """Um workflow que chama um script que não existe só falha na release.

    E falha **depois** de alguém ter marcado a etiqueta, que é o pior momento
    para descobrir um nome mal escrito.
    """
    chamados = set(re.findall(r"python (tools/[\w_]+\.py)", workflow))
    assert chamados, "o workflow não chama nenhuma ferramenta"
    for script in sorted(chamados):
        assert (RAIZ / script).is_file(), f"{script} não existe"


def test_a_release_verifica_a_versao_antes_de_construir(workflow):
    """Construir durante dez minutos para depois recusar é tempo deitado fora."""
    posicao_versao = workflow.index("verificar_versao.py")
    posicao_build = workflow.index("tools/build.py")
    assert posicao_versao < posicao_build


def test_a_release_corre_os_ensaios_que_protegem_quem_ja_instalou(workflow):
    """Correm semanalmente no outro workflow. Numa release têm de correr sempre.

    São os dois que garantem que instalar por cima não apaga tarefas, contas
    nem plugins — e uma release é exatamente quando isso importa.
    """
    assert "testar_atualizacao.py" in workflow
    assert "testar_instalador.py" in workflow


def test_o_ficheiro_publicado_leva_a_versao_no_nome(workflow):
    """Quem tiver dois downloads na pasta distingue-os sem os abrir."""
    assert "GerenciadorDeTarefas-Setup-" in workflow


def test_o_workflow_pode_criar_a_release(workflow):
    """Sem `contents: write` a publicação falha no último passo de todos."""
    assert "contents: write" in workflow


# ============================================ as notas vêm do que está no repo


def test_as_notas_saem_do_changelog(workflow):
    """Revistas como tudo o resto, e não escritas na caixa do GitHub.

    ``body_path`` e não ``body``: o texto vem de um ficheiro que passou por
    uma revisão, em vez de estar embutido no workflow onde ninguém o lê.
    """
    assert "notas_da_versao.py" in workflow
    assert "body_path:" in workflow
    assert "body: |" not in workflow, "voltou a haver notas presas ao workflow"


def test_a_versao_a_publicar_tem_notas_escritas():
    """Se falhar, alguém subiu a versão e esqueceu-se do changelog."""
    from tools.notas_da_versao import extrair

    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    notas = extrair(APP_VERSION, changelog)
    assert notas, f"não há secção [{APP_VERSION}] no CHANGELOG.md"
    assert len(notas.splitlines()) > 5, "a secção está praticamente vazia"


def test_uma_versao_sem_seccao_nao_rebenta():
    """Sai só com a lista que o GitHub gera. É pouco, mas não é errado."""
    from tools.notas_da_versao import extrair

    assert extrair("9.9.9", "# Changelog\n\n## [1.0.0]\nalgo\n") == ""


def test_a_seccao_acaba_onde_comeca_a_versao_seguinte():
    """Senão as notas de uma versão levavam a história toda atrás."""
    from tools.notas_da_versao import extrair

    texto = "## [2.0.0] - hoje\nnovo\n\n## [1.0.0] - ontem\nvelho\n"
    assert extrair("v2.0.0", texto) == "novo"
    assert "velho" not in extrair("2.0.0", texto)
