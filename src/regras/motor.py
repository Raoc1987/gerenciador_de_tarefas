"""O motor: liga o que aconteceu ao que fazer.

A parte difícil de um motor de regras não é executar ações. É **não se comer a
si próprio**. Uma regra "quando uma tarefa é criada, cria uma tarefa" é fácil
de escrever sem dar por isso, e sem defesa bloqueia a aplicação para sempre no
primeiro disparo — pior, com o banco a encher.

Três defesas, todas testadas:

* **profundidade máxima** — uma ação que provoca um evento corre a um nível
  abaixo, e há um limite de níveis;
* **uma regra não se repete na mesma cadeia** — se já correu nesta reação em
  cadeia, não volta a correr, mesmo por caminho indireto;
* **reagir a tudo é recusado** ao guardar a regra (ver :func:`validar_evento`).

Além disso, e pelo mesmo motivo que um plugin não derruba a aplicação: uma
ação que falha é registada e as restantes continuam. Uma automação partida não
pode impedir alguém de criar uma tarefa.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core import auditoria, eventos
from core.log import obter_logger
from regras import acoes as registo_de_acoes
from regras import repositorio
from regras.modelo import Regra

logger = obter_logger(__name__)

#: Quantos níveis de reação em cadeia se permitem.
#:
#: Cinco chega para automações reais (um evento leva a outro, que leva a
#: outro) e corta qualquer ciclo cedo. Um número maior só adia o problema.
PROFUNDIDADE_MAXIMA = 5

DONO = "regras"


@dataclass
class _Cadeia:
    """O que está a acontecer nesta reação em cadeia, nesta thread."""

    profundidade: int = 0
    regras: Set[int] = field(default_factory=set)


_local = threading.local()


def _cadeia() -> _Cadeia:
    if not hasattr(_local, "cadeia"):
        _local.cadeia = _Cadeia()
    return _local.cadeia


@dataclass
class Execucao:
    """O que aconteceu quando uma regra correu — para diagnóstico e testes."""

    regra_id: int
    regra: str
    evento: str
    acoes_corridas: int = 0
    falhas: List[str] = field(default_factory=list)

    @property
    def sucesso(self) -> bool:
        return not self.falhas


class Motor:
    """Ouve o barramento e faz correr as regras que se aplicam."""

    def __init__(self) -> None:
        self._inscricao = None
        self._historico: List[Execucao] = []

    # ------------------------------------------------------------ ligação

    def ativar(self) -> None:
        """Começa a ouvir. Chamar duas vezes não duplica a subscrição."""
        if self._inscricao is not None:
            return
        self._inscricao = eventos.subscrever("*", self._ao_acontecer, dono=DONO)
        logger.info("Motor de automação ativo.")

    def desativar(self) -> None:
        """Deixa de ouvir."""
        if self._inscricao is not None:
            eventos.barramento().cancelar(self._inscricao)
            self._inscricao = None

    def ativo(self) -> bool:
        """Se está ligado ao barramento **agora**.

        Pergunta ao barramento em vez de confiar na variável: um ``limpar()``
        do barramento cancela as subscrições sem avisar ninguém, e responder
        "sim" depois disso seria mentir.
        """
        if self._inscricao is None:
            return False
        return self._inscricao in eventos.barramento().inscricoes()

    def historico(self) -> List[Execucao]:
        """As últimas execuções, da mais recente para trás."""
        return list(reversed(self._historico))

    # ------------------------------------------------------------ execução

    def _ao_acontecer(self, evento) -> None:
        """Ponto de entrada do barramento. Nunca levanta."""
        if evento.nome.startswith("workflow."):
            # Os eventos do próprio motor não disparam regras: seriam a forma
            # mais curta de um ciclo, e não descrevem nada do negócio.
            return
        try:
            self.processar(evento.nome, dict(evento.dados))
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha a processar o evento %s.", evento.nome)

    def processar(self, nome_evento: str, dados: Dict[str, Any]) -> List[Execucao]:
        """Corre as regras que se aplicam a este evento."""
        regras = [
            regra
            for regra in repositorio.listar(apenas_ativas=True)
            if eventos.corresponde(nome_evento, regra.evento)
        ]
        if not regras:
            return []

        cadeia = _cadeia()
        if cadeia.profundidade >= PROFUNDIDADE_MAXIMA:
            self._limite_atingido(nome_evento, [r.nome for r in regras])
            return []

        execucoes: List[Execucao] = []
        cadeia.profundidade += 1
        try:
            for regra in regras:
                if regra.id in cadeia.regras:
                    # Já correu nesta cadeia: voltar a correr é o ciclo,
                    # mesmo que o caminho de volta tenha passado por outras.
                    logger.warning(
                        "Regra %r ignorada: já correu nesta reação em cadeia.", regra.nome
                    )
                    continue
                if not regra.aplica_se(dados):
                    continue

                cadeia.regras.add(regra.id)
                try:
                    execucoes.append(self._correr(regra, nome_evento, dados))
                finally:
                    cadeia.regras.discard(regra.id)
        finally:
            cadeia.profundidade -= 1

        return execucoes

    def _correr(self, regra: Regra, nome_evento: str, dados: Dict[str, Any]) -> Execucao:
        """Executa as ações de uma regra, isolando as falhas."""
        execucao = Execucao(regra.id, regra.nome, nome_evento)

        for acao in regra.acoes:
            try:
                registada = registo_de_acoes.obter(acao.nome)
                registada.funcao(dados, dict(acao.argumentos))
                execucao.acoes_corridas += 1
            except Exception as erro:
                # Uma automação partida não pode impedir alguém de criar uma
                # tarefa. O erro fica registado e a regra segue em frente.
                logger.exception("Regra %r: ação %r falhou.", regra.nome, acao.nome)
                execucao.falhas.append(f"{acao.nome}: {erro}")

        self._registar(execucao)
        return execucao

    def _registar(self, execucao: Execucao) -> None:
        self._historico.append(execucao)
        del self._historico[:-200]
        eventos.publicar(
            eventos.WORKFLOW_EXECUTADA,
            origem=DONO,
            id=execucao.regra,
            evento=execucao.evento,
            acoes=execucao.acoes_corridas,
            falhas=len(execucao.falhas),
        )

    def _limite_atingido(self, nome_evento: str, nomes: List[str]) -> None:
        """Avisa em vez de continuar a descer.

        Silêncio aqui seria pior do que o ciclo: as regras deixavam de correr
        sem ninguém perceber porquê.
        """
        logger.error(
            "Automação parada em %s: limite de %d níveis atingido (regras: %s).",
            nome_evento,
            PROFUNDIDADE_MAXIMA,
            ", ".join(nomes),
        )
        eventos.publicar(
            eventos.WORKFLOW_LIMITE,
            origem=DONO,
            id=nome_evento,
            limite=PROFUNDIDADE_MAXIMA,
            regras=", ".join(nomes),
        )


_motor: Optional[Motor] = None


def motor() -> Motor:
    """O motor da aplicação."""
    global _motor
    if _motor is None:
        _motor = Motor()
    return _motor


def ativar() -> None:
    """Liga a automação ao barramento."""
    motor().ativar()


def desativar() -> None:
    """Desliga a automação."""
    motor().desativar()


def ativa() -> bool:
    """Se a automação está a ouvir."""
    return motor().ativo()


def reiniciar() -> None:
    """Esquece o motor. Estado global: os testes têm de o repor."""
    global _motor
    if _motor is not None:
        _motor.desativar()
    _motor = None
