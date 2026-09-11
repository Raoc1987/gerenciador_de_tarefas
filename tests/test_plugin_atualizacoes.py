"""Testes do plugin de verificação de atualizações.

Nenhum destes testes toca na rede: a função que vai buscar os dados é
injetada. Um teste que dependesse da internet falharia por razões que nada
têm a ver com o código.
"""

import sys

import pytest

from core.plugin_manager import PREFIXO_MODULO, PluginManager
from tools.empacotar_plugin import empacotar

PACOTE_GITHUB = {
    "tag_name": "v2.5.0",
    "name": "Versão 2.5.0",
    "body": "- Dashboard mais rápido\n- Correções no calendário",
    "html_url": "https://github.com/Raoc1987/gerenciador_de_tarefas/releases/tag/v2.5.0",
    "published_at": "2026-10-01T12:00:00Z",
    "draft": False,
}

MANIFESTO_PROPRIO = {
    "versao": "3.0.0",
    "notas": "Versão da empresa.",
    "url": "https://exemplo.pt/gdt/3.0.0",
    "data": "2026-11-02",
}


@pytest.fixture
def modulo(raiz_projeto, tmp_path, pasta_plugins):
    """Instala o plugin real e devolve o módulo carregado."""
    gerenciador = PluginManager(diretorio=pasta_plugins, app_version="1.0.0")
    pacote = empacotar(raiz_projeto / "plugins" / "available" / "atualizacoes", tmp_path / "p")
    assert gerenciador.instalar_zip(pacote).sucesso
    assert gerenciador.ativar("atualizacoes").sucesso
    return sys.modules[PREFIXO_MODULO + "atualizacoes"]


@pytest.fixture
def plugin(modulo, pasta_plugins):
    """Instância do plugin, sem interface e sem rede."""
    gerenciador = PluginManager(diretorio=pasta_plugins, app_version="1.0.0")
    gerenciador.descobrir()
    gerenciador.ativar("atualizacoes")
    instancia = gerenciador.obter("atualizacoes").instancia
    instancia.buscar = lambda url: PACOTE_GITHUB
    return instancia


# ============================================================ INTERPRETAÇÃO


def test_le_o_formato_do_github(modulo):
    lancamento = modulo.interpretar(PACOTE_GITHUB)
    assert lancamento.versao == "2.5.0", "o 'v' da etiqueta tem de sair"
    assert "Dashboard mais rápido" in lancamento.notas
    assert lancamento.url.endswith("v2.5.0")
    assert lancamento.publicado_em == "2026-10-01"


def test_le_um_manifesto_proprio(modulo):
    lancamento = modulo.interpretar(MANIFESTO_PROPRIO)
    assert lancamento.versao == "3.0.0"
    assert lancamento.url == "https://exemplo.pt/gdt/3.0.0"


def test_rascunho_do_github_e_ignorado(modulo):
    assert modulo.interpretar({**PACOTE_GITHUB, "draft": True}) is None


@pytest.mark.parametrize(
    "resposta",
    [None, "<html>erro</html>", {}, {"outra": "coisa"}, [], {"tag_name": ""}, 42],
)
def test_resposta_que_nao_e_versao(modulo, resposta):
    assert modulo.interpretar(resposta) is None


def test_comparacao_de_versoes(modulo):
    lancamento = modulo.Lancamento(versao="2.0.0")
    assert lancamento.mais_recente_que("1.9.9") is True
    assert lancamento.mais_recente_que("2.0.0") is False
    assert lancamento.mais_recente_que("2.1.0") is False


def test_versao_ilegivel_nao_e_novidade(modulo):
    assert modulo.Lancamento(versao="ontem").mais_recente_que("1.0.0") is False


def test_origem_tem_de_ser_https(modulo):
    with pytest.raises(OSError) as erro:
        modulo.obter_json("http://exemplo.pt/versao.json")
    assert "HTTPS" in str(erro.value)


# ============================================================ CONSENTIMENTO


def test_nao_verifica_sem_autorizacao(plugin):
    """A regra que mais importa: não contacta a internet sem permissão."""
    pedidos = []
    plugin.buscar = lambda url: pedidos.append(url) or PACOTE_GITHUB

    assert plugin.consentiu() is False
    plugin.verificar(silencioso=True)

    assert pedidos == [], "não pode haver nenhum pedido de rede"
    assert plugin.ultimo_lancamento is None


def test_consentimento_e_guardado(plugin):
    plugin.definir_consentimento(True)
    assert plugin.consentiu() is True
    assert plugin.contexto.config()["verificar_online"] is True

    plugin.definir_consentimento(False)
    assert plugin.consentiu() is False


def test_verifica_depois_de_autorizado(plugin):
    pedidos = []
    plugin.buscar = lambda url: (pedidos.append(url), PACOTE_GITHUB)[1]
    plugin.definir_consentimento(True)

    plugin.verificar(silencioso=True)
    _esperar(lambda: pedidos)

    assert pedidos == [plugin.origem()]


