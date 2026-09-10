"""Configurações da aplicação e dos plugins, guardadas em JSON.

A configuração geral (``app_config.json``) fica separada da configuração de
cada plugin (``config/plugins/<id>.json``), para que remover um plugin nunca
afete as preferências da aplicação.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.log import obter_logger
from core.paths import diretorio_config, diretorio_config_plugins

logger = obter_logger(__name__)

_NOME_CONFIG_APP = "app_config.json"


def _ler_json(caminho: Path) -> Dict[str, Any]:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        logger.warning("Configuração ilegível em %s (%s); usando padrões.", caminho, erro)
        return {}
    return dados if isinstance(dados, dict) else {}


def _escrever_json(caminho: Path, dados: Dict[str, Any]) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(caminho)


def caminho_config_app() -> Path:
    """Caminho do arquivo de configuração geral."""
    return diretorio_config() / _NOME_CONFIG_APP


def carregar_config() -> Dict[str, Any]:
    """Devolve a configuração geral da aplicação."""
    return _ler_json(caminho_config_app())


def guardar_config(dados: Dict[str, Any]) -> None:
    """Persiste a configuração geral (escrita atómica)."""
    _escrever_json(caminho_config_app(), dados)


def obter(chave: str, padrao: Any = None) -> Any:
    """Lê uma preferência da configuração geral."""
    return carregar_config().get(chave, padrao)


def definir(chave: str, valor: Any) -> None:
    """Grava uma preferência na configuração geral."""
    dados = carregar_config()
    dados[chave] = valor
    guardar_config(dados)


def caminho_config_plugin(plugin_id: str) -> Path:
    """Caminho do arquivo de configuração de um plugin."""
    return diretorio_config_plugins() / f"{plugin_id}.json"


def carregar_config_plugin(plugin_id: str) -> Dict[str, Any]:
    """Configuração privada de um plugin."""
    return _ler_json(caminho_config_plugin(plugin_id))


def guardar_config_plugin(plugin_id: str, dados: Dict[str, Any]) -> None:
    """Persiste a configuração privada de um plugin."""
    _escrever_json(caminho_config_plugin(plugin_id), dados)


def remover_config_plugin(plugin_id: str) -> bool:
    """Apaga a configuração de um plugin. Devolve ``True`` se existia."""
    caminho = caminho_config_plugin(plugin_id)
    if caminho.exists():
        caminho.unlink()
        return True
    return False
