"""Sistema de idiomas.

Os textos ficam em ``assets/idiomas/<código>.json``. Um idioma parcial é
completado pelo idioma padrão (``pt``); se a chave não existir em lado nenhum,
a própria chave é devolvida — a interface nunca fica em branco.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from core import config
from core.log import obter_logger
from core.paths import caminho_recurso

logger = obter_logger(__name__)

IDIOMA_PADRAO = "pt"

IDIOMAS_SUPORTADOS: Dict[str, str] = {
    "pt": "Português 🇧🇷",
    "en": "Inglês 🇺🇸",
    "es": "Espanhol 🇪🇸",
}

_CHAVE_CONFIG = "idioma"

_cache: Dict[str, Dict[str, str]] = {}
_idioma_atual = IDIOMA_PADRAO


def _caminho_idioma(codigo: str):
    return caminho_recurso("assets", "idiomas", f"{codigo}.json")


def _carregar_idioma(codigo: str) -> Dict[str, str]:
    if codigo in _cache:
        return _cache[codigo]

    caminho = _caminho_idioma(codigo)
    textos: Dict[str, str] = {}
    try:
        conteudo = caminho.read_text(encoding="utf-8").strip()
        if conteudo:
            dados = json.loads(conteudo)
            if isinstance(dados, dict):
                textos = {str(k): str(v) for k, v in dados.items()}
            else:
                logger.warning("Arquivo de idioma %s não contém um objeto JSON.", caminho)
    except FileNotFoundError:
        logger.warning("Arquivo de idioma inexistente: %s", caminho)
    except (OSError, json.JSONDecodeError) as erro:
        logger.warning("Falha ao ler idioma %s: %s", codigo, erro)

    _cache[codigo] = textos
    return textos


def idiomas_disponiveis() -> List[Tuple[str, str]]:
    """Lista de ``(código, rótulo)`` dos idiomas suportados."""
    return list(IDIOMAS_SUPORTADOS.items())


def idioma_atual() -> str:
    """Código do idioma em uso."""
    return _idioma_atual


def definir_idioma(codigo: str, persistir: bool = True) -> str:
    """Define o idioma corrente e devolve o código efetivamente aplicado."""
    global _idioma_atual
    if codigo not in IDIOMAS_SUPORTADOS:
        logger.warning("Idioma não suportado: %r; mantendo %r.", codigo, _idioma_atual)
        return _idioma_atual

    _idioma_atual = codigo
    _carregar_idioma(codigo)
    if persistir:
        try:
            config.definir(_CHAVE_CONFIG, codigo)
        except OSError as erro:
            logger.warning("Não foi possível guardar o idioma escolhido: %s", erro)
    logger.info("Idioma definido para %s", codigo)
    return codigo


def restaurar_idioma_guardado() -> str:
    """Reaplica o idioma guardado nas configurações (ou o padrão)."""
    guardado = config.obter(_CHAVE_CONFIG, IDIOMA_PADRAO)
    return definir_idioma(str(guardado), persistir=False)


def carregar_texto(chave: str, padrao: str | None = None, **formatacao: Any) -> str:
    """Devolve o texto traduzido de ``chave``.

    Procura no idioma atual, depois no idioma padrão, depois em ``padrao`` e
    por fim devolve a própria chave. ``formatacao`` é aplicada com ``str.format``.
    """
    textos = _carregar_idioma(_idioma_atual)
    valor = textos.get(chave)
    if valor is None and _idioma_atual != IDIOMA_PADRAO:
        valor = _carregar_idioma(IDIOMA_PADRAO).get(chave)
    if valor is None:
        valor = padrao if padrao is not None else chave

    if formatacao:
        try:
            return valor.format(**formatacao)
        except (KeyError, IndexError, ValueError):
            logger.warning("Falha ao formatar o texto %r.", chave)
    return valor


def limpar_cache() -> None:
    """Descarta os idiomas em memória, incluindo os dos plugins."""
    _cache.clear()
    _textos_plugins.clear()


# --------------------------------------------------- textos fornecidos por plugins

#: ``plugin_id -> código de idioma -> {chave: texto}``
_textos_plugins: Dict[str, Dict[str, Dict[str, str]]] = {}


def registrar_textos_plugin(plugin_id: str, textos_por_idioma: Dict[str, Dict[str, str]]) -> None:
    """Regista os textos de um plugin, por idioma.

    Os textos do plugin vivem num espaço próprio: nunca sobrepõem os da
    aplicação nem colidem com os de outro plugin.
    """
    normalizados: Dict[str, Dict[str, str]] = {}
    for codigo, textos in (textos_por_idioma or {}).items():
        if isinstance(textos, dict):
            normalizados[str(codigo)] = {str(k): str(v) for k, v in textos.items()}
    _textos_plugins[plugin_id] = normalizados
    logger.debug("Textos registados para o plugin %s: %s", plugin_id, list(normalizados))


def remover_textos_plugin(plugin_id: str) -> None:
    """Esquece os textos de um plugin (ao descarregá-lo ou removê-lo)."""
    _textos_plugins.pop(plugin_id, None)


def carregar_texto_plugin(
    plugin_id: str, chave: str, padrao: str | None = None, **formatacao: Any
) -> str:
    """Texto de um plugin no idioma atual, com recurso aos textos da aplicação.

    Ordem de procura: idioma atual do plugin, idioma padrão do plugin, textos
    da aplicação, ``padrao``, e por fim a própria chave.
    """
    do_plugin = _textos_plugins.get(plugin_id, {})
    valor = do_plugin.get(_idioma_atual, {}).get(chave)
    if valor is None:
        valor = do_plugin.get(IDIOMA_PADRAO, {}).get(chave)
    if valor is None:
        return carregar_texto(chave, padrao, **formatacao)

    if formatacao:
        try:
            return valor.format(**formatacao)
        except (KeyError, IndexError, ValueError):
            logger.warning("Falha ao formatar o texto %r do plugin %s.", chave, plugin_id)
    return valor
