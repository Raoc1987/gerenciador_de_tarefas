"""Leitura dos números em linguagem natural.

Um insight é uma frase que o utilizador pode verificar: diz o que aconteceu e
mostra o número em que se baseia. Nunca é uma opinião nem uma extrapolação
sem suporte.

Regras, por ordem de importância:

1. **Sem dados suficientes, não há insight.** Dizer "a produtividade está
   estável" com três dias de histórico é inventar.
2. **Todo o insight traz o seu número.** "Subiu 12%" e não "subiu bastante".
3. **A previsão diz que é previsão** e só aparece quando o ajuste explica
   minimamente a série.

Os textos são chaves de tradução com parâmetros, resolvidas pela interface —
o núcleo não escreve português a martelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from analitica.datas import intervalo_de_dias, periodo_anterior
from analitica.metricas import KPIs, calcular_kpis, filtrar_por_periodo, normalizar
from analitica.series import (
    MINIMO_PARA_TENDENCIA,
    Ponto,
    detetar_anomalias,
    serie_diaria,
    tendencia,
    total,
    variacao_percentual,
)


class Nivel(str, Enum):
    """Gravidade do que o insight comunica."""

    INFORMACAO = "informacao"
    POSITIVO = "positivo"
    ATENCAO = "atencao"
    CRITICO = "critico"


class Tipo(str, Enum):
    """Que pergunta o insight responde (escada clássica de analitica)."""

    DESCRITIVO = "descritivo"
    """O que aconteceu."""

    DIAGNOSTICO = "diagnostico"
    """Porque aconteceu."""

    PREDITIVO = "preditivo"
    """O que é provável acontecer."""

    PRESCRITIVO = "prescritivo"
    """O que se pode fazer."""


@dataclass(frozen=True)
class Insight:
    """Uma afirmação sobre os dados, pronta a traduzir e mostrar."""

    chave: str
    """Chave de tradução (ex.: ``insight_atrasadas``)."""

    parametros: Dict[str, Any] = field(default_factory=dict)
    nivel: Nivel = Nivel.INFORMACAO
    tipo: Tipo = Tipo.DESCRITIVO

    def __str__(self) -> str:  # pragma: no cover - apoio a depuração
        return f"[{self.nivel.value}] {self.chave} {self.parametros}"


def gerar(
    tarefas: Sequence,
    hoje: Optional[date] = None,
    dias: int = 30,
) -> List[Insight]:
    """Analisa as tarefas e devolve os insights que os dados sustentam.

    Args:
        tarefas: linhas do banco (5 ou 6 colunas) ou ``Tarefa`` normalizadas.
        hoje: data de referência.
        dias: tamanho da janela de análise.

    Returns:
        Lista possivelmente vazia, ordenada do mais grave para o menos grave.
        Vazia significa mesmo "não há nada de sólido a dizer".
    """
    hoje = hoje or date.today()
    itens = normalizar(tarefas)
    if not itens:
        return []

    inicio, fim = intervalo_de_dias(hoje, dias)
    kpis = calcular_kpis(itens, hoje)
    encontrados: List[Insight] = []

    encontrados.extend(_sobre_atrasos(kpis))
    encontrados.extend(_sobre_conclusao(itens, inicio, fim, hoje, dias))
    encontrados.extend(_sobre_tendencia(itens, inicio, fim))
    encontrados.extend(_sobre_anomalias(itens, inicio, fim))
    encontrados.extend(_sobre_prazos(kpis))

    ordem = {Nivel.CRITICO: 0, Nivel.ATENCAO: 1, Nivel.POSITIVO: 2, Nivel.INFORMACAO: 3}
    return sorted(encontrados, key=lambda i: ordem[i.nivel])


# ------------------------------------------------------------- geradores


def _sobre_atrasos(kpis: KPIs) -> List[Insight]:
    if not kpis.atrasadas:
        return []
    nivel = Nivel.CRITICO if kpis.taxa_atraso >= 25 else Nivel.ATENCAO
    return [
        Insight(
            chave="insight_atrasadas",
            parametros={"quantidade": kpis.atrasadas, "percentagem": kpis.taxa_atraso},
            nivel=nivel,
            tipo=Tipo.DESCRITIVO,
        )
    ]


def _sobre_conclusao(
    itens: Sequence, inicio: date, fim: date, hoje: date, dias: int
) -> List[Insight]:
    """Compara o período atual com o anterior, do mesmo tamanho."""
    concluidas_agora = filtrar_por_periodo(itens, inicio, fim, campo="concluida_em")
    inicio_antes, fim_antes = periodo_anterior(inicio, fim)
    concluidas_antes = filtrar_por_periodo(itens, inicio_antes, fim_antes, campo="concluida_em")

    if not concluidas_antes:
        # Sem período de comparação, não se fala em variação.
        if concluidas_agora:
            return [
                Insight(
                    chave="insight_concluidas_periodo",
                    parametros={"quantidade": len(concluidas_agora), "dias": dias},
                    nivel=Nivel.INFORMACAO,
                    tipo=Tipo.DESCRITIVO,
                )
            ]
        return []

    variacao = variacao_percentual(len(concluidas_agora), len(concluidas_antes))
    if variacao is None or abs(variacao) < 10:
        return []

    return [
        Insight(
            chave="insight_produtividade_subiu" if variacao > 0 else "insight_produtividade_desceu",
            parametros={
                "percentagem": abs(variacao),
                "dias": dias,
                "atual": len(concluidas_agora),
                "anterior": len(concluidas_antes),
            },
            nivel=Nivel.POSITIVO if variacao > 0 else Nivel.ATENCAO,
            tipo=Tipo.DIAGNOSTICO,
        )
    ]


def _serie_de_conclusoes(itens: Sequence, inicio: date, fim: date) -> List[Ponto]:
    concluidas = [t.concluida_em for t in normalizar(itens) if t.concluida_em]
    return serie_diaria(concluidas, inicio, fim)


def _sobre_tendencia(itens: Sequence, inicio: date, fim: date) -> List[Insight]:
    serie = _serie_de_conclusoes(itens, inicio, fim)
    if total(serie) == 0:
        return []

    ajuste = tendencia(serie)
    if not ajuste.valida or ajuste.r2 < 0.3 or abs(ajuste.declive) < 0.05:
        # Ou há poucos pontos, ou a reta não explica a série: calar.
        return []

    return [
        Insight(
            chave="insight_tendencia",
            parametros={
                "direcao": ajuste.direcao,
                "por_dia": abs(round(ajuste.declive, 2)),
                "confianca": round(ajuste.r2 * 100),
            },
            nivel=Nivel.POSITIVO if ajuste.declive > 0 else Nivel.ATENCAO,
            tipo=Tipo.PREDITIVO,
        )
    ]


def _sobre_anomalias(itens: Sequence, inicio: date, fim: date) -> List[Insight]:
    serie = _serie_de_conclusoes(itens, inicio, fim)
    anomalias = detetar_anomalias(serie)
    if not anomalias:
        return []
    pico = max(anomalias, key=lambda p: p.valor)
    return [
        Insight(
            chave="insight_anomalia",
            parametros={"dia": pico.dia.isoformat(), "valor": int(pico.valor)},
            nivel=Nivel.ATENCAO,
            tipo=Tipo.DIAGNOSTICO,
        )
    ]


def _sobre_prazos(kpis: KPIs) -> List[Insight]:
    encontrados = []
    if kpis.vencem_hoje:
        encontrados.append(
            Insight(
                chave="insight_vencem_hoje",
                parametros={"quantidade": kpis.vencem_hoje},
                nivel=Nivel.ATENCAO,
                tipo=Tipo.PRESCRITIVO,
            )
        )
    if kpis.pendentes and kpis.sem_prazo == kpis.pendentes and kpis.pendentes >= 3:
        encontrados.append(
            Insight(
                chave="insight_sem_prazo",
                parametros={"quantidade": kpis.sem_prazo},
                nivel=Nivel.INFORMACAO,
                tipo=Tipo.PRESCRITIVO,
            )
        )
    return encontrados


def minimo_de_dados() -> int:
    """Pontos necessários para as análises temporais darem alguma coisa."""
    return MINIMO_PARA_TENDENCIA
