"""Regras de acesso às tarefas.

O armazenamento (:mod:`database`) não sabe quem está a usar a aplicação, e a
interface não deve decidir quem vê o quê. A política vive aqui, num sítio só,
e **todos** os caminhos passam por ela: a janela, os plugins e a análise.

A regra:

* quem tem ``tarefas.ver_todas`` vê e edita tudo;
* quem não tem vê e edita as suas — e as que não têm dono, criadas antes de
  existirem contas, que não pertencem a mais ninguém;
* escrever exige ``tarefas.escrever``, ver exige ``tarefas.ler``.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import database
from core import permissoes
from core.log import obter_logger
from core.permissoes import Permissao, PermissaoNegadaError

logger = obter_logger(__name__)


def utilizador_atual() -> str:
    """Quem está em sessão."""
    return permissoes.sessao().utilizador


def ve_tudo() -> bool:
    """Se a sessão atual vê as tarefas de toda a gente."""
    return permissoes.pode(Permissao.TAREFAS_VER_TODAS)


def visibilidade() -> Optional[str]:
    """Filtro de dono a aplicar: ``None`` quando não há filtro."""
    return None if ve_tudo() else utilizador_atual()


def _exigir_leitura() -> None:
    permissoes.exigir(Permissao.TAREFAS_LER)


def _exigir_escrita() -> None:
    permissoes.exigir(Permissao.TAREFAS_ESCREVER)


# ----------------------------------------------------------------- leitura


def listar(incluir_concluidas: bool = True, apenas_minhas: bool = False) -> List[tuple]:
    """Tarefas visíveis para a sessão atual.

    Args:
        apenas_minhas: restringe às próprias, mesmo para quem vê tudo — é o
            filtro que o utilizador escolhe na interface.
    """
    _exigir_leitura()
    dono = utilizador_atual() if apenas_minhas else visibilidade()
    return database.buscar_tarefas(incluir_concluidas=incluir_concluidas, de=dono)


def listar_por_data(data_iso: str, apenas_minhas: bool = False) -> List[tuple]:
    """Tarefas visíveis com vencimento na data indicada."""
    _exigir_leitura()
    dono = utilizador_atual() if apenas_minhas else visibilidade()
    return database.tarefas_por_data(data_iso, de=dono)


def listar_completas(apenas_minhas: bool = False) -> List[tuple]:
    """Tarefas visíveis com todas as colunas (usada pela análise)."""
    _exigir_leitura()
    dono = utilizador_atual() if apenas_minhas else visibilidade()
    return database.buscar_tarefas_completas(de=dono)


def obter(tarefa_id: int) -> Optional[tuple]:
    """Uma tarefa, se a sessão a puder ver."""
    _exigir_leitura()
    tarefa = database.obter_tarefa(tarefa_id)
    if tarefa is None or not pode_ver(tarefa_id):
        return None
    return tarefa


def dono(tarefa_id: int) -> Optional[str]:
    """Quem criou a tarefa (``""`` se foi criada antes das contas)."""
    return database.dono_de(tarefa_id)


def pode_ver(tarefa_id: int) -> bool:
    """Se a sessão atual pode ver esta tarefa."""
    if ve_tudo():
        return database.dono_de(tarefa_id) is not None
    criador = database.dono_de(tarefa_id)
    return criador in (utilizador_atual(), database.SEM_DONO)


def pode_editar(tarefa_id: int) -> bool:
    """Se a sessão atual pode alterar esta tarefa."""
    return permissoes.pode(Permissao.TAREFAS_ESCREVER) and pode_ver(tarefa_id)


def _exigir_edicao(tarefa_id: int) -> None:
    _exigir_escrita()
    if not pode_ver(tarefa_id):
        logger.warning(
            "%s tentou alterar a tarefa %s, de outra pessoa.",
            utilizador_atual(),
            tarefa_id,
        )
        raise PermissaoNegadaError(Permissao.TAREFAS_VER_TODAS)


# ------------------------------------------------------------------ escrita


def adicionar(descricao: str, data_vencimento: Optional[str] = None) -> int:
    """Cria uma tarefa em nome de quem está em sessão."""
    _exigir_escrita()
    return database.adicionar_tarefa(
        descricao, data_vencimento, criada_por=utilizador_atual()
    )


def concluir(tarefa_id: int, concluida: bool = True) -> bool:
    """Marca ou desmarca uma tarefa como concluída."""
    _exigir_edicao(tarefa_id)
    return database.concluir_tarefa(tarefa_id, concluida)


def remover(tarefa_id: int) -> bool:
    """Remove uma tarefa."""
    _exigir_edicao(tarefa_id)
    return database.remover_tarefa(tarefa_id)


def contar_por_dono() -> List[Tuple[str, int]]:
    """Quantas tarefas tem cada pessoa, para quem vê tudo."""
    _exigir_leitura()
    if not ve_tudo():
        return [(utilizador_atual(), len(listar()))]
    contagem: dict = {}
    for linha in database.buscar_tarefas_completas():
        criador = linha[6] or database.SEM_DONO
        contagem[criador] = contagem.get(criador, 0) + 1
    return sorted(contagem.items())
