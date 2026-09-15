"""Trilha de auditoria: o que aconteceu, quando e por quem.

Consome o barramento de eventos e grava no banco. Nenhum módulo precisa de
saber que a auditoria existe — é essa a razão de o barramento existir.

Decisões que valem a pena explicar:

* **Só se regista o que é auditável.** Uma lista explícita de eventos, não
  tudo o que passa: um registo cheio de ruído não se lê.
* **Não se guarda o conteúdo das tarefas.** O que importa é que a tarefa 12
  foi removida e quando — não o que dizia. Menos dados sensíveis guardados,
  menos problemas.
* **Falhar a registar nunca interrompe o utilizador.** Um erro de escrita vai
  para o log da aplicação e a ação segue.
* **A auditoria não se apaga pela interface.** Só a retenção programada
  remove registos, e diz quantos removeu.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core import eventos
from core.eventos import Evento
from core.log import obter_logger

logger = obter_logger(__name__)

DONO = "auditoria"

#: Eventos registados, e o que se guarda de cada um como "alvo".
#: Um evento que não esteja aqui não vai para a trilha.
EVENTOS_AUDITAVEIS: Dict[str, str] = {
    eventos.TAREFA_CRIADA: "id",
    eventos.TAREFA_CONCLUIDA: "id",
    eventos.TAREFA_REABERTA: "id",
    eventos.TAREFA_REMOVIDA: "id",
    eventos.PLUGIN_INSTALADO: "id",
    eventos.PLUGIN_ATIVADO: "id",
    eventos.PLUGIN_DESATIVADO: "id",
    eventos.PLUGIN_ATUALIZADO: "id",
    eventos.PLUGIN_REMOVIDO: "id",
    eventos.PLUGIN_ERRO: "id",
    eventos.SESSAO_INICIADA: "id",
    eventos.SESSAO_TERMINADA: "id",
    eventos.SESSAO_FALHADA: "id",
    eventos.UTILIZADOR_CRIADO: "id",
    eventos.UTILIZADOR_ALTERADO: "id",
    eventos.UTILIZADOR_REMOVIDO: "id",
    # Mexer na estrutura da empresa muda quem vê o quê: fica registado.
    eventos.UNIDADE_CRIADA: "id",
    eventos.UNIDADE_ALTERADA: "id",
    eventos.UNIDADE_REMOVIDA: "id",
    # Ligar ou desligar uma parte do produto muda o que toda a gente vê.
    eventos.FUNCIONALIDADE_ALTERADA: "id",
    # Uma automação que correu fez alguma coisa em nome de alguém: fica na
    # trilha, senão haveria alterações sem autor aparente.
    # Um alerta é uma afirmação da aplicação sobre o trabalho de alguém: fica
    # registado quando foi feita, e quando deixou de se aplicar.
    eventos.ANALISE_ALERTA: "id",
    eventos.ANALISE_RESOLVIDO: "id",
    eventos.WORKFLOW_EXECUTADA: "id",
    eventos.WORKFLOW_LIMITE: "id",
    eventos.APP_INICIADA: "",
    eventos.APP_ENCERRADA: "",
}

#: Campos do payload que podem ser guardados como detalhe, por evento.
_DETALHES = {
    # "proveniencia" responde à pergunta que uma trilha de auditoria tem de
    # responder sobre uma substituição: foi a aplicação a repor um plugin seu,
    # ou foi alguém a instalar um pacote? (ADR-0006)
    eventos.PLUGIN_INSTALADO: ("versao", "proveniencia"),
    eventos.PLUGIN_ATUALIZADO: ("versao", "versao_anterior", "proveniencia"),
    eventos.PLUGIN_ERRO: ("erro",),
    eventos.PLUGIN_REMOVIDO: ("dados_removidos",),
    # Nunca "senha": o detalhe diz o que mudou, não o valor.
    eventos.SESSAO_INICIADA: ("papel",),
    eventos.SESSAO_FALHADA: ("motivo", "tentativas"),
    eventos.UTILIZADOR_CRIADO: ("papel",),
    eventos.UTILIZADOR_ALTERADO: ("alteracao",),
}

#: Que campos podem ter o valor **antes e depois** guardado, por evento.
#:
#: É a mesma defesa do ``_DETALHES``, e pela mesma razão: não basta quem
#: publica mandar um ``antes``/``depois``: o campo tem de constar aqui. Sem
#: esta lista, um publicador distraído punha o conteúdo de uma tarefa — ou
#: uma senha — na trilha, e a auditoria passava a ser a maior fuga de dados
#: da aplicação.
#:
#: Repare no que **não** está: nada de tarefas. Que a tarefa 12 foi concluída
#: é um facto auditável; o que ela dizia não é assunto da trilha.
_ALTERACOES = {
    eventos.UTILIZADOR_ALTERADO: ("papel", "unidade", "ativo"),
    eventos.UNIDADE_ALTERADA: ("nome", "pai_id", "ativa"),
    eventos.FUNCIONALIDADE_ALTERADA: ("ligada",),
}

#: Corte do detalhe, para um traceback não inchar a tabela.
LIMITE_DETALHE = 500


@dataclass(frozen=True)
class RegistoAuditoria:
    """Uma linha da trilha."""

    id: int
    momento: str
    evento: str
    utilizador: str
    alvo: str
    detalhe: str
    origem: str
    antes: Dict[str, Any] = field(default_factory=dict)
    depois: Dict[str, Any] = field(default_factory=dict)

    def mudancas(self) -> List[Tuple[str, Any, Any]]:
        """Os campos que mudaram, com o valor de cada lado.

        Só os que **mudaram mesmo**: repetir um valor igual dos dois lados
        obrigava quem lê a comparar tudo à vista para encontrar o que
        interessa.
        """
        campos = sorted(set(self.antes) | set(self.depois))
        return [
            (campo, self.antes.get(campo), self.depois.get(campo))
            for campo in campos
            if self.antes.get(campo) != self.depois.get(campo)
        ]

    def resumo_da_mudanca(self) -> str:
        """As mudanças em texto: ``papel: colaborador -> gestor``."""
        return "; ".join(
            f"{campo}: {_legivel(antes)} -> {_legivel(depois)}"
            for campo, antes, depois in self.mudancas()
        )

    @property
    def quando(self) -> Optional[datetime]:
        """O momento como ``datetime``, se for legível."""
        try:
            return datetime.fromisoformat(self.momento)
        except (TypeError, ValueError):  # pragma: no cover - defensivo
            return None


def _utilizador_atual() -> str:
    from core import permissoes

    try:
        return permissoes.sessao().utilizador
    except Exception:  # pragma: no cover - defensivo
        return ""


def _para_registo(linha) -> RegistoAuditoria:
    """Converte uma linha do banco num registo.

    Um JSON ilegível — de uma versão anterior, ou de um ficheiro mexido à mão
    — vale objeto vazio. Uma trilha que não abre por causa de uma linha má é
    pior do que uma linha sem detalhe.
    """
    def ler(bruto) -> Dict[str, Any]:
        try:
            valor = json.loads(bruto or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}
        return valor if isinstance(valor, dict) else {}

    return RegistoAuditoria(*linha[:7], antes=ler(linha[7]), depois=ler(linha[8]))


def _legivel(valor: Any) -> str:
    """Um valor como se escreve num relatório, não como se imprime em Python."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    return str(valor)


