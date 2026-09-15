"""Testes da semeadura dos plugins que acompanham a aplicação (ADR-0006).

A pergunta que estes testes fazem é sempre a mesma: **de quem é este plugin?**
Da aplicação, e então uma correção publicada tem de lhe chegar; ou do
utilizador, e então nada lhe toca sem ele mandar.

O caso que deu origem a tudo isto está em
:func:`test_correcao_de_permissoes_chega_a_uma_instalacao_existente`: o
Calendar passou a declarar as permissões de que precisa, e em todas as
instalações que já existiam continuou a falhar a ativação — porque a
semeadura saltava qualquer id que já estivesse em disco.
"""

import json

import pytest

from conftest import CORPO_OK, manifesto_valido
from core import auditoria, eventos
from core.plugin_manager import PluginManager, SemeaduraDecisao
from core.plugin_registry import RegistroEstadoBanco
from core.plugin_sources import (
    PROVENIENCIA_EMBUTIDO,
    PROVENIENCIA_UTILIZADOR,
    FontePastasLocais,
)


@pytest.fixture
def pasta_embutidos(tmp_path):
    """Pasta que faz de ``plugins/available`` (os que vêm na aplicação)."""
    destino = tmp_path / "available"
    destino.mkdir()
    return destino


@pytest.fixture
def embutir(pasta_embutidos):
    """Escreve um plugin na pasta dos embutidos."""

    def _embutir(plugin_id="demo", corpo=CORPO_OK, **alteracoes):
        pasta = pasta_embutidos / plugin_id
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "plugin.json").write_text(
            json.dumps(manifesto_valido(plugin_id, **alteracoes), ensure_ascii=False),
            encoding="utf-8",
        )
        (pasta / "plugin.py").write_text(corpo, encoding="utf-8")
        return pasta

    return _embutir


@pytest.fixture
def fonte(pasta_embutidos):
    """A fonte dos plugins embutidos, apontada à pasta de teste."""
    return FontePastasLocais(pasta_embutidos)


@pytest.fixture
def gerenciador_no_banco(pasta_plugins):
    """Gerenciador com o registo persistido, que é onde a posse vive."""
    return PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )


def versao_no_disco(pasta_plugins, plugin_id: str) -> str:
    return json.loads(
        (pasta_plugins / plugin_id / "plugin.json").read_text(encoding="utf-8")
    )["version"]


# =============================================================== INSTALAR


def test_semeia_o_que_ainda_nao_existe(gerenciador_no_banco, fonte, embutir, pasta_plugins):
    embutir("demo", version="1.0.0")

    resultados = gerenciador_no_banco.semear_de_fonte(fonte)

    assert [r.sucesso for r in resultados] == [True]
    assert (pasta_plugins / "demo" / "plugin.json").is_file()


def test_o_que_e_semeado_fica_a_pertencer_a_aplicacao(
    gerenciador_no_banco, fonte, embutir
):
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    instalacao = gerenciador_no_banco.registro.instalacao("demo")
    assert instalacao.proveniencia == PROVENIENCIA_EMBUTIDO
    assert instalacao.impressao, "sem impressão não há como saber se lhe mexeram"


def test_semeadura_segunda_vez_nao_faz_nada(gerenciador_no_banco, fonte, embutir):
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    assert (
        gerenciador_no_banco.decidir_semeadura(fonte, "demo") is SemeaduraDecisao.EM_DIA
    )


# =============================================================== ATUALIZAR


