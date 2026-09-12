"""Barramento de eventos da plataforma.

É o que permite acrescentar módulos sem os ligar uns aos outros: quem cria uma
tarefa não precisa de saber que existe auditoria, notificações ou um plugin de
relatórios — publica ``tarefa.criada`` e segue.

Garantias:

* **um ouvinte com defeito não afeta os outros nem quem publicou** — a exceção
  é registada no log e a publicação continua;
* a ordem de entrega é a ordem de subscrição;
* o histórico recente fica em memória, para diagnóstico e para alimentar mais
  tarde a auditoria persistida.

Uso::

    from core import eventos

    def ao_criar(evento):
        print(evento.dados["descricao"])

    inscricao = eventos.subscrever(eventos.TAREFA_CRIADA, ao_criar)
    eventos.publicar(eventos.TAREFA_CRIADA, id=1, descricao="Comprar pão")
    eventos.cancelar(inscricao)

Padrões com ``*`` subscrevem famílias inteiras: ``"tarefa.*"`` ou ``"*"``.
"""

from __future__ import annotations

import fnmatch
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)

# ------------------------------------------------------------- catálogo

# Tarefas
TAREFA_CRIADA = "tarefa.criada"
TAREFA_ATUALIZADA = "tarefa.atualizada"
TAREFA_CONCLUIDA = "tarefa.concluida"
TAREFA_REABERTA = "tarefa.reaberta"
TAREFA_REMOVIDA = "tarefa.removida"

# Plugins
PLUGIN_INSTALADO = "plugin.instalado"
PLUGIN_ATIVADO = "plugin.ativado"
PLUGIN_DESATIVADO = "plugin.desativado"
PLUGIN_ATUALIZADO = "plugin.atualizado"
PLUGIN_REMOVIDO = "plugin.removido"
PLUGIN_ERRO = "plugin.erro"

# Sessão e contas
SESSAO_INICIADA = "sessao.iniciada"
SESSAO_TERMINADA = "sessao.terminada"
SESSAO_FALHADA = "sessao.falhada"
UTILIZADOR_CRIADO = "utilizador.criado"
UTILIZADOR_ALTERADO = "utilizador.alterado"
UTILIZADOR_REMOVIDO = "utilizador.removido"

UNIDADE_CRIADA = "unidade.criada"
UNIDADE_ALTERADA = "unidade.alterada"
UNIDADE_REMOVIDA = "unidade.removida"

FUNCIONALIDADE_ALTERADA = "funcionalidade.alterada"

WORKFLOW_EXECUTADA = "workflow.regra_executada"
WORKFLOW_LIMITE = "workflow.limite_atingido"

# Aplicação
APP_INICIADA = "app.iniciada"
APP_ENCERRADA = "app.encerrada"
IDIOMA_ALTERADO = "app.idioma_alterado"

#: Todos os eventos que o núcleo publica. Um módulo pode publicar os seus,
#: desde que use um prefixo próprio (ex.: ``estoque.item_criado``).
EVENTOS_DO_NUCLEO = (
    TAREFA_CRIADA, TAREFA_ATUALIZADA, TAREFA_CONCLUIDA, TAREFA_REABERTA,
    TAREFA_REMOVIDA, PLUGIN_INSTALADO, PLUGIN_ATIVADO, PLUGIN_DESATIVADO,
    PLUGIN_ATUALIZADO, PLUGIN_REMOVIDO, PLUGIN_ERRO, SESSAO_INICIADA,
    SESSAO_TERMINADA, SESSAO_FALHADA, UTILIZADOR_CRIADO, UTILIZADOR_ALTERADO,
    UTILIZADOR_REMOVIDO, UNIDADE_CRIADA, UNIDADE_ALTERADA, UNIDADE_REMOVIDA,
    FUNCIONALIDADE_ALTERADA, WORKFLOW_EXECUTADA, WORKFLOW_LIMITE,
    APP_INICIADA, APP_ENCERRADA, IDIOMA_ALTERADO,
)

TAMANHO_HISTORICO = 500


# --------------------------------------------------------------- modelo


@dataclass(frozen=True)
class Evento:
    """Algo que aconteceu, já em tempo passado."""

    nome: str
    dados: Dict[str, Any] = field(default_factory=dict)
    momento: str = ""
    origem: str = ""

    def __getitem__(self, chave: str) -> Any:
        return self.dados[chave]

    def obter(self, chave: str, padrao: Any = None) -> Any:
        """Valor do payload, com omissão."""
        return self.dados.get(chave, padrao)


Ouvinte = Callable[[Evento], None]


@dataclass(frozen=True)
class Inscricao:
    """Identifica uma subscrição, para a poder cancelar."""

    padrao: str
    ouvinte: Ouvinte
    dono: str = ""


