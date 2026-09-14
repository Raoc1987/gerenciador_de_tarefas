"""Onde as regras ficam guardadas.

Separado do motor: as regras são dados do utilizador, e o motor é
comportamento. Quem quiser trocar o armazenamento — um ficheiro, uma API —
troca isto e mais nada.

Uma regra malformada no banco (ficheiro editado à mão, versão anterior) é
**ignorada com registo**, não faz a aplicação falhar a arrancar. Uma regra que
não se consegue ler é uma regra que não corre, e isso é preferível a não haver
programa nenhum.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from core.log import obter_logger
from regras.modelo import Acao, Condicao, Regra, RegraInvalidaError, validar_evento

logger = obter_logger(__name__)

_COLUNAS = "id, nome, evento, condicoes, acoes, ativa, criada_em, criada_por"


def _conectar():
    import database

    database.criar_tabela()
    return database.conectar()


def _para_regra(linha) -> Optional[Regra]:
    """Converte uma linha em regra, ou ``None`` se não for legível."""
    try:
        condicoes = tuple(Condicao.de_dicionario(c) for c in json.loads(linha[3]))
        acoes = tuple(Acao.de_dicionario(a) for a in json.loads(linha[4]))
    except (json.JSONDecodeError, RegraInvalidaError, TypeError) as erro:
        logger.warning("Regra %s ignorada: %s", linha[0], erro)
        return None

    return Regra(
        id=linha[0],
        nome=linha[1],
        evento=linha[2],
        condicoes=condicoes,
        acoes=acoes,
        ativa=bool(linha[5]),
        criada_em=linha[6],
        criada_por=linha[7],
    )


def listar(apenas_ativas: bool = False) -> List[Regra]:
    """As regras guardadas, por nome."""
    consulta = f"SELECT {_COLUNAS} FROM regras"
    if apenas_ativas:
        consulta += " WHERE ativa = 1"
    consulta += " ORDER BY nome COLLATE NOCASE"

    with _conectar() as conexao:
        linhas = conexao.execute(consulta).fetchall()
    return [regra for regra in (_para_regra(l) for l in linhas) if regra is not None]


def obter(regra_id: int) -> Optional[Regra]:
    with _conectar() as conexao:
        linha = conexao.execute(
            f"SELECT {_COLUNAS} FROM regras WHERE id = ?", (regra_id,)
        ).fetchone()
    return _para_regra(linha) if linha else None


def criar(
    nome: str,
    evento: str,
    condicoes: Iterable[Condicao] = (),
    acoes: Iterable[Acao] = (),
    criada_por: str = "",
    ativa: bool = True,
) -> Regra:
    """Guarda uma regra nova.

    Raises:
        RegraInvalidaError: nome vazio, evento inválido, ou nenhuma ação —
            uma regra que não faz nada é sempre um engano por acabar.
    """
    nome = (nome or "").strip()
    if not nome:
        raise RegraInvalidaError("A regra precisa de um nome.")
    evento = validar_evento(evento)

    acoes = tuple(acoes)
    if not acoes:
        raise RegraInvalidaError("A regra precisa de pelo menos uma ação.")

    agora = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO regras (nome, evento, condicoes, acoes, ativa, criada_em,"
            " criada_por) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                nome,
                evento,
                json.dumps([c.para_dicionario() for c in condicoes], ensure_ascii=False),
                json.dumps([a.para_dicionario() for a in acoes], ensure_ascii=False),
                1 if ativa else 0,
                agora,
                criada_por,
            ),
        )
        novo = cursor.lastrowid

    logger.info("Regra criada: %s (quando %s)", nome, evento)
    return obter(novo)


def definir_ativa(regra_id: int, ativa: bool = True) -> bool:
    """Liga ou desliga uma regra sem a apagar."""
    with _conectar() as conexao:
        alteradas = conexao.execute(
            "UPDATE regras SET ativa = ? WHERE id = ?", (1 if ativa else 0, regra_id)
        ).rowcount
    return alteradas > 0


def remover(regra_id: int) -> bool:
    with _conectar() as conexao:
        return conexao.execute("DELETE FROM regras WHERE id = ?", (regra_id,)).rowcount > 0
