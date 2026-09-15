"""Regras de acesso às tarefas.

O armazenamento (:mod:`banco_de_dados`) não sabe quem está a usar a aplicação, e a
interface não deve decidir quem vê o quê. A política vive aqui, num sítio só,
e **todos** os caminhos passam por ela: a janela, os plugins e a análise.

A regra:

* quem tem ``tarefas.ver_todas`` vê e edita tudo;
* quem não tem vê e edita as suas — e as que não têm dono, criadas antes de
  existirem contas, que não pertencem a mais ninguém;
* escrever exige ``tarefas.escrever``, ver exige ``tarefas.ler``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import banco_de_dados
from core import organizacao, permissoes
from core.log import obter_logger
from core.permissoes import Permissao, PermissaoNegadaError

logger = obter_logger(__name__)


def garantir_esquema() -> None:
    """Cria as tabelas se ainda não existirem.

    Quem usa as tarefas pede-o ao serviço; o armazenamento é assunto daqui
    para dentro. É o mesmo padrão defensivo da auditoria e das contas.
    """
    banco_de_dados.criar_tabela()


def utilizador_atual() -> str:
    """Quem está em sessão."""
    return permissoes.sessao().utilizador


def ve_tudo() -> bool:
    """Se a sessão atual vê as tarefas de toda a gente."""
    return permissoes.pode(Permissao.TAREFAS_VER_TODAS)


def ve_a_unidade() -> bool:
    """Se a sessão atual vê as tarefas da sua unidade e das de baixo."""
    return permissoes.pode(Permissao.TAREFAS_VER_UNIDADE)


def unidade_atual() -> Optional[int]:
    """A unidade de quem está em sessão, se tiver alguma."""
    from core import utilizadores

    conta = utilizadores.obter(utilizador_atual())
    return conta.unidade_id if conta else None


@dataclass(frozen=True)
class Ambito:
    """O que a sessão alcança.

    ``dono=None`` é "tudo". Caso contrário são as próprias (e as sem dono),
    mais as ``unidades`` — a relação é **ou**, não **e**: um chefe vê o que
    faz *e* o que a sua equipa faz.
    """

    dono: Optional[str] = None
    unidades: Sequence[int] = ()

    @property
    def ve_tudo(self) -> bool:
        return self.dono is None


def ambito() -> Ambito:
    """O âmbito da sessão atual — o único sítio onde isto se decide.

    Três casos, por ordem de alcance:

    * quem tem ``tarefas.ver_todas`` não tem filtro nenhum;
    * quem tem ``tarefas.ver_unidade`` vê as suas e as da sua sub-árvore.
      Sem unidade atribuída, a sub-árvore é vazia e sobra o caso seguinte —
      é o que mantém quem ainda não montou estrutura exatamente como estava;
    * os restantes veem as suas e as que não têm dono.
    """
    if ve_tudo():
        return Ambito()

    eu = utilizador_atual()
    if not ve_a_unidade():
        return Ambito(dono=eu)

    minha = unidade_atual()
    if minha is None:
        return Ambito(dono=eu)
    return Ambito(dono=eu, unidades=[u.id for u in organizacao.descendentes(minha)])


def visibilidade() -> Optional[str]:
    """Filtro de dono a aplicar: ``None`` quando não há filtro."""
    return ambito().dono


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
    alcance = Ambito(dono=utilizador_atual()) if apenas_minhas else ambito()
    return banco_de_dados.buscar_tarefas(
        incluir_concluidas=incluir_concluidas,
        de=alcance.dono,
        unidades=alcance.unidades,
    )


def listar_por_data(data_iso: str, apenas_minhas: bool = False) -> List[tuple]:
    """Tarefas visíveis com vencimento na data indicada."""
    _exigir_leitura()
    alcance = Ambito(dono=utilizador_atual()) if apenas_minhas else ambito()
    return banco_de_dados.tarefas_por_data(
        data_iso, de=alcance.dono, unidades=alcance.unidades
    )


def listar_completas(apenas_minhas: bool = False) -> List[tuple]:
    """Tarefas visíveis com todas as colunas (usada pela análise)."""
    _exigir_leitura()
    alcance = Ambito(dono=utilizador_atual()) if apenas_minhas else ambito()
    return banco_de_dados.buscar_tarefas_completas(
        de=alcance.dono, unidades=alcance.unidades
    )


def obter(tarefa_id: int) -> Optional[tuple]:
    """Uma tarefa, se a sessão a puder ver."""
    _exigir_leitura()
    tarefa = banco_de_dados.obter_tarefa(tarefa_id)
    if tarefa is None or not pode_ver(tarefa_id):
        return None
    return tarefa


def dono(tarefa_id: int) -> Optional[str]:
    """Quem criou a tarefa (``""`` se foi criada antes das contas)."""
    return banco_de_dados.dono_de(tarefa_id)


def pode_ver(tarefa_id: int) -> bool:
    """Se a sessão atual pode ver esta tarefa.

    Responde pelo mesmo âmbito que :func:`listar` usa: uma tarefa que aparece
    na lista tem de poder ser aberta, e uma que não aparece não.
    """
    criador = banco_de_dados.dono_de(tarefa_id)
    if criador is None:
        return False

    alcance = ambito()
    if alcance.ve_tudo:
        return True
    if criador in (alcance.dono, banco_de_dados.SEM_DONO):
        return True
    return bool(alcance.unidades) and banco_de_dados.unidade_de(tarefa_id) in alcance.unidades


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
    return banco_de_dados.adicionar_tarefa(
        descricao,
        data_vencimento,
        criada_por=utilizador_atual(),
        unidade_id=unidade_atual(),
    )


def concluir(tarefa_id: int, concluida: bool = True) -> bool:
    """Marca ou desmarca uma tarefa como concluída."""
    _exigir_edicao(tarefa_id)
    return banco_de_dados.concluir_tarefa(tarefa_id, concluida)


def remover(tarefa_id: int) -> bool:
    """Remove uma tarefa."""
    _exigir_edicao(tarefa_id)
    return banco_de_dados.remover_tarefa(tarefa_id)


def contar_por_dono() -> List[Tuple[str, int]]:
    """Quantas tarefas tem cada pessoa, para quem vê tudo."""
    _exigir_leitura()
    if not ve_tudo():
        return [(utilizador_atual(), len(listar()))]
    contagem: dict = {}
    for linha in banco_de_dados.buscar_tarefas_completas():
        criador = linha[6] or banco_de_dados.SEM_DONO
        contagem[criador] = contagem.get(criador, 0) + 1
    return sorted(contagem.items())
