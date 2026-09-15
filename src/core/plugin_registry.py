"""Persistência do estado dos plugins no banco de dados.

Implementa a porta :class:`core.plugin_manager.RegistroEstado` sobre a tabela
``plugins``, criada pela migração v2 do banco. A tabela é independente das
tabelas existentes: remover um plugin nunca afeta as tarefas do utilizador.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.log import obter_logger
from core.plugin_api import ManifestoPlugin
from core.plugin_manager import RegistroEstado

logger = obter_logger(__name__)


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RegistroEstadoBanco(RegistroEstado):
    """Guarda no SQLite qual plugin está instalado e se deve arrancar ativo."""

    def __init__(self) -> None:
        super().__init__()
        self._schema_pronto = False

    # ---------------------------------------------------------------- leitura

    def habilitados(self) -> Dict[str, bool]:
        """Mapa ``plugin_id -> habilitado`` conforme guardado no banco."""
        return {
            linha[0]: bool(linha[1])
            for linha in self._consultar("SELECT id, enabled FROM plugins")
        }

    def obter(self, plugin_id: str) -> Optional[Tuple[str, str, bool, str, str]]:
        """Linha completa do plugin: ``(id, versão, habilitado, instalado, atualizado)``."""
        linhas = self._consultar(
            "SELECT id, version, enabled, installed_at, updated_at FROM plugins WHERE id = ?",
            (plugin_id,),
        )
        if not linhas:
            return None
        linha = linhas[0]
        return (linha[0], linha[1], bool(linha[2]), linha[3], linha[4])

    def listar(self) -> List[Tuple[str, str, bool]]:
        """Todos os plugins registados: ``(id, versão, habilitado)``."""
        return [
            (linha[0], linha[1], bool(linha[2]))
            for linha in self._consultar(
                "SELECT id, version, enabled FROM plugins ORDER BY id"
            )
        ]

    # ---------------------------------------------------------------- escrita

    def registrar(self, manifesto: ManifestoPlugin, habilitado: bool = False) -> None:
        """Insere o plugin ou atualiza a sua versão, preservando ``enabled``."""
        agora = _agora()
        with self._conexao() as conexao:
            conexao.execute(
                """
                INSERT INTO plugins (id, version, enabled, installed_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (manifesto.id, manifesto.versao, 1 if habilitado else 0, agora, agora),
            )
        logger.debug("Plugin registado no banco: %s v%s", manifesto.id, manifesto.versao)

    def definir_habilitado(self, plugin_id: str, habilitado: bool) -> None:
        """Persiste a escolha do utilizador de manter o plugin ligado ou não."""
        with self._conexao() as conexao:
            cursor = conexao.execute(
                "UPDATE plugins SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if habilitado else 0, _agora(), plugin_id),
            )
            if cursor.rowcount == 0:
                logger.debug("Plugin %s ainda não registado; nada a atualizar.", plugin_id)

    def esquecer(self, plugin_id: str) -> None:
        """Remove o plugin do registo, após desinstalação."""
        with self._conexao() as conexao:
            conexao.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
        logger.debug("Plugin esquecido no banco: %s", plugin_id)

    # ---------------------------------------------------------------- apoio

    def _conexao(self):
        import banco_de_dados

        if not self._schema_pronto:
            banco_de_dados.criar_tabela()
            self._schema_pronto = True
        return banco_de_dados.conectar()

    def _consultar(self, sql: str, parametros: tuple = ()) -> List[tuple]:
        try:
            with self._conexao() as conexao:
                return conexao.execute(sql, parametros).fetchall()
        except Exception:
            logger.exception("Falha ao ler o registo de plugins.")
            return []
