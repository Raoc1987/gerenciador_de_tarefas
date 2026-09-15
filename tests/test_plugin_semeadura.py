"""Testes da semeadura dos plugins embutidos.

A semeadura corre em todos os arranques: é ela que põe os plugins que
acompanham a aplicação na pasta do utilizador. O que aqui se prova é sobretudo
o que ela **não** faz — não passa por cima de uma versão mais recente, não
mexe numa pasta que não reconhece — e o caso que motivou estes testes: uma
instalação antiga da mesma versão ficava presa a um manifesto desatualizado.
"""

import json
from pathlib import Path

import pytest

from conftest import CORPO_OK, manifesto_valido
from core.plugin_manager import PluginManager
from core.plugin_sources import FontePastasLocais


@pytest.fixture
def pasta_embutidos(tmp_path) -> Path:
    """Diretório que faz de ``plugins/available`` nos testes."""
    destino = tmp_path / "embutidos"
    destino.mkdir()
    return destino


@pytest.fixture
def criar_embutido(pasta_embutidos):
    """Cria um plugin embutido (pasta com manifesto e código)."""

    def _criar(plugin_id="demo", corpo=CORPO_OK, **alteracoes) -> Path:
        pasta = pasta_embutidos / plugin_id
        pasta.mkdir(parents=True, exist_ok=True)
        manifesto = manifesto_valido(plugin_id, **alteracoes)
        (pasta / "plugin.json").write_text(
            json.dumps(manifesto, ensure_ascii=False), encoding="utf-8"
        )
        (pasta / "plugin.py").write_text(corpo, encoding="utf-8")
        return pasta

    return _criar


@pytest.fixture
def fonte(pasta_embutidos) -> FontePastasLocais:
    """A fonte dos plugins embutidos, apontada à pasta temporária."""
    return FontePastasLocais(pasta_embutidos)


def manifesto_instalado(gerenciador: PluginManager, plugin_id: str) -> dict:
    """O ``plugin.json`` tal como está no disco, já instalado."""
    caminho = gerenciador.diretorio / plugin_id / "plugin.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


# ------------------------------------------------------------- caso de base


def test_semeia_plugin_em_falta(gerenciador, criar_embutido, fonte):
    criar_embutido("demo")

    resultados = gerenciador.semear_de_fonte(fonte)

    assert [r.sucesso for r in resultados] == [True]
    assert (gerenciador.diretorio / "demo" / "plugin.py").is_file()


def test_semeadura_e_idempotente(gerenciador, criar_embutido, fonte):
    """Um segundo arranque não reinstala o que já está igual."""
    criar_embutido("demo")
    gerenciador.semear_de_fonte(fonte)

    assert gerenciador.semear_de_fonte(fonte) == []


def test_fonte_indisponivel_nao_faz_nada(gerenciador, tmp_path):
    fonte = FontePastasLocais(tmp_path / "inexistente")

    assert gerenciador.semear_de_fonte(fonte) == []


def test_plugin_incompativel_e_ignorado(gerenciador, criar_embutido, fonte):
    criar_embutido("demo", min_app_version="9.0.0")

    assert gerenciador.semear_de_fonte(fonte) == []
    assert not (gerenciador.diretorio / "demo").exists()


# ------------------------------------------- manifesto alterado, versão igual


def test_manifesto_embutido_alterado_com_a_mesma_versao_e_refrescado(
    gerenciador, criar_plugin, criar_embutido, fonte
):
    """O caso real: o campo ``permissions`` chegou sem a versão mudar.

    Quem já tinha a aplicação instalada ficava com o manifesto sem
    ``permissions`` e o plugin recusava-se a trabalhar — enquanto uma
    instalação limpa trazia o manifesto novo.
    """
    criar_plugin("demo")  # instalado por um pacote anterior desta versão
    criar_embutido("demo", permissions=["tarefas.ler", "tarefas.escrever"])

    resultados = gerenciador.semear_de_fonte(fonte)

    assert [r.sucesso for r in resultados] == [True], resultados
    assert manifesto_instalado(gerenciador, "demo")["permissions"] == [
        "tarefas.ler",
        "tarefas.escrever",
    ]