class BarramentoEventos:
    """Publicação e subscrição de eventos, em memória e no mesmo processo."""

    def __init__(self, tamanho_historico: int = TAMANHO_HISTORICO) -> None:
        self._inscricoes: List[Inscricao] = []
        self._historico: Deque[Evento] = deque(maxlen=tamanho_historico)
        self._tranca = threading.RLock()

    # ------------------------------------------------------- subscrição

    def subscrever(self, padrao: str, ouvinte: Ouvinte, dono: str = "") -> Inscricao:
        """Regista um ouvinte para um evento ou família (``"tarefa.*"``).

        Args:
            padrao: nome exato ou padrão com ``*``.
            ouvinte: função que recebe o :class:`Evento`.
            dono: identificador de quem subscreveu (ex.: o id de um plugin),
                para depois se poder cancelar tudo de uma vez.
        """
        if not callable(ouvinte):
            raise TypeError("O ouvinte tem de ser invocável.")
        inscricao = Inscricao(padrao=padrao, ouvinte=ouvinte, dono=dono)
        with self._tranca:
            self._inscricoes.append(inscricao)
        logger.debug("Subscrição de %r por %r.", padrao, dono or "anónimo")
        return inscricao

    def cancelar(self, inscricao: Inscricao) -> bool:
        """Cancela uma subscrição. Devolve ``True`` se existia."""
        with self._tranca:
            try:
                self._inscricoes.remove(inscricao)
                return True
            except ValueError:
                return False

    def cancelar_por_dono(self, dono: str) -> int:
        """Cancela todas as subscrições de um dono. Devolve quantas eram.

        Usado quando um plugin é desativado: as suas subscrições saem com ele.
        """
        if not dono:
            return 0
        with self._tranca:
            restantes = [i for i in self._inscricoes if i.dono != dono]
            removidas = len(self._inscricoes) - len(restantes)
            self._inscricoes = restantes
        if removidas:
            logger.debug("Canceladas %d subscrições de %r.", removidas, dono)
        return removidas

    def subscritores(self, nome: Optional[str] = None) -> List[Inscricao]:
        """Subscrições ativas, opcionalmente as que reagem a ``nome``."""
        with self._tranca:
            if nome is None:
                return list(self._inscricoes)
            return [i for i in self._inscricoes if self._corresponde(i.padrao, nome)]

    # -------------------------------------------------------- publicação

    def publicar(self, nome: str, origem: str = "", **dados: Any) -> Evento:
        """Publica um evento e entrega-o aos ouvintes correspondentes.

        Nunca levanta por causa de um ouvinte: uma falha é registada com
        traceback e os restantes ouvintes continuam a ser chamados.
        """
        evento = Evento(
            nome=nome,
            dados=dict(dados),
            momento=datetime.now().isoformat(timespec="seconds"),
            origem=origem,
        )
        with self._tranca:
            self._historico.append(evento)
            destinatarios = [
                i for i in self._inscricoes if self._corresponde(i.padrao, nome)
            ]

        for inscricao in destinatarios:
            try:
                inscricao.ouvinte(evento)
            except Exception:
                logger.exception(
                    "Ouvinte de %r (dono=%r) falhou a tratar %s.",
                    inscricao.padrao,
                    inscricao.dono or "anónimo",
                    nome,
                )
        return evento

    # --------------------------------------------------------- histórico

    def historico(self, limite: Optional[int] = None, padrao: str = "*") -> List[Evento]:
        """Eventos recentes, do mais antigo para o mais recente."""
        with self._tranca:
            eventos = [e for e in self._historico if self._corresponde(padrao, e.nome)]
        return eventos[-limite:] if limite else eventos

    def limpar(self) -> None:
        """Esquece subscrições e histórico (usado pelos testes)."""
        with self._tranca:
            self._inscricoes.clear()
            self._historico.clear()

    @staticmethod
    def _corresponde(padrao: str, nome: str) -> bool:
        return corresponde(nome, padrao)

    def inscricoes(self) -> List[Inscricao]:
        """As subscrições ativas — para quem precise de confirmar a sua."""
        with self._tranca:
            return list(self._inscricoes)


# ------------------------------------------------- barramento da aplicação

_barramento = BarramentoEventos()


def barramento() -> BarramentoEventos:
    """O barramento partilhado pela aplicação."""
    return _barramento


def corresponde(nome: str, padrao: str) -> bool:
    """Se um nome de evento cai num padrão (``"tarefa.*"``).

    Pública de propósito: o motor de automação faz a mesma pergunta, e ter
    duas implementações da mesma regra é ter duas que acabam por discordar.
    """
    return padrao == nome or fnmatch.fnmatchcase(nome, padrao)


def subscrever(padrao: str, ouvinte: Ouvinte, dono: str = "") -> Inscricao:
    """Atalho para ``barramento().subscrever``."""
    return _barramento.subscrever(padrao, ouvinte, dono)


def cancelar(inscricao: Inscricao) -> bool:
    """Atalho para ``barramento().cancelar``."""
    return _barramento.cancelar(inscricao)


def cancelar_por_dono(dono: str) -> int:
    """Atalho para ``barramento().cancelar_por_dono``."""
    return _barramento.cancelar_por_dono(dono)


def publicar(nome: str, origem: str = "", **dados: Any) -> Evento:
    """Atalho para ``barramento().publicar``."""
    return _barramento.publicar(nome, origem, **dados)


def historico(limite: Optional[int] = None, padrao: str = "*") -> List[Evento]:
    """Atalho para ``barramento().historico``."""
    return _barramento.historico(limite, padrao)


def eventos_conhecidos() -> Iterable[str]:
    """Nomes dos eventos publicados pelo núcleo."""
    return EVENTOS_DO_NUCLEO
