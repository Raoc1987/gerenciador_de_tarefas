"""As ações que esta aplicação oferece às regras de automação.

O motor (:mod:`regras`) não conhece tarefas. Este módulo é a ligação entre
os dois: sabe o que a aplicação faz e regista isso no catálogo de ações. Um
módulo de negócio regista as suas do mesmo modo, sem passar por aqui.

É deliberadamente fino. Se começar a crescer, é sinal de que o motor está a
ganhar domínio pela porta das traseiras.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from core.log import obter_logger
from regras import acoes

logger = obter_logger(__name__)

#: Só letras, dígitos e ``_`` entre chavetas. Nada de pontos nem índices.
_CAMPO = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def preencher(modelo: str, dados: Dict[str, Any]) -> str:
    """Substitui ``{campo}`` pelos dados do evento.

    Escrito à mão em vez de ``str.format`` pela mesma razão que não há
    ``eval`` na calculadora: ``"{0.__class__}".format(x)`` navega dentro dos
    objetos, e o modelo aqui vem de uma regra guardada no banco — texto que
    alguém pode alterar. Isto só troca nomes simples por valores, e um campo
    que não existe fica como está, para se ver o que faltou em vez de rebentar.
    """
    def trocar(achado: re.Match) -> str:
        nome = achado.group(1)
        return str(dados[nome]) if nome in dados else achado.group(0)

    return _CAMPO.sub(trocar, str(modelo or ""))


def _criar_tarefa(dados: Dict[str, Any], argumentos: Dict[str, Any]) -> int:
    """Cria uma tarefa a partir de um evento.

    Argumentos da regra:
        descricao: texto, com ``{campo}`` a ser trocado pelos dados do evento.
        vencimento: data ``AAAA-MM-DD``, opcional.

    A criação passa por :mod:`tarefas_servico`, com as permissões de quem está
    em sessão — uma regra não é uma forma de fazer por automação o que não se
    pode fazer à mão.
    """
    import tarefas_servico

    descricao = preencher(argumentos.get("descricao", ""), dados).strip()
    if not descricao:
        raise ValueError("A ação 'tarefa.criar' precisa de uma descrição.")

    vencimento = argumentos.get("vencimento") or None
    if vencimento:
        vencimento = preencher(str(vencimento), dados).strip() or None

    return tarefas_servico.adicionar(descricao, vencimento)


def _registar_no_log(dados: Dict[str, Any], argumentos: Dict[str, Any]) -> None:
    """Escreve uma linha no registo — útil para experimentar uma regra.

    Sem esta, a única forma de ver se uma regra dispara era deixá-la criar
    tarefas a sério.
    """
    logger.info("Automação: %s", preencher(argumentos.get("texto", "{id}"), dados))


def registar_incluidas() -> None:
    """Põe no catálogo as ações que vêm com a aplicação.

    Chamado no arranque. Registar duas vezes substitui, por isso é seguro.
    """
    acoes.registar(
        "tarefa.criar", _criar_tarefa, chave_descricao="acao_tarefa_criar"
    )
    acoes.registar(
        "registar", _registar_no_log, chave_descricao="acao_registar"
    )
