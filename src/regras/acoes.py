"""O que uma regra pode mandar fazer.

O motor não sabe criar tarefas nem encomendar material. Quem tem uma ação para
oferecer regista-a aqui, com um nome e uma descrição; o motor liga o que
aconteceu ao que fazer e mais nada.

É isto que permite a um módulo novo — um de compras, um de RH — participar em
automações sem tocar numa linha do motor. E é isto que impede o motor de se
tornar o sítio onde todos os domínios se encontram, que é como um Service se
transforma num monólito com outro nome.

**A ação verifica as suas próprias permissões.** O motor corre-as em nome de
quem provocou o evento, e uma ação que escreve tem de exigir o mesmo que
exigiria se alguém carregasse no botão — senão uma regra seria a forma de
fazer por automação o que não se pode fazer à mão.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)


class AcaoDesconhecidaError(KeyError):
    """A regra pede uma ação que ninguém registou."""

    chave_mensagem = "workflow_acao_desconhecida"


@dataclass(frozen=True)
class AcaoRegistada:
    """Uma ação disponível para as regras.

    Attributes:
        nome: identificador estável, usado nas regras guardadas.
        funcao: recebe ``(dados_do_evento, argumentos)`` e faz o trabalho.
        chave_descricao: chave de tradução para a interface.
        dono: quem a registou — um plugin removido leva as suas.
    """

    nome: str
    funcao: Callable[[Dict[str, Any], Dict[str, Any]], Any]
    chave_descricao: str = ""
    dono: str = ""


_REGISTO: Dict[str, AcaoRegistada] = {}


def registar(
    nome: str,
    funcao: Callable[[Dict[str, Any], Dict[str, Any]], Any],
    chave_descricao: str = "",
    dono: str = "",
) -> AcaoRegistada:
    """Disponibiliza uma ação às regras.

    Registar duas vezes o mesmo nome substitui — é o que acontece quando um
    plugin é recarregado, e falhar aí obrigaria a reiniciar a aplicação.

    Raises:
        ValueError: nome vazio ou função que não é chamável.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Uma ação precisa de um nome.")
    if not callable(funcao):
        raise ValueError(f"A ação {nome!r} não é uma função.")

    acao = AcaoRegistada(nome, funcao, chave_descricao or f"acao_{nome}", dono)
    _REGISTO[nome] = acao
    logger.info("Ação de automação registada: %s", nome)
    return acao


def esquecer(nome: str) -> bool:
    """Tira uma ação do registo."""
    return _REGISTO.pop(nome, None) is not None


def esquecer_por_dono(dono: str) -> int:
    """Tira todas as ações de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [nome for nome, acao in _REGISTO.items() if acao.dono == dono]
    for nome in saem:
        _REGISTO.pop(nome, None)
    if saem:
        logger.info("Ações de %s esquecidas: %s", dono, ", ".join(sorted(saem)))
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _REGISTO.clear()


def obter(nome: str) -> AcaoRegistada:
    """A ação registada com esse nome.

    Raises:
        AcaoDesconhecidaError: se não existir. Uma regra que aponta para uma
            ação que já não existe — porque o plugin foi removido — tem de o
            dizer, em vez de não fazer nada em silêncio.
    """
    acao = _REGISTO.get((nome or "").strip())
    if acao is None:
        disponiveis = ", ".join(sorted(_REGISTO)) or "nenhuma"
        raise AcaoDesconhecidaError(
            f"Ação desconhecida: {nome!r}. Disponíveis: {disponiveis}."
        )
    return acao


def existe(nome: str) -> bool:
    """Se a ação está registada agora."""
    return (nome or "").strip() in _REGISTO


def disponiveis() -> List[AcaoRegistada]:
    """Todas as ações registadas, por nome."""
    return [_REGISTO[nome] for nome in sorted(_REGISTO)]
