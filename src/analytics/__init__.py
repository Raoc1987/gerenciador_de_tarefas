"""Camada de análise da plataforma.

Independente da interface e da persistência (ver ADR-0003):

* :mod:`analytics.metricas` — KPIs a partir de tarefas;
* :mod:`analytics.series` — séries temporais, tendência, previsão e anomalias;
* :mod:`analytics.insights` — frases derivadas dos números;
* :mod:`analytics.fontes` — a única peça que conhece o banco de dados.

Tudo o resto são funções puras: recebem dados, devolvem resultados. Não abrem
conexões, não tocam em widgets e não sabem que existe um dashboard.
"""

from analytics.metricas import KPIs, calcular_kpis
from analytics.series import (
    Ponto,
    Tendencia,
    detetar_anomalias,
    media_movel,
    prever,
    serie_diaria,
    tendencia,
)

__all__ = [
    "KPIs",
    "Ponto",
    "Tendencia",
    "calcular_kpis",
    "detetar_anomalias",
    "media_movel",
    "prever",
    "serie_diaria",
    "tendencia",
]
