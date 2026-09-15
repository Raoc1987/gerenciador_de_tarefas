"""Os indicadores que esta aplicacao declara sobre si propria.

A ligacao fina entre :mod:`indicadores`, que nao conhece dominios, e as
tarefas. Um modulo de negocio declara os seus pelo contexto do plugin, sem
passar por aqui.

Cada calculo passa por :mod:`tarefas_servico`, e nao pelo banco: um numero
calculado sobre tudo o que existe diria a um colaborador quantas tarefas a
empresa tem, o que a lista dele nao diz.
"""

from __future__ import annotations

from typing import List

import indicadores
from core.log import obter_logger
from indicadores import Valor

logger = obter_logger(__name__)


def _kpis():
    """Os indicadores calculados sobre o que a sessao ve."""
    from analitica.metricas import calcular_kpis, normalizar
    from tarefas_servico import listar_completas

    return calcular_kpis(normalizar(listar_completas()))


def _total() -> Valor:
    kpis = _kpis()
    return Valor(kpis.total) if kpis.tem_dados else Valor()


def _atrasadas() -> Valor:
    kpis = _kpis()
    return Valor(kpis.atrasadas) if kpis.tem_dados else Valor()


def _taxa_conclusao() -> Valor:
    kpis = _kpis()
    if not kpis.tem_dados:
        return Valor()
    return Valor(round(kpis.taxa_conclusao, 1), sufixo="%")


def registar_incluidos() -> None:
    """Poe no registo os indicadores que vem com a aplicacao."""
    indicadores.registar(
        "tarefas.total", _total, "indicador_tarefas_total", permissao="tarefas.ler"
    )
    indicadores.registar(
        "tarefas.atrasadas",
        _atrasadas,
        "indicador_tarefas_atrasadas",
        subir_e_bom=False,
        permissao="tarefas.ler",
    )
    indicadores.registar(
        "tarefas.taxa_conclusao",
        _taxa_conclusao,
        "indicador_tarefas_taxa",
        permissao="tarefas.ler",
    )