def test_versao_embutida_mais_recente_atualiza(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    """O buraco que este ADR tapa: a correção tem de chegar a quem já tem."""
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    embutir("demo", version="1.1.0")
    assert (
        gerenciador_no_banco.decidir_semeadura(fonte, "demo")
        is SemeaduraDecisao.ATUALIZAR
    )
    resultados = gerenciador_no_banco.semear_de_fonte(fonte)

    assert [r.chave_mensagem for r in resultados] == ["plugin_atualizado"]
    assert versao_no_disco(pasta_plugins, "demo") == "1.1.0"


def test_versao_embutida_mais_antiga_nao_desatualiza(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    embutir("demo", version="2.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    embutir("demo", version="1.0.0")
    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    assert versao_no_disco(pasta_plugins, "demo") == "2.0.0"


def test_plugin_embutido_ilegivel_e_reposto(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    """Um plugin nosso que ficou ilegível repõe-se sozinho.

    Vem antes da regra de não pisar o que foi modificado, e de propósito: uma
    pasta que não se consegue ler não é uma alteração a preservar. Deixá-la
    como está seria deixar o plugin partido à espera de um clique.
    """
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)
    (pasta_plugins / "demo" / "plugin.json").write_text("{ isto não é json", encoding="utf-8")

    assert (
        gerenciador_no_banco.decidir_semeadura(fonte, "demo")
        is SemeaduraDecisao.ATUALIZAR
    )
    assert all(r.sucesso for r in gerenciador_no_banco.semear_de_fonte(fonte))
    assert versao_no_disco(pasta_plugins, "demo") == "1.0.0"
    assert gerenciador_no_banco.obter("demo").estado.utilizavel


# ============================================================== NÃO TOCAR


def test_plugin_modificado_a_mao_nao_e_tocado(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    """Mexer no plugin é uma escolha de alguém. O arranque não a desfaz."""
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)
    alterado = pasta_plugins / "demo" / "plugin.py"
    alterado.write_text(CORPO_OK + "\n# alterado à mão\n", encoding="utf-8")

    embutir("demo", version="1.1.0")

    assert (
        gerenciador_no_banco.decidir_semeadura(fonte, "demo")
        is SemeaduraDecisao.MODIFICADO
    )
    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    assert "alterado à mão" in alterado.read_text(encoding="utf-8")
    assert gerenciador_no_banco.retidos_da_fonte(fonte) == ["demo"]


def test_plugin_instalado_pelo_utilizador_nao_e_tocado(
    gerenciador_no_banco, fonte, embutir, zip_valido, pasta_plugins
):
    """Instalar por cima transfere a posse: passa a mandar o utilizador."""
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)
    gerenciador_no_banco.instalar_zip(zip_valido("demo", version="3.0.0"))
    assert (
        gerenciador_no_banco.registro.instalacao("demo").proveniencia
        == PROVENIENCIA_UTILIZADOR
    )

    embutir("demo", version="4.0.0")

    assert (
        gerenciador_no_banco.decidir_semeadura(fonte, "demo")
        is SemeaduraDecisao.DO_UTILIZADOR
    )
    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    assert versao_no_disco(pasta_plugins, "demo") == "3.0.0"


def test_plugin_embutido_incompativel_e_ignorado(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    embutir("futuro", min_app_version="99.0.0")
    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    assert not (pasta_plugins / "futuro").exists()


# ================================================================= REPOR


def test_repor_sobrepoe_o_que_foi_modificado(
    gerenciador_no_banco, fonte, embutir, pasta_plugins
):
    """A saída explícita: mesma versão, conteúdo reposto."""
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)
    alterado = pasta_plugins / "demo" / "plugin.py"
    alterado.write_text("# estragado\n", encoding="utf-8")

    resultados = gerenciador_no_banco.semear_de_fonte(fonte, repor=True)

    assert all(r.sucesso for r in resultados), [r.detalhes for r in resultados]
    assert alterado.read_text(encoding="utf-8") == CORPO_OK
    assert gerenciador_no_banco.retidos_da_fonte(fonte) == []


def test_repor_recupera_o_plugin_que_o_utilizador_substituiu(
    gerenciador_no_banco, fonte, embutir, zip_valido, pasta_plugins
):
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)
    gerenciador_no_banco.instalar_zip(zip_valido("demo", version="3.0.0"))

    gerenciador_no_banco.semear_de_fonte(fonte, repor=True)

    assert versao_no_disco(pasta_plugins, "demo") == "1.0.0"
    assert (
        gerenciador_no_banco.registro.instalacao("demo").proveniencia
        == PROVENIENCIA_EMBUTIDO
    )


# ============================================================== ADOÇÃO


def test_instalacao_anterior_ao_registo_e_adotada(
    gerenciador_no_banco, fonte, embutir, criar_plugin, pasta_plugins
):
    """Uma pasta que já lá estava, sem dono registado, é adotada e atualizada.

    É o caminho de atualização real: quem já tinha a aplicação instalada tem
    os plugins em disco e o banco sem uma palavra sobre a posse deles.
    """
    criar_plugin("demo", version="1.0.0")
    assert not gerenciador_no_banco.registro.instalacao("demo").proveniencia

    embutir("demo", version="1.1.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    assert (
        gerenciador_no_banco.registro.instalacao("demo").proveniencia
        == PROVENIENCIA_EMBUTIDO
    )
    assert versao_no_disco(pasta_plugins, "demo") == "1.1.0"


def test_adocao_nao_mexe_no_que_ja_esta_em_dia(
    gerenciador_no_banco, fonte, embutir, criar_plugin, pasta_plugins
):
    """Adotar dá dono; não é desculpa para reinstalar o que está bem."""
    criar_plugin("demo", version="1.0.0")
    embutir("demo", version="1.0.0")

    assert gerenciador_no_banco.semear_de_fonte(fonte) == []
    instalacao = gerenciador_no_banco.registro.instalacao("demo")
    assert instalacao.proveniencia == PROVENIENCIA_EMBUTIDO
    assert instalacao.intacta(pasta_plugins / "demo")


# ====================================================== O CASO DE ORIGEM


def test_correcao_de_permissoes_chega_a_uma_instalacao_existente(
    gerenciador_no_banco, fonte, embutir, criar_plugin, pasta_plugins
):
    """O bug relatado, em miniatura.

    Instalado: um plugin que não declara as permissões de que precisa — e que
    por isso falha a ativar. Embutido: a versão corrigida. Antes do ADR-0006 a
    correção nunca chegava; agora chega.
    """
    criar_plugin("demo", version="1.0.0")  # sem "permissions"
    manifesto_instalado = json.loads(
        (pasta_plugins / "demo" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "permissions" not in manifesto_instalado

    embutir("demo", version="1.0.1", permissions=["tarefas.ler"])
    gerenciador_no_banco.semear_de_fonte(fonte)

    registro = gerenciador_no_banco.obter("demo")
    assert registro.manifesto.versao == "1.0.1"
    assert [p.value for p in registro.manifesto.permissoes] == ["tarefas.ler"]
    assert gerenciador_no_banco.ativar("demo").sucesso


# ============================================================= AUDITORIA


def test_a_substituicao_fica_na_trilha_de_auditoria(
    gerenciador_no_banco, fonte, embutir
):
    """Substituir o plugin de alguém é um facto: fica registado, e diz quem."""
    embutir("demo", version="1.0.0")
    gerenciador_no_banco.semear_de_fonte(fonte)

    auditoria.ativar()
    try:
        embutir("demo", version="1.1.0")
        gerenciador_no_banco.semear_de_fonte(fonte)
        registos = auditoria.consultar(evento=eventos.PLUGIN_ATUALIZADO)
    finally:
        auditoria.desativar()

    assert len(registos) == 1
    assert registos[0].alvo == "demo"
    assert "1.1.0" in registos[0].detalhe
    assert "1.0.0" in registos[0].detalhe
    assert PROVENIENCIA_EMBUTIDO in registos[0].detalhe