def _alteracoes_de(evento: Evento) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """O antes e o depois, reduzidos aos campos que este evento pode guardar."""
    permitidos = _ALTERACOES.get(evento.nome, ())
    if not permitidos:
        return {}, {}

    def filtrar(chave: str) -> Dict[str, Any]:
        bruto = evento.obter(chave) or {}
        if not isinstance(bruto, dict):
            logger.warning("%s: %r devia ser um objeto.", evento.nome, chave)
            return {}
        return {c: bruto[c] for c in permitidos if c in bruto}

    return filtrar("antes"), filtrar("depois")


def _detalhe_de(evento: Evento) -> str:
    campos = _DETALHES.get(evento.nome, ())
    partes = []
    for campo in campos:
        valor = evento.obter(campo)
        if valor not in (None, ""):
            partes.append(f"{campo}={valor}")
    return "; ".join(partes)[:LIMITE_DETALHE]


def registar(evento: Evento) -> bool:
    """Grava um evento na trilha. Devolve se chegou a gravar.

    Nunca levanta: a auditoria é importante, mas não ao ponto de impedir o
    utilizador de trabalhar.
    """
    if evento.nome not in EVENTOS_AUDITAVEIS:
        return False

    import banco_de_dados

    campo_alvo = EVENTOS_AUDITAVEIS[evento.nome]
    alvo = str(evento.obter(campo_alvo, "")) if campo_alvo else ""

    try:
        banco_de_dados.criar_tabela()
        with banco_de_dados.conectar() as conexao:
            conexao.execute(
                "INSERT INTO auditoria (momento, evento, utilizador, alvo, detalhe,"
                " origem, antes, depois) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    evento.momento or datetime.now().isoformat(timespec="seconds"),
                    evento.nome,
                    _utilizador_atual(),
                    alvo,
                    _detalhe_de(evento),
                    evento.origem,
                    *(
                        json.dumps(lado, ensure_ascii=False, default=str)[:LIMITE_DETALHE]
                        for lado in _alteracoes_de(evento)
                    ),
                ),
            )
        return True
    except Exception:
        logger.exception("Falha ao registar o evento %s na auditoria.", evento.nome)
        return False


