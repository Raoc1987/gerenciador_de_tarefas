"""O que esta aplicação sabe procurar.

A ligação entre :mod:`pesquisa`, que não conhece domínios, e os domínios que
existem. Um módulo de negócio regista as suas fontes do mesmo modo, sem passar
por aqui — este ficheiro é só para o que vem de origem.

**Cada fonte passa pela camada que aplica as permissões**, e não pelo banco.
É aí que está a defesa: a pesquisa devolve o que as fontes lhe derem, por isso
uma fonte que consulte o armazenamento diretamente mostrava a quem procura
aquilo que a aplicação lhe esconde noutro sítio. Um colaborador que procure
"orçamento" não pode ver a tarefa do colega por causa disso.
"""

from __future__ import annotations

from typing import List, Sequence

import pesquisa
from core.log import obter_logger
from pesquisa import Resultado, contem

logger = obter_logger(__name__)


def _tarefas(termo: str, limite: int) -> List[Resultado]:
    """Tarefas visíveis para a sessão — o âmbito vem do serviço."""
    import tarefas_servico

    encontradas = []
    for tarefa in tarefas_servico.listar():
        identificador, descricao, vencimento, concluida = tarefa[0], tarefa[1], tarefa[2], tarefa[3]
        if not contem(descricao, termo):
            continue
        estado = "concluída" if concluida else (vencimento or "sem prazo")
        encontradas.append(
            Resultado("tarefas", descricao, str(estado), str(identificador))
        )
        if len(encontradas) >= limite:
            break
    return encontradas


def _unidades(termo: str, limite: int) -> List[Resultado]:
    """Unidades da estrutura, com o caminho como contexto."""
    from core import organizacao

    encontradas = []
    for unidade in organizacao.listar(incluir_inativas=True):
        if not contem(unidade.nome, termo):
            continue
        encontradas.append(
            Resultado(
                "unidades",
                unidade.nome,
                organizacao.caminho(unidade.id),
                str(unidade.id),
            )
        )
        if len(encontradas) >= limite:
            break
    return encontradas


def _contas(termo: str, limite: int) -> List[Resultado]:
    """Contas — só para quem as pode gerir.

    Sem esta verificação, a pesquisa dizia a toda a gente que contas existem
    na instalação, o que a janela de contas não diz.
    """
    from core import permissoes, utilizadores
    from core.permissoes import Permissao

    if not permissoes.pode(Permissao.UTILIZADORES_GERIR):
        return []

    encontradas = []
    for conta in utilizadores.listar():
        if not (contem(conta.nome_utilizador, termo) or contem(conta.nome, termo)):
            continue
        encontradas.append(
            Resultado(
                "contas",
                conta.apresentacao,
                conta.papel_nome,
                conta.nome_utilizador,
            )
        )
        if len(encontradas) >= limite:
            break
    return encontradas


def _regras(termo: str, limite: int) -> List[Resultado]:
    """Regras de automação — só para quem administra a instalação."""
    from core import permissoes
    from core.permissoes import Permissao
    from regras import repositorio

    if not permissoes.pode(Permissao.SISTEMA_ADMIN):
        return []

    encontradas = []
    for regra in repositorio.listar():
        if not (contem(regra.nome, termo) or contem(regra.evento, termo)):
            continue
        encontradas.append(
            Resultado("regras", regra.nome, f"quando {regra.evento}", str(regra.id))
        )
        if len(encontradas) >= limite:
            break
    return encontradas


def registar_incluidas() -> None:
    """Põe no registo as fontes que vêm com a aplicação.

    Chamado no arranque. Registar duas vezes substitui, por isso é seguro.
    """
    pesquisa.registar("tarefas", _tarefas, "pesquisa_fonte_tarefas")
    pesquisa.registar("unidades", _unidades, "pesquisa_fonte_unidades")
    pesquisa.registar("contas", _contas, "pesquisa_fonte_contas")
    pesquisa.registar("regras", _regras, "pesquisa_fonte_regras")