def test_refrescar_nao_repete_no_arranque_seguinte(
    gerenciador, criar_plugin, criar_embutido, fonte
):
    """Depois de refrescado, o manifesto passa a coincidir e a semeadura pára."""
    criar_plugin("demo")
    criar_embutido("demo", permissions=["tarefas.ler"])
    gerenciador.semear_de_fonte(fonte)

    assert gerenciador.semear_de_fonte(fonte) == []


def test_diferenca_apenas_de_formatacao_nao_reinstala(
    gerenciador, pasta_plugins, criar_embutido, fonte
):
    """Comparam-se manifestos, não bytes: indentação e fins de linha não contam."""
    criar_embutido("demo")
    gerenciador.semear_de_fonte(fonte)

    instalado = pasta_plugins / "demo" / "plugin.json"
    dados = json.loads(instalado.read_text(encoding="utf-8"))
    instalado.write_text(json.dumps(dados, indent=4) + "\n", encoding="utf-8")

    assert gerenciador.semear_de_fonte(fonte) == []


# ------------------------------------------------------- a versão do utilizador


def test_versao_instalada_mais_recente_nunca_e_substituida(
    gerenciador, criar_plugin, criar_embutido, fonte
):
    """O utilizador pode ter instalado algo mais novo do que o que vem na caixa."""
    criar_plugin("demo", version="2.0.0", description="a que o utilizador instalou")
    criar_embutido("demo", description="a embutida")

    assert gerenciador.semear_de_fonte(fonte) == []
    instalado = manifesto_instalado(gerenciador, "demo")
    assert instalado["version"] == "2.0.0"
    assert instalado["description"] == "a que o utilizador instalou"


def test_versao_embutida_mais_nova_atualiza_a_instalada(
    gerenciador, criar_plugin, criar_embutido, fonte
):
    """Uma versão nova na aplicação chega a quem já tinha a antiga."""
    criar_plugin("demo", version="1.0.0")
    criar_embutido("demo", version="1.0.1")

    resultados = gerenciador.semear_de_fonte(fonte)

    assert [r.sucesso for r in resultados] == [True], resultados
    assert manifesto_instalado(gerenciador, "demo")["version"] == "1.0.1"


def test_pasta_instalada_com_manifesto_ilegivel_fica_intacta(
    gerenciador, pasta_plugins, criar_embutido, fonte
):
    """Sem saber o que lá está, a semeadura não passa por cima."""
    pasta = pasta_plugins / "demo"
    pasta.mkdir()
    (pasta / "plugin.json").write_text("{ nao é json", encoding="utf-8")

    criar_embutido("demo")

    assert gerenciador.semear_de_fonte(fonte) == []
    assert (pasta / "plugin.json").read_text(encoding="utf-8") == "{ nao é json"


# ------------------------------------------------- os plugins reais do repositório


def test_plugins_embutidos_do_repositorio_semeiam_sem_erros(gerenciador, raiz_projeto):
    """Os plugins que acompanham a aplicação instalam-se todos numa pasta limpa."""
    fonte = FontePastasLocais(raiz_projeto / "plugins" / "available")
    oferecidos = {p.id for p in fonte.listar()}
    assert oferecidos, "o repositório deve trazer plugins embutidos"

    resultados = gerenciador.semear_de_fonte(fonte)

    assert all(r.sucesso for r in resultados), [r.detalhes for r in resultados if not r]
    assert {r.plugin_id for r in resultados} == oferecidos
    # Segunda passagem: nada a fazer, senão a aplicação reinstalava em cada arranque.
    assert gerenciador.semear_de_fonte(fonte) == []
