"""Aba *Dashboard*: KPIs, gráficos e análise.

É a ponta visível da espinha de dados: uma tarefa criada publica um evento, o
dashboard ouve-o e recalcula. Não faz `SELECT` nenhum — pede o panorama a
:mod:`analitica.fontes` e desenha o que recebe.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional

from analitica import fontes
from analitica.fontes import PERIODO_PADRAO, PERIODOS, Panorama
from analitica.insights import Insight, Nivel
from core import eventos, permissoes
from core.log import obter_logger
from core.permissoes import Permissao
from aparencia import cores, fonte
from language_manager import carregar_texto
from relatorios import exportadores, servico
from relatorios.construtor import relatorio_de_tarefas
from textos import texto_do_insight
from componentes.graficos import (
    COR_ALERTA,
    PREENCHER_ATENCAO,
    PREENCHER_BOM,
    PREENCHER_MAU,
    COR_ATENCAO,
    COR_NEUTRA,
    COR_PRIMARIA,
    COR_SECUNDARIA,
    CartaoKPI,
    GraficoBarras,
    GraficoLinhas,
    Serie,
)

logger = obter_logger(__name__)

#: Espera antes de recalcular, para uma rajada de eventos dar um só recálculo.
ATRASO_ATUALIZACAO_MS = 250

#: Que token de cor corresponde a cada nível — o **nome**, não o valor.
#:
#: Guardar o valor aqui prendia a aplicação ao modo que estava em vigor
#: quando este módulo foi lido, que é sempre o claro.
TOKEN_POR_NIVEL = {
    Nivel.CRITICO: "mau",
    Nivel.ATENCAO: "aviso",
    Nivel.POSITIVO: "bom",
    Nivel.INFORMACAO: "texto_suave",
}

MARCAS_POR_NIVEL = {
    Nivel.CRITICO: "!",
    Nivel.ATENCAO: "!",
    Nivel.POSITIVO: "+",
    Nivel.INFORMACAO: "•",
}


class PainelDashboard(ttk.Frame):
    """Painel com indicadores, gráficos e análise das tarefas.

    Args:
        master: widget pai.
        obter_panorama: injetável nos testes; por omissão usa
            :func:`analitica.fontes.panorama`.
    """

    def __init__(
        self,
        master: tk.Misc,
        obter_panorama: Optional[Callable[..., Panorama]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._obter_panorama = obter_panorama or fontes.panorama
        self._dias = PERIODO_PADRAO
        self._panorama: Optional[Panorama] = None
        self._agendamento: Optional[str] = None

        self._construir()

        self._inscricao = eventos.subscrever("tarefa.*", self._ao_mudar_tarefas, dono="dashboard")
        self.bind("<Destroy>", self._ao_destruir, add="+")

        self.atualizar()

    # ------------------------------------------------------------ montagem

    def _construir(self) -> None:
        barra = ttk.Frame(self)
        barra.pack(fill=tk.X, pady=(8, 4), padx=8)

        self._titulo = ttk.Label(barra, font=fonte("subtitulo", negrito=True))
        self._titulo.pack(side=tk.LEFT)

        self._botao_atualizar = ttk.Button(barra, command=self.atualizar, width=12)
        self._botao_atualizar.pack(side=tk.RIGHT)

        self._botao_exportar = ttk.Button(barra, command=self.exportar, width=12)
        self._botao_exportar.pack(side=tk.RIGHT, padx=(0, 6))

        self._periodo_var = tk.StringVar()
        self._seletor = ttk.Combobox(
            barra,
            textvariable=self._periodo_var,
            state="readonly",
            width=18,
            values=[self._rotulo_periodo(d) for d in PERIODOS],
        )
        self._seletor.pack(side=tk.RIGHT, padx=8)
        self._seletor.bind("<<ComboboxSelected>>", self._ao_mudar_periodo)

        self._linha_kpis = ttk.Frame(self)
        self._linha_kpis.pack(fill=tk.X, padx=8)
        # Fluxo (criadas/concluídas) leva variação face ao período anterior;
        # estado (pendentes/atrasadas/taxa) não leva — não há histórico de estado.
        self._cartoes = {
            # Só o que é mesmo um estado leva cor. "Criadas: 6" não é bom
            # nem mau — é um número, e pintá-lo obrigava quem lê a decidir
            # o que a cor queria dizer.
            "criadas": CartaoKPI(self._linha_kpis),
            "concluidas": CartaoKPI(self._linha_kpis),
            "pendentes": CartaoKPI(self._linha_kpis),
            "atrasadas": CartaoKPI(
                self._linha_kpis, cor=cores()["mau"], subir_e_bom=False
            ),
            "taxa": CartaoKPI(self._linha_kpis),
        }
        for coluna, cartao in enumerate(self._cartoes.values()):
            cartao.grid(row=0, column=coluna, sticky="ew", padx=3, pady=4)
            self._linha_kpis.columnconfigure(coluna, weight=1)

        # Segunda linha: o que os módulos declararem. Vazia e invisível
        # quando não há nenhum — um painel não deve ter espaço reservado a
        # coisas que talvez existam.
        self._linha_modulos = ttk.Frame(self)
        self._cartoes_modulos = {}

        graficos = ttk.Frame(self)
        graficos.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        graficos.columnconfigure(0, weight=3)
        graficos.columnconfigure(1, weight=2)
        graficos.rowconfigure(0, weight=1)

        self._grafico_linhas = GraficoLinhas(graficos, altura=180)
        self._grafico_linhas.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._grafico_barras = GraficoBarras(graficos, altura=180)
        self._grafico_barras.grid(row=0, column=1, sticky="nsew")

        self._caixa_insights = ttk.LabelFrame(self, padding=8)
        self._caixa_insights.pack(fill=tk.X, padx=8, pady=(4, 8))
        self._lista_insights = ttk.Frame(self._caixa_insights)
        self._lista_insights.pack(fill=tk.X)

        self.aplicar_idioma()

    # --------------------------------------------------------------- API

    def aplicar_idioma(self) -> None:
        """Reaplica os textos no idioma atual e redesenha."""
        self._titulo.config(text=carregar_texto("dashboard"))
        self._botao_atualizar.config(text=carregar_texto("atualizar_lista"))
        self._botao_exportar.config(text=carregar_texto("exportar"))
        self._caixa_insights.config(text=carregar_texto("analise"))
        self._seletor.config(values=[self._rotulo_periodo(d) for d in PERIODOS])
        self._periodo_var.set(self._rotulo_periodo(self._dias))
        self._grafico_linhas.definir_titulo(carregar_texto("grafico_conclusoes"))
        self._grafico_barras.definir_titulo(carregar_texto("grafico_estado"))
        self._grafico_linhas.definir_texto_sem_dados(carregar_texto("sem_dados_periodo"))
        self._grafico_barras.definir_texto_sem_dados(carregar_texto("sem_dados_periodo"))
        if self._panorama is not None:
            self._mostrar(self._panorama)
        self._mostrar_indicadores_de_modulos()

    @property
    def dias(self) -> int:
        """Período em análise, em dias."""
        return self._dias

    @property
    def panorama(self) -> Optional[Panorama]:
        """Último panorama calculado (``None`` antes da primeira leitura)."""
        return self._panorama

    def definir_periodo(self, dias: int) -> None:
        """Muda o período e recalcula."""
        self._dias = dias
        self._periodo_var.set(self._rotulo_periodo(dias))
        self.atualizar()

    def atualizar(self) -> None:
        """Relê os dados e redesenha o painel.

        Uma falha aqui não pode derrubar a aplicação: sem permissão ou com erro
        de leitura, o painel mostra a razão e o resto da janela continua a
        funcionar.
        """
        if not permissoes.pode(Permissao.ANALYTICS_LER):
            self._mostrar_mensagem(carregar_texto("permissao_negada"))
            return
        try:
            self._panorama = self._obter_panorama(dias=self._dias)
        except Exception:
            logger.exception("Falha ao calcular o panorama do dashboard.")
            self._mostrar_mensagem(carregar_texto("dashboard_erro"))
            return
        self._mostrar(self._panorama)

    def _mostrar_indicadores_de_modulos(self) -> None:
        """Desenha os cartões que os módulos instalados declararam.

        O painel não sabe o que cada um mede. Pergunta ao registo, e mostra o
        que a sessão puder ver — quem não pode ver um número não vê o cartão,
        e não vê sequer que ele existe.
        """
        import indicadores

        for cartao in self._cartoes_modulos.values():
            cartao.destroy()
        self._cartoes_modulos = {}

        try:
            leituras = [l for l in indicadores.ler() if l.indicador.dono]
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao ler os indicadores dos módulos.")
            return

        if not leituras:
            self._linha_modulos.pack_forget()
            return

        for coluna, leitura in enumerate(leituras):
            cartao = CartaoKPI(
                self._linha_modulos,
                cor=COR_PRIMARIA if leitura.indicador.subir_e_bom else COR_ATENCAO,
                subir_e_bom=leitura.indicador.subir_e_bom,
            )
            cartao.atualizar(
                rotulo=carregar_texto(leitura.indicador.chave_titulo, leitura.chave),
                valor=leitura.valor.formatado(),
                variacao=leitura.valor.variacao,
            )
            cartao.grid(row=0, column=coluna, sticky="ew", padx=3, pady=4)
            self._linha_modulos.columnconfigure(coluna, weight=1)
            self._cartoes_modulos[leitura.chave] = cartao

        self._linha_modulos.pack(fill=tk.X, padx=8, before=self._grafico_linhas.master)

    def exportar(self) -> Optional[Path]:
        """Gera o relatório do período e grava-o no formato escolhido.

        Devolve o caminho gravado, ou ``None`` se o utilizador desistir ou não
        tiver permissão. Nunca levanta: uma falha vira mensagem e log.
        """
        if not permissoes.pode(Permissao.RELATORIOS_EXPORTAR):
            messagebox.showwarning(
                carregar_texto("aviso"), carregar_texto("permissao_negada"), parent=self
            )
            return None

        tipos = [
            (exportadores.descricao(f), f"*{exportadores.extensao(f)}")
            for f in servico.formatos_disponiveis()
        ]
        try:
            relatorio = relatorio_de_tarefas(dias=self._dias)
        except Exception:
            logger.exception("Falha ao construir o relatório.")
            messagebox.showerror(
                carregar_texto("erro"),
                carregar_texto("relatorio_erro_exportar"),
                parent=self,
            )
            return None

        escolhido = filedialog.asksaveasfilename(
            parent=self,
            title=carregar_texto("exportar_relatorio"),
            initialfile=servico.nome_sugerido(relatorio, servico.formatos_disponiveis()[0]),
            defaultextension=exportadores.extensao(servico.formatos_disponiveis()[0]),
            filetypes=tipos,
        )
        if not escolhido:
            return None

        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            caminho = servico.exportar(relatorio, Path(escolhido))
        except Exception:
            logger.exception("Falha ao exportar o relatório.")
            messagebox.showerror(
                carregar_texto("erro"),
                carregar_texto("relatorio_erro_exportar"),
                parent=self,
            )
            return None
        finally:
            self.configure(cursor="")

        messagebox.showinfo(
            carregar_texto("informacao"),
            carregar_texto("relatorio_exportado", caminho=caminho),
            parent=self,
        )
        return caminho

    # ------------------------------------------------------------ desenho

    def _mostrar(self, visao: Panorama) -> None:
        kpis = visao.kpis
        variacoes = visao.variacoes

        self._cartoes["criadas"].atualizar(
            carregar_texto("kpi_criadas", dias=visao.dias),
            str(visao.fluxo.criadas),
            variacoes.get("criadas"),
        )
        self._cartoes["concluidas"].atualizar(
            carregar_texto("kpi_concluidas", dias=visao.dias),
            str(visao.fluxo.concluidas),
            variacoes.get("concluidas"),
        )
        self._cartoes["pendentes"].atualizar(
            carregar_texto("kpi_pendentes"), str(kpis.pendentes)
        )
        self._cartoes["atrasadas"].atualizar(
            carregar_texto("kpi_atrasadas"), str(kpis.atrasadas)
        )
        self._cartoes["taxa"].atualizar(
            carregar_texto("kpi_taxa_conclusao"), f"{kpis.taxa_conclusao:.0f}%"
        )

        series: List[Serie] = [
            Serie(carregar_texto("serie_concluidas"), visao.concluidas, COR_SECUNDARIA),
            Serie(carregar_texto("serie_media_movel"), visao.concluidas_suavizadas, COR_PRIMARIA),
        ]
        if visao.previsao:
            series.append(
                Serie(carregar_texto("serie_previsao"), visao.previsao, COR_NEUTRA, tracejado=True)
            )
        self._grafico_linhas.definir_series(series)

        self._grafico_barras.definir_dados(
            [
                (carregar_texto("estado_concluidas"), kpis.concluidas),
                (carregar_texto("estado_pendentes"), kpis.pendentes - kpis.atrasadas),
                (carregar_texto("estado_atrasadas"), kpis.atrasadas),
            ],
            cores=(PREENCHER_BOM, PREENCHER_ATENCAO, PREENCHER_MAU),
        )

        self._mostrar_insights(visao.insights)

    def _mostrar_insights(self, encontrados: List[Insight]) -> None:
        for filho in self._lista_insights.winfo_children():
            filho.destroy()

        if not encontrados:
            ttk.Label(
                self._lista_insights,
                text=carregar_texto("sem_insights"),
                foreground=COR_NEUTRA,
            ).pack(anchor=tk.W)
            return

        for insight in encontrados[:4]:
            linha = ttk.Frame(self._lista_insights)
            linha.pack(fill=tk.X, anchor=tk.W)
            ttk.Label(
                linha,
                text=MARCAS_POR_NIVEL[insight.nivel],
                foreground=cores()[TOKEN_POR_NIVEL[insight.nivel]],
                font=fonte("destaque", negrito=True),
                width=2,
            ).pack(side=tk.LEFT)
            ttk.Label(linha, text=texto_do_insight(insight), wraplength=680, justify=tk.LEFT).pack(
                side=tk.LEFT, anchor=tk.W
            )

    def _mostrar_mensagem(self, mensagem: str) -> None:
        """Estado degradado: sem dados, sem permissão ou com erro."""
        for cartao in self._cartoes.values():
            cartao.atualizar(valor="—", variacao=None)
        self._grafico_linhas.definir_series([])
        self._grafico_barras.definir_dados([])
        for filho in self._lista_insights.winfo_children():
            filho.destroy()
        ttk.Label(self._lista_insights, text=mensagem, foreground=COR_NEUTRA).pack(anchor=tk.W)

    # ------------------------------------------------------------- eventos

    def _ao_mudar_periodo(self, _evento=None) -> None:
        rotulo = self._periodo_var.get()
        for dias in PERIODOS:
            if self._rotulo_periodo(dias) == rotulo:
                self.definir_periodo(dias)
                return

    def _ao_mudar_tarefas(self, _evento) -> None:
        """Reage a alterações nas tarefas, agrupando rajadas num só recálculo."""
        if self._agendamento is not None:
            try:
                self.after_cancel(self._agendamento)
            except tk.TclError:  # pragma: no cover - janela a fechar
                pass
        try:
            self._agendamento = self.after(ATRASO_ATUALIZACAO_MS, self._atualizar_agendado)
        except tk.TclError:  # pragma: no cover - widget já destruído
            self._agendamento = None

    def _atualizar_agendado(self) -> None:
        self._agendamento = None
        if self.winfo_exists():
            self.atualizar()

    def _ao_destruir(self, evento) -> None:
        if evento.widget is not self:
            return
        eventos.cancelar(self._inscricao)
        if self._agendamento is not None:
            try:
                self.after_cancel(self._agendamento)
            except tk.TclError:  # pragma: no cover
                pass
            self._agendamento = None

    @staticmethod
    def _rotulo_periodo(dias: int) -> str:
        return carregar_texto("periodo_dias", dias=dias)
