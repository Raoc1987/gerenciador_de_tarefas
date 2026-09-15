"""Séries temporais, tendência, previsão e deteção de anomalias.

Estatística simples, com a biblioteca padrão (ver ADR-0002). Nada aqui é
"inteligência artificial": é regressão linear por mínimos quadrados e desvios
face à mediana. A vantagem é ser explicável — cada número pode ser mostrado ao
utilizador com o seu porquê.

Regra que atravessa o módulo: **sem dados suficientes, devolve-se "não sei"**
em vez de um número bonito sem significado.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence

from analitica.datas import lista_de_dias, para_data

#: Mínimo de pontos para arriscar uma tendência ou uma previsão.
MINIMO_PARA_TENDENCIA = 4
#: Mínimo de pontos para procurar anomalias.
MINIMO_PARA_ANOMALIAS = 7


@dataclass(frozen=True)
class Ponto:
    """Um valor num dia."""

    dia: date
    valor: float

    def __iter__(self):
        yield self.dia
        yield self.valor


@dataclass(frozen=True)
class Tendencia:
    """Resultado de uma regressão linear sobre uma série."""

    declive: float
    """Variação média por dia."""

    intercecao: float
    r2: float
    """Qualidade do ajuste (0–1). Abaixo de ~0,3 a reta explica pouco."""

    pontos: int

    @property
    def valida(self) -> bool:
        """Se houve pontos suficientes para calcular."""
        return self.pontos >= MINIMO_PARA_TENDENCIA

    @property
    def direcao(self) -> str:
        """``"subida"``, ``"descida"`` ou ``"estável"``."""
        if not self.valida or abs(self.declive) < 1e-9:
            return "estável"
        return "subida" if self.declive > 0 else "descida"

    def valor_em(self, indice: float) -> float:
        """Valor previsto pela reta no índice indicado."""
        return self.intercecao + self.declive * indice


def agrupar_por_dia(datas: Iterable) -> Dict[date, int]:
    """Conta ocorrências por dia, ignorando valores sem data."""
    contagem: Dict[date, int] = {}
    for valor in datas:
        dia = para_data(valor)
        if dia is None:
            continue
        contagem[dia] = contagem.get(dia, 0) + 1
    return contagem


def serie_diaria(datas: Iterable, inicio: date, fim: date) -> List[Ponto]:
    """Série com um ponto por dia do intervalo, com zeros onde não houve nada.

    Os dias sem ocorrências têm de aparecer: uma série com buracos mente sobre
    a tendência.
    """
    contagem = agrupar_por_dia(datas)
    return [Ponto(dia, float(contagem.get(dia, 0))) for dia in lista_de_dias(inicio, fim)]


def total(serie: Sequence[Ponto]) -> float:
    """Soma dos valores da série."""
    return float(sum(p.valor for p in serie))


def media(serie: Sequence[Ponto]) -> Optional[float]:
    """Média dos valores, ou ``None`` se a série estiver vazia."""
    return round(statistics.fmean(p.valor for p in serie), 2) if serie else None


def media_movel(serie: Sequence[Ponto], janela: int = 7) -> List[Ponto]:
    """Média móvel simples.

    Os primeiros pontos usam a janela disponível, para a linha começar no
    início da série em vez de flutuar no ar.
    """
    if janela < 1:
        raise ValueError("A janela tem de ser pelo menos 1.")
    suavizada: List[Ponto] = []
    for indice, ponto in enumerate(serie):
        fatia = serie[max(0, indice - janela + 1) : indice + 1]
        suavizada.append(Ponto(ponto.dia, round(statistics.fmean(p.valor for p in fatia), 2)))
    return suavizada


def tendencia(serie: Sequence[Ponto]) -> Tendencia:
    """Regressão linear por mínimos quadrados sobre a série.

    Com menos de :data:`MINIMO_PARA_TENDENCIA` pontos devolve uma tendência
    inválida (``valida == False``) em vez de uma reta sem significado.
    """
    pontos = len(serie)
    if pontos < MINIMO_PARA_TENDENCIA:
        return Tendencia(declive=0.0, intercecao=0.0, r2=0.0, pontos=pontos)

    xs = list(range(pontos))
    ys = [p.valor for p in serie]
    media_x = statistics.fmean(xs)
    media_y = statistics.fmean(ys)

    variacao_x = sum((x - media_x) ** 2 for x in xs)
    if variacao_x == 0:  # pragma: no cover - impossível com índices distintos
        return Tendencia(0.0, media_y, 0.0, pontos)

    covariancia = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    declive = covariancia / variacao_x
    intercecao = media_y - declive * media_x

    variacao_y = sum((y - media_y) ** 2 for y in ys)
    if variacao_y == 0:
        r2 = 1.0  # série constante: a reta descreve-a perfeitamente
    else:
        residuos = sum((y - (intercecao + declive * x)) ** 2 for x, y in zip(xs, ys))
        r2 = max(0.0, 1 - residuos / variacao_y)

    return Tendencia(
        declive=round(declive, 4),
        intercecao=round(intercecao, 4),
        r2=round(r2, 4),
        pontos=pontos,
    )


def prever(serie: Sequence[Ponto], dias: int = 7) -> List[Ponto]:
    """Prolonga a série pela reta de tendência.

    Devolve lista vazia se não houver pontos suficientes. Valores negativos são
    cortados a zero: não existe "menos três tarefas".
    """
    if dias < 1:
        raise ValueError("É preciso prever pelo menos um dia.")
    ajuste = tendencia(serie)
    if not ajuste.valida or not serie:
        return []

    ultimo_dia = serie[-1].dia
    base = len(serie) - 1
    return [
        Ponto(ultimo_dia + timedelta(days=passo), round(max(0.0, ajuste.valor_em(base + passo)), 2))
        for passo in range(1, dias + 1)
    ]


def detetar_anomalias(serie: Sequence[Ponto], limiar: float = 3.0) -> List[Ponto]:
    """Pontos que se afastam demasiado do comportamento habitual.

    Usa a mediana e o desvio absoluto mediano (MAD), que não são arrastados
    pelos próprios extremos como a média e o desvio-padrão seriam.

    Args:
        limiar: quantos desvios medianos um ponto tem de distar para contar.
    """
    if len(serie) < MINIMO_PARA_ANOMALIAS:
        return []

    valores = [p.valor for p in serie]
    mediana = statistics.median(valores)
    desvios = [abs(v - mediana) for v in valores]
    mad = statistics.median(desvios)

    if mad == 0:
        # Série quase constante: só destoa quem for diferente da mediana.
        return [p for p in serie if p.valor != mediana]

    # 1,4826 aproxima o MAD ao desvio-padrão numa distribuição normal.
    escala = mad * 1.4826
    return [p for p in serie if abs(p.valor - mediana) / escala > limiar]


def variacao_percentual(atual: float, anterior: float) -> Optional[float]:
    """Variação de ``anterior`` para ``atual``, ou ``None`` se antes era zero."""
    if anterior == 0:
        return None
    return round((atual - anterior) * 100 / anterior, 1)
