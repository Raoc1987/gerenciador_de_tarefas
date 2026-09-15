"""Camada de análise da plataforma.

Independente da interface e da persistência (ver ADR-0003):

* :mod:`analitica.metricas` — KPIs a partir de tarefas;
* :mod:`analitica.series` — séries temporais, tendência, previsão e anomalias;
* :mod:`analitica.insights` — frases derivadas dos números;
* :mod:`analitica.fontes` — a única peça que conhece o banco de dados.

Tudo o resto são funções puras: recebem dados, devolvem resultados. Não abrem
conexões, não tocam em widgets e não sabem que existe um dashboard.
"""

from analitica.metricas import KPIs, calcular_kpis
from analitica.series import (
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
