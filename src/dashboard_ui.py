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
import painel_incluido
from core.permissoes import Permissao
from painel import Grelha, Rolo
from painel.contexto import Contexto
from aparencia import ESPACO, cores, fonte
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

#: A marca de cada gravidade. **Nenhuma se distingue de outra só pela cor.**
#:
#: Crítico e atenção partilhavam o "!" e separavam-se por vermelho contra
#: âmbar — que é a mesma marca para quem não distingue as duas cores, e são
#: cerca de 8% dos homens. O contraste do texto já era medido contra a WCAG;
#: isto é a outra metade da mesma regra.
MARCAS_POR_NIVEL = {
    Nivel.CRITICO: "!",
    Nivel.ATENCAO: "▲",
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
        barra.pack(fill=tk.X, pady=(ESPACO["largo"], ESPACO["normal"]),
                   padx=ESPACO["seccao"])

        # O título fica, mas escondido: a concha já põe o nome da secção na
        # barra de topo, e vê-lo duas vezes na mesma janela faz parecer que
        # há duas coisas abertas. Fica construído porque a tradução e os
        # testes falam dele, e porque uma instalação sem concha — um painel
        # embutido noutro sítio — volta a precisar dele.
        self._titulo = ttk.Label(barra, font=fonte("subtitulo", negrito=True))

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

        # O corpo é a grelha: os blocos são widgets registados, e um módulo
        # pode pôr o seu ao lado deles. Ver ADR-0010.
        painel_incluido.registar_incluidos()
        # A grelha vive dentro de um rolo. A 940x620 -- o minimo que a
        # aplicacao declarava -- a caixa "Analise" ficava abaixo da dobra e
        # nao havia como la chegar: calculada, desenhada, e inalcancavel.
        self._rolo = Rolo(self)
        self._rolo.pack(fill=tk.BOTH, expand=True)
        self._grelha = Grelha(self._rolo.interior,
                              padding=(ESPACO["largo"], 0, ESPACO["largo"], ESPACO["largo"]))
        self._grelha.pack(fill=tk.BOTH, expand=True)
        self._grelha.montar()

        # A razão de não haver nada vive **no painel**, e não num widget.
        #
        # Estava num widget, e a primeira execução mostrou porquê é que não
        # podia: sem permissão de análise nenhum widget é visível — incluindo
        # o que ia mostrar a razão. O painel ficava vazio e calado, que é pior
        # do que dizer "não tem permissão".
        self._aviso = ttk.Label(self, style="Suave.TLabel",
                                padding=(ESPACO["seccao"], ESPACO["largo"]))

        self.aplicar_idioma()

    # --------------------------------------------------------------- API

    def aplicar_idioma(self) -> None:
        """Reaplica os textos no idioma atual e redesenha."""
        self._titulo.config(text=carregar_texto("dashboard"))
        self._botao_atualizar.config(text=carregar_texto("atualizar_lista"))
        self._botao_exportar.config(text=carregar_texto("exportar"))
        self._seletor.config(values=[self._rotulo_periodo(d) for d in PERIODOS])
        self._periodo_var.set(self._rotulo_periodo(self._dias))

        # Cada widget traduz-se a si próprio quando recebe o contexto: o
        # painel não tem de conhecer os títulos de widgets que não escreveu —
        # e há-os, vindos de plugins.
        for declarado in self._grelha._ordem:
            widget = self._grelha.widget(declarado.id)
            titulo = getattr(widget, "definir_titulo", None)
            if callable(titulo):
                titulo(carregar_texto(declarado.chave_titulo, declarado.id))
            caixa = getattr(widget, "configure", None)
            if isinstance(widget, ttk.LabelFrame) and callable(caixa):
                caixa(text=carregar_texto(declarado.chave_titulo, declarado.id))
        self._mostrar(self._panorama) if self._panorama is not None else None
        self._grelha.atualizar_widgets(self._grelha.contexto())

    @property
    def _cartoes(self) -> dict:
        """Os cartões das tarefas, para quem os inspecione.

        Um atalho para dentro da grelha, e não estado próprio: o painel
        deixou de os possuir quando passaram a ser um widget registado.
        """
        widget = self._grelha.widget("tarefas.kpis")
        return getattr(widget, "cartoes", {})

    @property
    def _grafico_linhas(self):
        return self._grelha.widget("tarefas.serie")

    @property
    def _grafico_barras(self):
        return self._grelha.widget("tarefas.estado")

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
        """Dá o panorama aos widgets. Nenhum deles vai buscar dados."""
        self._dizer("")
        self._grelha.atualizar_widgets(Contexto(dias=self._dias, panorama=visao))
        self._rolo.sincronizar()

    def _mostrar_mensagem(self, mensagem: str) -> None:
        """Estado degradado: sem dados, sem permissão ou com erro.

        A razão viaja no contexto, e é cada widget que decide como a mostra —
        um cartão põe "—", a caixa de análise escreve a frase. O painel não
        precisa de saber quantos widgets existem para os apagar.
        """
        self._grelha.atualizar_widgets(
            Contexto(dias=self._dias, panorama=None, mensagem=mensagem)
        )
        self._rolo.sincronizar()
        self._dizer(mensagem)

    def _dizer(self, mensagem: str = "") -> None:
        """Mostra (ou esconde) a razão de o painel não ter o que mostrar."""
        if mensagem:
            self._aviso.configure(text=mensagem)
            # `before` tem de nomear um irmao. A grelha deixou de o ser
            # quando passou para dentro do rolo, e o `pack` com um
            # `before` de outro pai **nao faz nada nem levanta**: a
            # mensagem desaparecia do ecra em silencio.
            self._aviso.pack(anchor=tk.W, before=self._rolo)
        else:
            self._aviso.pack_forget()

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
