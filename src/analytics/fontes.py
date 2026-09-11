"""A ponte entre a análise e os dados.

É o **único** módulo de :mod:`analytics` que conhece o banco de dados. Trocar
SQLite por outra coisa mexe aqui e em mais lado nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

from analytics.datas import intervalo_de_dias, periodo_anterior
from analytics.insights import Insight, gerar
from analytics.metricas import KPIs, Tarefa, calcular_kpis, comparar, normalizar
from analytics.series import Ponto, media_movel, prever, serie_diaria, tendencia
from core.log import obter_logger
from core.permissoes import Permissao, exigir

logger = obter_logger(__name__)

#: Períodos oferecidos pelo dashboard, em dias.
PERIODOS = (7, 30, 90, 365)
PERIODO_PADRAO = 30


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
    kpis_anteriores: KPIs
    variacoes: dict
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
    """Lê as tarefas do banco, já normalizadas para análise.

    Raises:
        PermissaoNegadaError: se a sessão não puder ler analytics.
    """
    import database

    exigir(Permissao.ANALYTICS_LER)
    database.criar_tabela()
    return normalizar(database.buscar_tarefas_completas())


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

    def no_periodo(desde: date, ate: date) -> List[Tarefa]:
        return [t for t in itens if t.criada_em and desde <= t.criada_em <= ate]

    kpis = calcular_kpis(itens, hoje)
    kpis_antes = calcular_kpis(no_periodo(inicio_antes, fim_antes), fim_antes)

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
        kpis_anteriores=kpis_antes,
        variacoes=comparar(kpis, kpis_antes),
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
