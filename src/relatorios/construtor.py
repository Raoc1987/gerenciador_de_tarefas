"""Montagem dos relatórios a partir da análise.

Os números vêm todos de :mod:`analitica` — o relatório não recalcula nada por
sua conta, senão acabaria a divergir do dashboard.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, List, Optional, Sequence

from analitica import fontes
from analitica.fontes import Panorama
from analitica.metricas import Tarefa, normalizar
from language_manager import carregar_texto
from relatorios.modelo import Indicadores, Lista, Relatorio, Tabela
from textos import texto_do_insight

Tradutor = Callable[..., str]


def _estado(tarefa: Tarefa, hoje: date, traduzir: Tradutor) -> str:
    """Estado de UMA tarefa — no singular.

    Os rótulos do dashboard ("Concluídas", "Atrasadas") contam conjuntos; numa
    linha de tabela ficariam errados.
    """
    if tarefa.concluida:
        return traduzir("estado_tarefa_concluida")
    if tarefa.esta_atrasada(hoje):
        return traduzir("estado_tarefa_atrasada")
    return traduzir("estado_tarefa_pendente")


def tabela_de_tarefas(
    tarefas: Sequence,
    hoje: Optional[date] = None,
    traduzir: Tradutor = carregar_texto,
    limite: Optional[int] = None,
) -> Tabela:
    """Tabela com uma linha por tarefa, ordenada pelas atrasadas primeiro."""
    hoje = hoje or date.today()
    itens = normalizar(tarefas)

    def ordem(tarefa: Tarefa):
        return (
            not tarefa.esta_atrasada(hoje),
            tarefa.concluida,
            tarefa.vencimento or date.max,
            tarefa.id,
        )

    ordenadas = sorted(itens, key=ordem)
    if limite:
        ordenadas = ordenadas[:limite]

    return Tabela(
        titulo=traduzir("tarefas"),
        colunas=[
            traduzir("descricao_tarefa"),
            # "data_vencimento" traz a dica de formato, útil no formulário e
            # desproporcionada como cabeçalho de coluna.
            traduzir("relatorio_vencimento"),
            traduzir("plugin_status"),
            traduzir("relatorio_criada_em"),
            traduzir("relatorio_concluida_em"),
        ],
        linhas=[
            [
                tarefa.descricao,
                tarefa.vencimento.strftime("%d/%m/%Y") if tarefa.vencimento else "",
                _estado(tarefa, hoje, traduzir),
                tarefa.criada_em.strftime("%d/%m/%Y") if tarefa.criada_em else "",
                tarefa.concluida_em.strftime("%d/%m/%Y") if tarefa.concluida_em else "",
            ]
            for tarefa in ordenadas
        ],
    )


def indicadores(visao: Panorama, traduzir: Tradutor = carregar_texto) -> Indicadores:
    """Os mesmos indicadores do dashboard, em texto."""
    kpis = visao.kpis
    itens = [
        (traduzir("kpi_criadas", dias=visao.dias), str(visao.fluxo.criadas)),
        (traduzir("kpi_concluidas", dias=visao.dias), str(visao.fluxo.concluidas)),
        (traduzir("kpi_pendentes"), str(kpis.pendentes)),
        (traduzir("kpi_atrasadas"), str(kpis.atrasadas)),
        (traduzir("kpi_taxa_conclusao"), f"{kpis.taxa_conclusao:.0f}%"),
    ]
    if kpis.duracao_media_dias is not None:
        itens.append(
            (traduzir("relatorio_duracao_media"), f"{kpis.duracao_media_dias:.1f}")
        )
    return Indicadores(titulo=traduzir("relatorio_indicadores"), itens=itens)


def analise(visao: Panorama, traduzir: Tradutor = carregar_texto) -> Lista:
    """A análise em texto, igual à do dashboard."""
    return Lista(
        titulo=traduzir("analise"),
        itens=[texto_do_insight(insight) for insight in visao.insights],
    )


def relatorio_de_tarefas(
    dias: int = fontes.PERIODO_PADRAO,
    hoje: Optional[date] = None,
    tarefas: Optional[Sequence] = None,
    traduzir: Tradutor = carregar_texto,
) -> Relatorio:
    """Relatório operacional: indicadores, análise e a lista de tarefas.

    Args:
        dias: período a analisar.
        hoje: data de referência (fixada pelos testes).
        tarefas: dados já lidos; se omitido, lê do banco.
    """
    hoje = hoje or date.today()
    itens = normalizar(tarefas) if tarefas is not None else fontes.carregar_tarefas()
    visao = fontes.panorama(dias=dias, hoje=hoje, tarefas=itens)

    secoes: List = [indicadores(visao, traduzir), analise(visao, traduzir)]
    secoes.append(tabela_de_tarefas(itens, hoje=hoje, traduzir=traduzir))

    relatorio = Relatorio(
        titulo=traduzir("relatorio_titulo"),
        subtitulo=traduzir("periodo_dias", dias=dias),
        inicio=visao.inicio,
        fim=visao.fim,
        secoes=secoes,
        rodape=traduzir("relatorio_rodape", aplicacao=traduzir("titulo")),
    )
    relatorio.validar()
    return relatorio
