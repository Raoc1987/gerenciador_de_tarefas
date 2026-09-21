"""Modelos de domínio leves.

O SQLite continua sendo a fonte de verdade nesta etapa. Este modelo isola a
interface do formato de retorno do banco e prepara uma migração futura para
SQLAlchemy sem acoplar as telas ao driver.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tarefa:
    id: int
    titulo: str
    descricao: str
    categoria: str
    prioridade: str
    status: str
    data_limite: str | None
    hora_limite: str | None
    criado_em: str
    concluido_em: str | None