def _esperar(condicao, tentativas: int = 100) -> None:
    """Espera pelo trabalho feito noutra linha de execução."""
    import time

    for _ in range(tentativas):
        if condicao():
            return
        time.sleep(0.02)


# ================================================================ RESULTADO


def test_versao_nova_fica_registada(plugin, modulo):
    plugin.definir_consentimento(True)
    plugin._concluir(modulo.interpretar(PACOTE_GITHUB), None, silencioso=True)

    assert plugin.ultimo_lancamento.versao == "2.5.0"
    assert plugin.ultima_verificacao(), "a data da verificação tem de ficar guardada"


def test_publica_evento_quando_ha_novidade(plugin, modulo):
    from core import eventos

    recebidos = []
    eventos.subscrever("atualizacoes.*", recebidos.append)

    plugin.definir_consentimento(True)
    plugin._concluir(modulo.interpretar(PACOTE_GITHUB), None, silencioso=True)

    nomes = [e.nome for e in recebidos]
    assert "atualizacoes.verificada" in nomes
    assert "atualizacoes.disponivel" in nomes
    assert recebidos[-1].dados["versao"] == "2.5.0"


def test_versao_igual_nao_anuncia_novidade(plugin, modulo):
    from core import eventos
    from core.version import APP_VERSION

    recebidos = []
    eventos.subscrever("atualizacoes.disponivel", recebidos.append)

    plugin.definir_consentimento(True)
    plugin._concluir(modulo.Lancamento(versao=APP_VERSION), None, silencioso=True)

    assert recebidos == []


def test_falha_de_rede_e_silenciosa(plugin):
    plugin.definir_consentimento(True)
    plugin._concluir(None, OSError("sem rede"), silencioso=True)

    assert plugin.ultimo_lancamento is None
    assert plugin.ultima_verificacao(), "mesmo a falhar, regista que tentou"


def test_versao_ignorada_nao_volta_a_perguntar(plugin, modulo):
    plugin.definir_consentimento(True)
    plugin._guardar(versao_ignorada="2.5.0")

    # Sem painel, _propor não faz nada; o que se verifica é que a versão
    # ignorada é reconhecida.
    assert plugin.versao_ignorada() == "2.5.0"
    plugin._concluir(modulo.interpretar(PACOTE_GITHUB), None, silencioso=True)
    assert plugin.ultimo_lancamento.versao == "2.5.0"


# ================================================================ ABRIR PÁGINA


def test_abrir_pagina_usa_o_navegador(plugin, modulo, monkeypatch):
    """O plugin não descarrega nem executa nada: abre a página oficial."""
    abertos = []
    monkeypatch.setattr(modulo.webbrowser, "open", abertos.append)

    plugin.ultimo_lancamento = modulo.interpretar(PACOTE_GITHUB)
    assert plugin.abrir_pagina() is True
    assert abertos == [PACOTE_GITHUB["html_url"]]


def test_url_que_nao_e_https_e_recusado(plugin, modulo, monkeypatch):
    abertos = []
    monkeypatch.setattr(modulo.webbrowser, "open", abertos.append)

    plugin.ultimo_lancamento = modulo.Lancamento(versao="9.0.0", url="http://inseguro.pt")
    assert plugin.abrir_pagina() is False
    assert abertos == []


def test_sem_lancamento_abre_a_pagina_do_projeto(plugin, modulo, monkeypatch):
    from core.version import APP_URL

    abertos = []
    monkeypatch.setattr(modulo.webbrowser, "open", abertos.append)

    plugin.ultimo_lancamento = None
    assert plugin.abrir_pagina() is True
    assert abertos == [APP_URL]


# =============================================================== INSTALAÇÃO


def test_plugin_instala_e_ativa(pasta_plugins, raiz_projeto, tmp_path):
    gerenciador = PluginManager(diretorio=pasta_plugins, app_version="1.0.0")
    pacote = empacotar(raiz_projeto / "plugins" / "available" / "atualizacoes", tmp_path / "z")

    assert gerenciador.instalar_zip(pacote).sucesso
    registo = gerenciador.obter("atualizacoes")
    assert registo.nome == "Verificação de Atualizações"
    assert gerenciador.ativar("atualizacoes").sucesso


def test_idiomas_do_plugin(modulo, pasta_plugins):
    import language_manager as lm

    for codigo, esperado in (("pt", "Atualizações"), ("en", "Updates"), ("es", "Actualizaciones")):
        lm.definir_idioma(codigo, persistir=False)
        assert lm.carregar_texto_plugin("atualizacoes", "aba") == esperado


def test_consentimento_e_explicito_no_texto(modulo, pasta_plugins):
    import language_manager as lm

    lm.definir_idioma("pt", persistir=False)
    texto = lm.carregar_texto_plugin("atualizacoes", "pedir_consentimento", origem="X")
    assert "Nada é descarregado nem instalado sem a sua autorização" in texto
