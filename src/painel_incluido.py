"""Os widgets de painel que vêm com a aplicação.

A ligação fina entre :mod:`painel`, que não conhece domínios, e o que esta
aplicação tem para mostrar. Um módulo de negócio regista os seus pelo
contexto do plugin, sem passar por aqui.

Eram quatro blocos escritos à mão dentro de ``dashboard_ui.py``. Continuam a
mostrar exatamente o mesmo — o que mudou é que agora são **widgets como os
outros**: declaram a largura que querem, respeitam a permissão, saem quando a
funcionalidade é desligada, e um módulo pode pôr o seu ao lado deles.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List

from analitica.insights import Insight
from aparencia import ESPACO, cores, fonte
from componentes.graficos import (
    PREENCHER_ATENCAO,
    PREENCHER_BOM,
    PREENCHER_MAU,
    CartaoKPI,
    GraficoBarras,
    GraficoLinhas,
    Serie,
)
from core.log import obter_logger
from core.permissoes import Permissao
from language_manager import carregar_texto
from painel import registar
from painel.contexto import Contexto
from textos import texto_do_insight

logger = obter_logger(__name__)

LER = Permissao.ANALYTICS_LER.value

#: Quantos insights mostrar. Ver quatro é ler; ver dezasseis é percorrer.
INSIGHTS_VISIVEIS = 4


class CartoesDeTarefas(ttk.Frame):
    """Os cinco indicadores das tarefas, numa linha."""

    CHAVES = ("criadas", "concluidas", "pendentes", "atrasadas", "taxa")

    def __init__(self, pai: tk.Misc) -> None:
        super().__init__(pai)
        # Fluxo (criadas/concluídas) leva variação face ao período anterior;
        # estado (pendentes/atrasadas/taxa) não leva — não há histórico de
        # estado para comparar.
        self.cartoes = {
            "criadas": CartaoKPI(self),
            "concluidas": CartaoKPI(self),
            "pendentes": CartaoKPI(self),
            "atrasadas": CartaoKPI(self, cor=cores()["mau"], subir_e_bom=False),
            "taxa": CartaoKPI(self),
        }
        for coluna, cartao in enumerate(self.cartoes.values()):
            cartao.grid(row=0, column=coluna, sticky=tk.EW,
                        padx=ESPACO["apertado"], pady=ESPACO["apertado"])
            self.columnconfigure(coluna, weight=1)

    def atualizar(self, contexto: Contexto) -> None:
        if not contexto.tem_dados:
            for cartao in self.cartoes.values():
                cartao.atualizar(valor="—", variacao=None)
            return
        visao = contexto.panorama
        kpis, variacoes = visao.kpis, visao.variacoes
        self.cartoes["criadas"].atualizar(
            carregar_texto("kpi_criadas", dias=visao.dias),
            str(visao.fluxo.criadas), variacoes.get("criadas"),
        )
        self.cartoes["concluidas"].atualizar(
            carregar_texto("kpi_concluidas", dias=visao.dias),
            str(visao.fluxo.concluidas), variacoes.get("concluidas"),
        )
        self.cartoes["pendentes"].atualizar(
            carregar_texto("kpi_pendentes"), str(kpis.pendentes)
        )
        self.cartoes["atrasadas"].atualizar(
            carregar_texto("kpi_atrasadas"), str(kpis.atrasadas)
        )
        self.cartoes["taxa"].atualizar(
            carregar_texto("kpi_taxa_conclusao"), f"{kpis.taxa_conclusao:.0f}%"
        )


class CartoesDeModulos(ttk.Frame):
    """O que os módulos instalados declararam saber medir.

    O painel não sabe o que cada um mede: pergunta ao registo. Quem não pode
    ver um número não vê o cartão — e não vê sequer que ele existe.

    Sem módulos a medir, este widget fica com altura zero em vez de reservar
    espaço a coisas que talvez existam.
    """

    def __init__(self, pai: tk.Misc) -> None:
        super().__init__(pai)
        self.cartoes = {}

    def atualizar(self, contexto: Contexto) -> None:
        import indicadores

        for cartao in self.cartoes.values():
            cartao.destroy()
        self.cartoes = {}

        try:
            leituras = [l for l in indicadores.ler() if l.indicador.dono]
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao ler os indicadores dos módulos.")
            return

        for coluna, leitura in enumerate(leituras):
            cartao = CartaoKPI(self, subir_e_bom=leitura.indicador.subir_e_bom)
            cartao.atualizar(
                rotulo=carregar_texto(leitura.indicador.chave_titulo, leitura.chave),
                valor=leitura.valor.formatado(),
                variacao=leitura.valor.variacao,
            )
            cartao.grid(row=0, column=coluna, sticky=tk.EW,
                        padx=ESPACO["apertado"], pady=ESPACO["apertado"])
            self.columnconfigure(coluna, weight=1)
            self.cartoes[leitura.chave] = cartao


class SerieDeConclusoes(GraficoLinhas):
    """Concluídas por dia, com média móvel e previsão."""

    def __init__(self, pai: tk.Misc) -> None:
        super().__init__(pai, altura=180)
        self.definir_texto_sem_dados(carregar_texto("sem_dados_periodo"))

    def atualizar(self, contexto: Contexto) -> None:
        if not contexto.tem_dados:
            self.definir_series([])
            return
        visao = contexto.panorama
        paleta = cores()
        series: List[Serie] = [
            Serie(carregar_texto("serie_concluidas"), visao.concluidas, paleta["bom"]),
            Serie(carregar_texto("serie_media_movel"), visao.concluidas_suavizadas,
                  paleta["acento"]),
        ]
        if visao.previsao:
            series.append(
                Serie(carregar_texto("serie_previsao"), visao.previsao,
                      paleta["texto_suave"], tracejado=True)
            )
        self.definir_series(series)


class EstadoDasTarefas(GraficoBarras):
    """Concluídas, em dia e atrasadas."""

    def __init__(self, pai: tk.Misc) -> None:
        super().__init__(pai, altura=180)
        self.definir_texto_sem_dados(carregar_texto("sem_dados_periodo"))

    def atualizar(self, contexto: Contexto) -> None:
        if not contexto.tem_dados:
            self.definir_dados([])
            return
        kpis = contexto.panorama.kpis
        self.definir_dados(
            [
                (carregar_texto("estado_concluidas"), kpis.concluidas),
                (carregar_texto("estado_pendentes"), kpis.pendentes - kpis.atrasadas),
                (carregar_texto("estado_atrasadas"), kpis.atrasadas),
            ],
            cores=(PREENCHER_BOM, PREENCHER_ATENCAO, PREENCHER_MAU),
        )


class CaixaDeInsights(ttk.LabelFrame):
    """As frases derivadas dos números — nunca inventadas."""

    def __init__(self, pai: tk.Misc) -> None:
        super().__init__(pai, padding=ESPACO["confortavel"])
        self.configure(text=carregar_texto("analise"))
        self.lista = ttk.Frame(self)
        self.lista.pack(fill=tk.X)

    def atualizar(self, contexto: Contexto) -> None:
        from dashboard_ui import MARCAS_POR_NIVEL, TOKEN_POR_NIVEL

        for filho in self.lista.winfo_children():
            filho.destroy()

        if contexto.mensagem:
            ttk.Label(self.lista, text=contexto.mensagem, style="Suave.TLabel").pack(
                anchor=tk.W
            )
            return

        encontrados: List[Insight] = (
            list(contexto.panorama.insights) if contexto.tem_dados else []
        )
        if not encontrados:
            ttk.Label(
                self.lista, text=carregar_texto("sem_insights"), style="Suave.TLabel"
            ).pack(anchor=tk.W)
            return

        paleta = cores()
        for insight in encontrados[:INSIGHTS_VISIVEIS]:
            linha = ttk.Frame(self.lista)
            linha.pack(fill=tk.X, anchor=tk.W)
            ttk.Label(
                linha,
                text=MARCAS_POR_NIVEL[insight.nivel],
                foreground=paleta[TOKEN_POR_NIVEL[insight.nivel]],
                font=fonte("destaque", negrito=True),
                width=2,
            ).pack(side=tk.LEFT)
            ttk.Label(
                linha, text=texto_do_insight(insight), wraplength=680, justify=tk.LEFT
            ).pack(side=tk.LEFT, anchor=tk.W)


def registar_incluidos() -> None:
    """Põe no registo os widgets que vêm com a aplicação.

    Idempotente: o registo é por id. As larguras dizem o que cada um precisa
    — os cartões e a análise querem a linha inteira, os dois gráficos ficam
    lado a lado num ecrã largo e um sobre o outro quando a janela encolhe.
    """
    registar("tarefas.kpis", "kpi_criadas", CartoesDeTarefas,
             largura=4, ordem=10, permissao=LER)
    registar("modulos.kpis", "indicadores", CartoesDeModulos,
             largura=4, ordem=20, permissao=LER)
    registar("tarefas.serie", "grafico_conclusoes", SerieDeConclusoes,
             largura=2, ordem=30, permissao=LER)
    registar("tarefas.estado", "grafico_estado", EstadoDasTarefas,
             largura=2, ordem=40, permissao=LER)
    registar("analise.insights", "analise", CaixaDeInsights,
             largura=4, ordem=50, permissao=LER)
