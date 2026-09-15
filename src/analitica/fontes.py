"""A ponte entre a análise e os dados.

É o **único** módulo de :mod:`analitica` que conhece o banco de dados. Trocar
SQLite por outra coisa mexe aqui e em mais lado nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

from analitica.datas import intervalo_de_dias, periodo_anterior
from analitica.insights import Insight, gerar
from analitica.metricas import KPIs, Tarefa, calcular_kpis, normalizar
from analitica.series import (
    Ponto,
    media_movel,
    prever,
    serie_diaria,
    tendencia,
    variacao_percentual,
)
from core.log import obter_logger
from core.permissoes import Permissao, exigir

logger = obter_logger(__name__)

#: Períodos oferecidos pelo dashboard, em dias.
PERIODOS = (7, 30, 90, 365)
PERIODO_PADRAO = 30


@dataclass(frozen=True)
class Fluxo:
    """O que **aconteceu** num período: grandezas comparáveis entre períodos."""

    criadas: int = 0
    concluidas: int = 0

    @property
    def saldo(self) -> int:
        """Criadas menos concluídas: positivo significa acumulação."""
        return self.criadas - self.concluidas


@dataclass(frozen=True)
class Panorama:
    """Tudo o que um dashboard precisa, calculado de uma vez.

    Uma única leitura do banco alimenta KPIs, séries, previsão e insights —
    em vez de cada widget ir buscar os seus dados por sua conta.
    """

    inicio: date
    fim: date
    dias: int
    kpis: KPIs
    """Estado **atual** de todas as tarefas: pendentes, atrasadas, total."""

    fluxo: Fluxo
    """O que aconteceu no período."""

    fluxo_anterior: Fluxo
    """O mesmo, no período imediatamente anterior."""

    variacoes: dict
    """Variação percentual do fluxo. Só grandezas de fluxo aparecem aqui:
    comparar "pendentes agora" com "pendentes há 30 dias" exigiria histórico
    de estado, que não é guardado — e inventá-lo daria um número errado."""

    criadas: List[Ponto]
    concluidas: List[Ponto]
    concluidas_suavizadas: List[Ponto]
    previsao: List[Ponto]
    insights: List[Insight]
    total_tarefas: int

    @property
    def tem_dados(self) -> bool:
        """Se existe alguma tarefa registada."""
        return self.total_tarefas > 0

    @property
    def tem_historico(self) -> bool:
        """Se houve movimento no período analisado."""
        return any(p.valor for p in self.criadas) or any(p.valor for p in self.concluidas)


def carregar_tarefas() -> List[Tarefa]:
    """Lê as tarefas visíveis para a sessão, normalizadas para análise.

    Passa pelo serviço de tarefas: os indicadores de quem só vê as suas contam
    só as suas.

    Raises:
        PermissaoNegadaError: se a sessão não puder ler analitica ou tarefas.
    """
    import banco_de_dados
    import tarefas_servico

    exigir(Permissao.ANALYTICS_LER)
    banco_de_dados.criar_tabela()
    return normalizar(tarefas_servico.listar_completas())


def panorama(
    dias: int = PERIODO_PADRAO,
    hoje: Optional[date] = None,
    tarefas: Optional[Sequence] = None,
) -> Panorama:
    """Calcula o panorama de um período.

    Args:
        dias: tamanho da janela.
        hoje: data de referência (os testes fixam-na).
        tarefas: dados já lidos; se omitido, lê do banco.
    """
    hoje = hoje or date.today()
    itens = normalizar(tarefas) if tarefas is not None else carregar_tarefas()
    inicio, fim = intervalo_de_dias(hoje, dias)
    inicio_antes, fim_antes = periodo_anterior(inicio, fim)

    def contar(desde: date, ate: date, campo: str) -> int:
        return sum(
            1
            for t in itens
            if getattr(t, campo) and desde <= getattr(t, campo) <= ate
        )

    def fluxo_de(desde: date, ate: date) -> Fluxo:
        return Fluxo(
            criadas=contar(desde, ate, "criada_em"),
            concluidas=contar(desde, ate, "concluida_em"),
        )

    # Estado atual (tudo), medido hoje: é o que interessa em "pendentes" e
    # "atrasadas", que são fotografias e não fluxos.
    kpis = calcular_kpis(itens, hoje)
    fluxo = fluxo_de(inicio, fim)
    fluxo_antes = fluxo_de(inicio_antes, fim_antes)
    variacoes = {
        "criadas": variacao_percentual(fluxo.criadas, fluxo_antes.criadas),
        "concluidas": variacao_percentual(fluxo.concluidas, fluxo_antes.concluidas),
    }

    criadas = serie_diaria([t.criada_em for t in itens if t.criada_em], inicio, fim)
    concluidas = serie_diaria(
        [t.concluida_em for t in itens if t.concluida_em], inicio, fim
    )
    janela = 7 if dias >= 14 else 3

    return Panorama(
        inicio=inicio,
        fim=fim,
        dias=dias,
        kpis=kpis,
        fluxo=fluxo,
        fluxo_anterior=fluxo_antes,
        variacoes=variacoes,
        criadas=criadas,
        concluidas=concluidas,
        concluidas_suavizadas=media_movel(concluidas, janela),
        previsao=prever(concluidas, dias=min(7, dias)),
        insights=gerar(itens, hoje=hoje, dias=dias),
        total_tarefas=len(itens),
    )


def tendencia_de_conclusoes(panorama_atual: Panorama):
    """Tendência da série de conclusões do panorama."""
    return tendencia(panorama_atual.concluidas)
