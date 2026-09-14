"""Vigilância: transformar o que a análise vê em algo que alguém sabe.

A análise já sabia dizer que há tarefas atrasadas, que o ritmo caiu ou que um
dia foge ao padrão — mas só o dizia a quem abrisse o painel. Este módulo fecha
o último elo da cadeia que faltava:

    tarefa -> evento -> métrica -> painel -> modelo -> previsão -> **alerta**

Publica eventos ``analise.*``, e a partir daí uma regra de automação pode
agir sem que a análise saiba que a automação existe.

**O problema difícil aqui é não repetir.** "Há 15 tarefas atrasadas" continua
verdade amanhã, e depois. Se cada avaliação publicasse, uma regra ligada a ela
criava a mesma tarefa de novo todos os dias — e um alerta que se repete é um
alerta que se deixa de ler. Por isso a vigilância **lembra-se do que já disse**:

* uma conclusão nova é anunciada;
* a mesma conclusão, na mesma gravidade, cala-se;
* se a gravidade **agravar**, volta a ser anunciada — passar de atenção a
  crítico é notícia;
* quando deixa de se aplicar, é anunciado que passou.

O estado é guardado, não fica em memória: senão cada arranque recomeçava do
zero e voltava a anunciar tudo.

É um **Service** (ADR-0004): não tem interface, não tem domínio próprio, e
existe para ligar duas peças que não se conhecem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from analytics.insights import Insight, Nivel, gerar
from core import eventos
from core.log import obter_logger

logger = obter_logger(__name__)

#: Gravidade por ordem. Só um agravamento volta a ser anunciado.
_ORDEM = {
    Nivel.INFORMACAO: 0,
    Nivel.POSITIVO: 0,
    Nivel.ATENCAO: 1,
    Nivel.CRITICO: 2,
}

#: Níveis que valem um alerta. Uma boa notícia não devia acordar ninguém nem
#: fazer disparar automações; fica no painel, que é onde se vai vê-la.
NIVEIS_ALERTAVEIS = (Nivel.ATENCAO, Nivel.CRITICO)


@dataclass(frozen=True)
class Mudanca:
    """O que mudou desde a última vigilância."""

    novos: Tuple[Insight, ...] = ()
    agravados: Tuple[Insight, ...] = ()
    resolvidos: Tuple[str, ...] = ()

    @property
    def houve_novidade(self) -> bool:
        return bool(self.novos or self.agravados or self.resolvidos)

    @property
    def anunciados(self) -> Tuple[Insight, ...]:
        return self.novos + self.agravados


# ------------------------------------------------------------------ estado


def _conectar():
    import database

    database.criar_tabela()
    return database.conectar()


def vistos() -> Dict[str, Nivel]:
    """O que a vigilância já anunciou, e com que gravidade."""
    with _conectar() as conexao:
        linhas = conexao.execute("SELECT chave, nivel FROM alertas_vistos").fetchall()

    conhecidos = {}
    for chave, nivel in linhas:
        try:
            conhecidos[chave] = Nivel(nivel)
        except ValueError:  # pragma: no cover - linha de uma versão anterior
            logger.warning("Nível desconhecido em alertas_vistos: %r", nivel)
    return conhecidos


def _marcar(chave: str, nivel: Nivel) -> None:
    with _conectar() as conexao:
        conexao.execute(
            "INSERT INTO alertas_vistos (chave, nivel, visto_em) VALUES (?, ?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET nivel = excluded.nivel, "
            "visto_em = excluded.visto_em",
            (chave, nivel.value, datetime.now().isoformat(timespec="seconds")),
        )


def _esquecer(chave: str) -> None:
    with _conectar() as conexao:
        conexao.execute("DELETE FROM alertas_vistos WHERE chave = ?", (chave,))


def esquecer_tudo() -> None:
    """Apaga a memória da vigilância — tudo voltará a ser anunciado uma vez."""
    with _conectar() as conexao:
        conexao.execute("DELETE FROM alertas_vistos")


# ------------------------------------------------------------- vigilância


def avaliar(
    tarefas: Optional[Sequence] = None, hoje: Optional[date] = None, dias: int = 30
) -> Mudanca:
    """Analisa, compara com o que já foi dito, e anuncia só o que mudou.

    Args:
        tarefas: quando não é dado, vem de :mod:`analytics.fontes` — que
            aplica as permissões e a visibilidade da sessão. A vigilância não
            vê mais do que quem a desencadeou.

    Returns:
        O que mudou. Vazio quando não há novidade, que é o caso normal.
    """
    if tarefas is None:
        from analytics import fontes

        tarefas = fontes.carregar_tarefas()

    encontrados = [i for i in gerar(tarefas, hoje=hoje, dias=dias) if i.nivel in NIVEIS_ALERTAVEIS]
    atuais = {insight.chave: insight for insight in encontrados}
    conhecidos = vistos()

    novos: List[Insight] = []
    agravados: List[Insight] = []
    for chave, insight in atuais.items():
        anterior = conhecidos.get(chave)
        if anterior is None:
            novos.append(insight)
        elif _ORDEM[insight.nivel] > _ORDEM[anterior]:
            agravados.append(insight)

    resolvidos = [chave for chave in conhecidos if chave not in atuais]

    mudanca = Mudanca(tuple(novos), tuple(agravados), tuple(resolvidos))
    _anunciar(mudanca)
    return mudanca


def _anunciar(mudanca: Mudanca) -> None:
    """Publica os eventos e atualiza a memória."""
    for insight in mudanca.anunciados:
        # Os parâmetros do insight vão no evento para uma regra os poder usar
        # no texto de uma tarefa. `id` e `nivel` não são sobrepostos: um
        # parâmetro com esse nome não pode disfarçar a identidade do alerta.
        dados = {k: v for k, v in insight.parametros.items() if k not in ("id", "nivel")}
        eventos.publicar(
            eventos.ANALISE_ALERTA,
            origem="alertas",
            id=insight.chave,
            nivel=insight.nivel.value,
            tipo=insight.tipo.value,
            **dados,
        )
        _marcar(insight.chave, insight.nivel)
        logger.info("Alerta: %s (%s)", insight.chave, insight.nivel.value)

    for chave in mudanca.resolvidos:
        eventos.publicar(eventos.ANALISE_RESOLVIDO, origem="alertas", id=chave)
        _esquecer(chave)
        logger.info("Alerta resolvido: %s", chave)


def ativar() -> None:
    """Liga a vigilância às alterações nas tarefas.

    Reavalia quando uma tarefa é criada, concluída, reaberta ou removida —
    que é quando as conclusões podem ter mudado. Não reavalia a cada evento
    do sistema: correr a análise inteira por causa de um plugin ativado seria
    trabalho a mais para a mesma resposta.
    """
    if _inscricoes():
        return
    for nome in (
        eventos.TAREFA_CRIADA,
        eventos.TAREFA_CONCLUIDA,
        eventos.TAREFA_REABERTA,
        eventos.TAREFA_REMOVIDA,
    ):
        eventos.subscrever(nome, _ao_mudar, dono="alertas")
    logger.info("Vigilância ativa.")


def desativar() -> None:
    """Desliga a vigilância."""
    eventos.barramento().cancelar_por_dono("alertas")


def ativa() -> bool:
    """Se a vigilância está ligada ao barramento agora."""
    return bool(_inscricoes())


def _inscricoes() -> List:
    return [i for i in eventos.barramento().inscricoes() if i.dono == "alertas"]


def _ao_mudar(evento) -> None:
    """Reavalia sem nunca estragar a operação que provocou o evento."""
    try:
        avaliar()
    except Exception:
        # Uma falha a analisar não pode impedir alguém de criar uma tarefa.
        logger.exception("Falha ao reavaliar os alertas.")
