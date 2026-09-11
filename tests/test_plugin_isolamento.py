"""Dois plugins com o mesmo nome de módulo não se podem misturar.

Um plugin pode trazer módulos vizinhos na sua pasta — ``utils.py``,
``modelo.py``, nomes que qualquer pessoa escolhe. Se dois plugins escolherem
o mesmo, o segundo a carregar tem de receber o **seu**, não o do primeiro.

Não é só arrumação: se o primeiro plugin pudesse decidir o que o segundo
importa, um plugin instalado escolheria o código que outro executa.
"""

import textwrap

import pytest

CORPO = textwrap.dedent(
    '''
    from core.plugin_api import Plugin
    import ajuda


    class MeuPlugin(Plugin):
        def marca(self):
            return ajuda.MARCA
    '''
)


@pytest.fixture
def dois_plugins(criar_plugin, gerenciador):
    """Dois plugins, cada um com o seu ``ajuda.py``, com conteúdo diferente."""
    for plugin_id, marca in (("alfa", "sou-o-alfa"), ("beta", "sou-o-beta")):
        pasta = criar_plugin(plugin_id, corpo=CORPO)
        (pasta / "ajuda.py").write_text(f'MARCA = "{marca}"\n', encoding="utf-8")
    gerenciador.descobrir()
    return gerenciador


def test_cada_plugin_recebe_o_seu_modulo_vizinho(dois_plugins):
    """O nome ``ajuda`` existe nos dois, e cada um fica com o seu."""
    assert dois_plugins.carregar("alfa").sucesso
    assert dois_plugins.carregar("beta").sucesso

    alfa = dois_plugins.obter("alfa").instancia
    beta = dois_plugins.obter("beta").instancia
    assert alfa.marca() == "sou-o-alfa"
    assert beta.marca() == "sou-o-beta", "o beta recebeu o módulo do alfa"


def test_a_ordem_de_carregamento_nao_muda_o_resultado(dois_plugins):
    assert dois_plugins.carregar("beta").sucesso
    assert dois_plugins.carregar("alfa").sucesso
    assert dois_plugins.obter("beta").instancia.marca() == "sou-o-beta"
    assert dois_plugins.obter("alfa").instancia.marca() == "sou-o-alfa"


def test_um_plugin_nao_deixa_o_nome_ocupado(dois_plugins):
    """Carregar um plugin não pode pôr ``ajuda`` ao alcance de toda a gente."""
    import sys

    dois_plugins.carregar("alfa")
    assert "ajuda" not in sys.modules, (
        "o módulo vizinho do plugin ficou visível como um módulo global"
    )


def test_descarregar_nao_deixa_restos(dois_plugins):
    import sys

    dois_plugins.carregar("alfa")
    dois_plugins.descarregar("alfa")
    restos = [nome for nome in sys.modules if "alfa" in nome]
    assert restos == [], f"ficaram módulos por descartar: {restos}"


def test_recarregar_um_plugin_apanha_o_codigo_novo(dois_plugins, pasta_plugins):
    """Atualizar um plugin não pode servir o módulo vizinho da versão antiga."""
    dois_plugins.carregar("alfa")
    assert dois_plugins.obter("alfa").instancia.marca() == "sou-o-alfa"

    dois_plugins.descarregar("alfa")
    (pasta_plugins / "alfa" / "ajuda.py").write_text(
        'MARCA = "sou-o-alfa-v2"\n', encoding="utf-8"
    )
    dois_plugins.carregar("alfa")
    assert dois_plugins.obter("alfa").instancia.marca() == "sou-o-alfa-v2"


# ============================================ A FORMA RECOMENDADA: `from .`

CORPO_RELATIVO = textwrap.dedent(
    '''
    from core.plugin_api import Plugin


    class MeuPlugin(Plugin):
        def marca(self):
            from . import ajuda          # tarde, de propósito
            return ajuda.MARCA
    '''
)


@pytest.fixture
def dois_plugins_relativos(criar_plugin, gerenciador):
    for plugin_id, marca in (("alfa", "sou-o-alfa"), ("beta", "sou-o-beta")):
        pasta = criar_plugin(plugin_id, corpo=CORPO_RELATIVO)
        (pasta / "ajuda.py").write_text(f'MARCA = "{marca}"\n', encoding="utf-8")
    gerenciador.descobrir()
    return gerenciador


def test_o_import_relativo_funciona_dentro_de_uma_funcao(dois_plugins_relativos):
    """`from . import x` resolve depois do carregamento, sem sys.path.

    É a forma recomendada: já nasce debaixo do nome do plugin, por isso é
    imune à colisão mesmo quando é adiado para dentro de um método.
    """
    for plugin_id in ("alfa", "beta"):
        assert dois_plugins_relativos.carregar(plugin_id).sucesso

    assert dois_plugins_relativos.obter("alfa").instancia.marca() == "sou-o-alfa"
    assert dois_plugins_relativos.obter("beta").instancia.marca() == "sou-o-beta"


def test_o_import_relativo_tambem_nao_ocupa_o_nome(dois_plugins_relativos):
    import sys

    dois_plugins_relativos.carregar("alfa")
    dois_plugins_relativos.obter("alfa").instancia.marca()
    assert "ajuda" not in sys.modules


def test_um_plugin_partido_nao_derruba_a_aplicacao(criar_plugin, gerenciador):
    """Um vizinho que não existe é um erro do plugin, não da aplicação."""
    pasta = criar_plugin("partido", corpo=CORPO)
    assert not (pasta / "ajuda.py").exists()
    gerenciador.descobrir()

    resultado = gerenciador.carregar("partido")
    assert not resultado.sucesso
    assert gerenciador.obter("partido").estado.name == "ERRO"
