"""Camada de persistência (SQLite) das tarefas.

O banco vive no diretório de dados do utilizador (ver :mod:`core.paths`) e
nunca em ``Program Files``, para que a aplicação funcione sem privilégios de
administrador e sobreviva a atualizações.

O schema é versionado através de ``PRAGMA user_version``; as migrações são
aplicadas em ordem e são aditivas (nunca destrutivas).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

from core.log import obter_logger
from core.paths import caminho_banco

logger = obter_logger(__name__)

# Cada entrada é aplicada quando ``PRAGMA user_version`` for menor que o índice+1.
_MIGRACOES: List[Sequence[str]] = [
    # v1 — tabela de tarefas
    (
        """
        CREATE TABLE IF NOT EXISTS tarefas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao        TEXT    NOT NULL,
            data_vencimento  TEXT,
            concluida        INTEGER NOT NULL DEFAULT 0,
            criada_em        TEXT    NOT NULL
        )
        """,
    ),
    # v2 — registo dos plugins instalados (aditiva: não toca em `tarefas`)
    (
        """
        CREATE TABLE IF NOT EXISTS plugins (
            id            TEXT    PRIMARY KEY,
            version       TEXT    NOT NULL,
            enabled       INTEGER NOT NULL DEFAULT 0,
            installed_at  TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        )
        """,
    ),
]


def caminho_bd() -> Path:
    """Caminho do arquivo de banco de dados em uso."""
    return caminho_banco()


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Abre uma conexão com commit automático e fecho garantido."""
    conexao = sqlite3.connect(caminho_bd())
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _aplicar_migracoes(conexao: sqlite3.Connection) -> None:
    versao_atual = conexao.execute("PRAGMA user_version").fetchone()[0]
    for indice, comandos in enumerate(_MIGRACOES, start=1):
        if versao_atual >= indice:
            continue
        logger.info("Aplicando migração de banco v%d", indice)
        for comando in comandos:
            conexao.execute(comando)
        conexao.execute(f"PRAGMA user_version = {indice}")
    conexao.commit()


def criar_tabela() -> None:
    """Garante que o banco existe e está no schema mais recente."""
    with conectar() as conexao:
        _aplicar_migracoes(conexao)


def adicionar_tarefa(descricao: str, data_vencimento: Optional[str] = None) -> int:
    """Insere uma tarefa e devolve o seu ``id``.

    Raises:
        ValueError: se a descrição estiver vazia.
    """
    descricao = (descricao or "").strip()
    if not descricao:
        raise ValueError("A descrição da tarefa não pode estar vazia.")

    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, criada_em)"
            " VALUES (?, ?, 0, ?)",
            (descricao, data_vencimento, datetime.now().isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)


def buscar_tarefas(incluir_concluidas: bool = True) -> List[tuple]:
    """Devolve as tarefas como tuplas ``(id, descrição, vencimento, concluída, criada_em)``."""
    consulta = "SELECT id, descricao, data_vencimento, concluida, criada_em FROM tarefas"
    if not incluir_concluidas:
        consulta += " WHERE concluida = 0"
    consulta += " ORDER BY concluida ASC, id ASC"
    with conectar() as conexao:
        return conexao.execute(consulta).fetchall()


def obter_tarefa(tarefa_id: int) -> Optional[tuple]:
    """Devolve uma tarefa pelo ``id``, ou ``None`` se não existir."""
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, descricao, data_vencimento, concluida, criada_em"
            " FROM tarefas WHERE id = ?",
            (tarefa_id,),
        ).fetchone()


def concluir_tarefa(tarefa_id: int, concluida: bool = True) -> bool:
    """Marca (ou desmarca) uma tarefa como concluída. Devolve se algo mudou."""
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE tarefas SET concluida = ? WHERE id = ?",
            (1 if concluida else 0, tarefa_id),
        )
        return cursor.rowcount > 0


def remover_tarefa(tarefa_id: int) -> bool:
    """Remove uma tarefa. Devolve ``True`` se a tarefa existia."""
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))
        return cursor.rowcount > 0


def tarefas_por_data(data_iso: str) -> List[tuple]:
    """Tarefas cujo vencimento é exatamente ``data_iso`` (``AAAA-MM-DD``)."""
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, descricao, data_vencimento, concluida, criada_em"
            " FROM tarefas WHERE data_vencimento = ? ORDER BY concluida ASC, id ASC",
            (data_iso,),
        ).fetchall()
