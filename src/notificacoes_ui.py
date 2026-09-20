"""O sino na barra de topo e o centro onde as notificações se leem.

A caixa (:mod:`notificacoes`) guarda; isto mostra. A separação é a de sempre
(ADR-0003): o que decide o que é anunciado não pode depender de haver uma
janela aberta.

Duas escolhas que valem a pena explicar:

**A frase é montada aqui, a partir da chave e dos parâmetros guardados.** É o
que faz uma caixa antiga aparecer em inglês quando se muda o idioma, em vez
de ficar metade numa língua e metade noutra.

**O centro abre por baixo do sino e não ao meio do ecrã.** Uma paleta de
comandos ao centro está certa — é o sítio para onde se olha quando se está a
procurar. Um sino é um sítio onde se reparou, e a resposta tem de aparecer
onde o olho já está.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

import notificacoes
from aparencia import ESPACO, cores, fonte
from core.log import obter_logger
from language_manager import carregar_texto, carregar_texto_plugin
from notificacoes import Notificacao

logger = obter_logger(__name__)

#: Quantas mostrar de uma vez. Ver dez é ler; ver duzentas é percorrer.
MOSTRAR = 12


def marca_e_cor(nivel: str):
    """A marca e o token de cor de uma gravidade.

    Vem das tabelas do painel em vez de as repetir aqui. A mesma conclusão
    não pode ter duas aparências consoante o sítio onde aparece — e uma cópia
    diverge no dia em que alguém mudar só uma das duas.

    A conversão existe porque a caixa guarda a gravidade como texto: o valor
    está num banco e tem de sobreviver a um ``Nivel`` que ganhe ou perca
    membros. Um valor que já não exista vale ``informacao``, que é a forma
    discreta de mostrar uma coisa que não se sabe classificar.
    """
    from analitica.insights import Nivel
    from dashboard_ui import MARCAS_POR_NIVEL, TOKEN_POR_NIVEL

    try:
        grau = Nivel(nivel)
    except ValueError:
        grau = Nivel.INFORMACAO
    return MARCAS_POR_NIVEL[grau], TOKEN_POR_NIVEL[grau]


def texto_da_notificacao(notificacao: Notificacao) -> str:
    """A frase de uma notificação, traduzida agora e com os seus números.

    A chave é procurada primeiro nos textos do módulo que a criou e só depois
    nos da aplicação — é o que permite a um módulo anunciar nas suas próprias
    palavras. Uma chave desconhecida devolve-se a si mesma, que é como o texto
    livre de uma regra de automação chega intacto ao ecrã.
    """
    try:
        return carregar_texto_plugin(
            notificacao.origem, notificacao.chave, **notificacao.parametros
        )
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha a traduzir a notificação %s.", notificacao.id)
        return notificacao.chave


def _quando(momento: str) -> str:
    """A data sem os segundos, que ninguém lê."""
    texto = str(momento or "")
    return texto.replace("T", " ")[:16]


class CentroDeNotificacoes(tk.Toplevel):
    """A lista do que foi anunciado a quem está em sessão."""

    def __init__(self, master: tk.Misc, ao_mudar: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.withdraw()
        self._ao_mudar = ao_mudar
        self._itens: List[Notificacao] = []

        self.title(carregar_texto("notificacoes_titulo", "Notificações"))
        self.transient(master)
        self.resizable(False, True)

        corpo = ttk.Frame(self, padding=ESPACO["confortavel"])
        corpo.pack(fill=tk.BOTH, expand=True)

        cabecalho = ttk.Frame(corpo)
        cabecalho.pack(fill=tk.X, pady=(0, ESPACO["normal"]))
        ttk.Label(
            cabecalho,
            text=carregar_texto("notificacoes_titulo", "Notificações"),
            font=fonte("subtitulo", negrito=True),
        ).pack(side=tk.LEFT)
        self._botao_todas = ttk.Button(
            cabecalho,
            text=carregar_texto("notificacoes_marcar_todas", "Marcar todas como lidas"),
            command=self._marcar_todas,
        )
        self._botao_todas.pack(side=tk.RIGHT)

        self._lista = ttk.Frame(corpo)
        self._lista.pack(fill=tk.BOTH, expand=True)

        rodape = ttk.Frame(corpo)
        rodape.pack(fill=tk.X, pady=(ESPACO["normal"], 0))
        self._botao_limpar = ttk.Button(
            rodape,
            text=carregar_texto("notificacoes_limpar_lidas", "Limpar as lidas"),
            command=self._limpar_lidas,
        )
        self._botao_limpar.pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _: self.destroy())

        self.recarregar()
        self._junto_ao_sino()
        self.deiconify()
        self.focus_set()

    # --------------------------------------------------------------- desenho

    def recarregar(self) -> None:
        """Volta a desenhar a lista a partir da caixa."""
        for filho in self._lista.winfo_children():
            filho.destroy()

        try:
            self._itens = notificacoes.listar(limite=MOSTRAR)
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao ler a caixa de notificações.")
            self._itens = []

        if not self._itens:
            ttk.Label(
                self._lista,
                text=carregar_texto("notificacoes_vazio", "Nada por ler."),
                style="Suave.TLabel",
            ).pack(anchor=tk.W, pady=ESPACO["normal"])
            self._botao_todas.state(["disabled"])
            self._botao_limpar.state(["disabled"])
            return

        self._botao_todas.state(["!disabled"])
        self._botao_limpar.state(["!disabled"])
        for notificacao in self._itens:
            self._desenhar(notificacao)

    def _desenhar(self, notificacao: Notificacao) -> None:
        paleta = cores()
        marca, token = marca_e_cor(notificacao.nivel)

        linha = ttk.Frame(self._lista, padding=(0, ESPACO["apertado"]))
        linha.pack(fill=tk.X)

        ttk.Label(
            linha,
            text=marca,
            foreground=paleta[token],
            font=fonte("destaque", negrito=True),
            width=2,
        ).pack(side=tk.LEFT, anchor=tk.N)

        texto = ttk.Frame(linha)
        texto.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # O que está por ler vem a negrito. É a única diferença, e chega:
        # duas cores para dizer "lido" competiriam com as da gravidade, que
        # é a informação que importa.
        ttk.Label(
            texto,
            text=texto_da_notificacao(notificacao),
            font=fonte("corpo", negrito=not notificacao.lida),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        ttk.Label(
            texto, text=_quando(notificacao.criada_em), style="Tenue.TLabel"
        ).pack(anchor=tk.W)

        if not notificacao.lida:
            ttk.Button(
                linha,
                text=carregar_texto("notificacoes_marcar_lida", "Lida"),
                command=lambda ident=notificacao.id: self._marcar(ident),
            ).pack(side=tk.RIGHT, anchor=tk.N, padx=(ESPACO["normal"], 0))

    def _junto_ao_sino(self) -> None:
        """Encosta o centro ao canto superior direito da janela principal."""
        self.update_idletasks()
        pai = self.master
        try:
            largura = self.winfo_width()
            x = pai.winfo_rootx() + pai.winfo_width() - largura - ESPACO["seccao"]
            y = pai.winfo_rooty() + ESPACO["pagina"] + ESPACO["seccao"]
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:  # pragma: no cover - sem pai visível
            pass

    # ----------------------------------------------------------------- ações

    def _avisar(self) -> None:
        if self._ao_mudar is not None:
            try:
                self._ao_mudar()
            except Exception:  # pragma: no cover - defensivo
                logger.exception("Falha a atualizar o sino.")

    def _marcar(self, ident: int) -> None:
        try:
            notificacoes.marcar_lida(ident)
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao marcar a notificação %s como lida.", ident)
        self.recarregar()
        self._avisar()

    def _marcar_todas(self) -> None:
        try:
            notificacoes.marcar_todas_lidas()
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao marcar as notificações como lidas.")
        self.recarregar()
        self._avisar()

    def _limpar_lidas(self) -> None:
        try:
            notificacoes.limpar_lidas()
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao limpar as notificações lidas.")
        self.recarregar()
        self._avisar()


def abrir(master: tk.Misc, ao_mudar: Optional[Callable[[], None]] = None):
    """Abre o centro sobre a janela indicada."""
    return CentroDeNotificacoes(master, ao_mudar=ao_mudar)