_inscricao = None


def ativa() -> bool:
    """Se a auditoria está mesmo a registar.

    Verifica a subscrição no barramento em vez de confiar numa variável: a
    variável pode ficar a dizer "ativa" depois de o barramento ter sido
    reposto, e a auditoria estaria calada sem ninguém dar por isso.
    """
    return _inscricao is not None and _inscricao in eventos.barramento().subscritores()


def ativar() -> bool:
    """Liga a auditoria ao barramento. Idempotente."""
    global _inscricao
    if ativa():
        return False
    _inscricao = eventos.subscrever("*", registar, dono=DONO)
    logger.info("Auditoria ativa (%d eventos auditáveis).", len(EVENTOS_AUDITAVEIS))
    return True


def desativar() -> bool:
    """Desliga a auditoria do barramento."""
    global _inscricao
    if _inscricao is None:
        return False
    eventos.cancelar(_inscricao)
    _inscricao = None
    return True


def consultar(
    limite: int = 200,
    evento: str = "",
    utilizador: str = "",
    desde: Optional[datetime] = None,
) -> List[RegistoAuditoria]:
    """Lê a trilha, do mais recente para o mais antigo.

    Args:
        limite: número máximo de registos.
        evento: filtra por nome exato, ou por prefixo terminado em ``*``.
        utilizador: filtra por utilizador.
        desde: só registos a partir deste momento.
    """
    import banco_de_dados

    condicoes = []
    parametros: List = []

    if evento:
        if evento.endswith("*"):
            condicoes.append("evento LIKE ?")
            parametros.append(evento[:-1] + "%")
        else:
            condicoes.append("evento = ?")
            parametros.append(evento)
    if utilizador:
        condicoes.append("utilizador = ?")
        parametros.append(utilizador)
    if desde is not None:
        condicoes.append("momento >= ?")
        parametros.append(desde.isoformat(timespec="seconds"))

    consulta = (
        "SELECT id, momento, evento, utilizador, alvo, detalhe, origem, antes, depois"
        " FROM auditoria"
    )
    if condicoes:
        consulta += " WHERE " + " AND ".join(condicoes)
    consulta += " ORDER BY id DESC LIMIT ?"
    parametros.append(max(1, limite))

    try:
        banco_de_dados.criar_tabela()
        with banco_de_dados.conectar() as conexao:
            linhas = conexao.execute(consulta, parametros).fetchall()
    except Exception:
        logger.exception("Falha ao consultar a auditoria.")
        return []

    return [_para_registo(linha) for linha in linhas]


def contar() -> int:
    """Número de registos na trilha."""
    import banco_de_dados

    try:
        banco_de_dados.criar_tabela()
        with banco_de_dados.conectar() as conexao:
            return int(conexao.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0])
    except Exception:
        logger.exception("Falha ao contar os registos de auditoria.")
        return 0


def aplicar_retencao(dias: int) -> int:
    """Remove registos mais antigos que ``dias``. Devolve quantos removeu.

    É a única forma de apagar auditoria, e diz sempre o que apagou.
    """
    if dias < 1:
        raise ValueError("A retenção tem de ser de pelo menos um dia.")

    import banco_de_dados

    limite = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    try:
        banco_de_dados.criar_tabela()
        with banco_de_dados.conectar() as conexao:
            cursor = conexao.execute("DELETE FROM auditoria WHERE momento < ?", (limite,))
            removidos = cursor.rowcount
    except Exception:
        logger.exception("Falha ao aplicar a retenção da auditoria.")
        return 0

    if removidos:
        logger.info("Auditoria: %d registo(s) removido(s) por retenção (%dd).", removidos, dias)
    return removidos
