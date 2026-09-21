"""Onde as partes que vêm com a aplicação vivem na barra lateral.

A ligação fina entre :mod:`navegacao`, que não conhece o produto, e as
secções que a aplicação traz. Um módulo de negócio declara a sua pelo
contexto do plugin, sem passar por aqui.

O nome de cada destino é a **chave de tradução** do título da secção: é por
aí que a concha as junta, porque é o que já lá estava — ``notebook.add`` só
recebe o texto. Ligar pelo texto traduzido partia ao mudar de idioma; ligar
pela chave não.
"""

from __future__ import annotations

from core.log import obter_logger
from navegacao import registar

logger = obter_logger(__name__)


def registar_incluidos() -> None:
    """Põe no registo as secções que vêm com a aplicação.

    Idempotente: o registo é por id.
    """
    registar("painel", chave_titulo="Dashboard", grupo="principal",
             marca="▣", ordem=10, funcionalidade="painel")
    registar("tarefas", chave_titulo="Tarefas", grupo="principal",
             marca="✓", ordem=20, permissao="tarefas.ler")
