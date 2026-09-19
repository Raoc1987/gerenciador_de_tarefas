"""A grelha do painel: arruma os widgets registados e reparte-se com a janela.

Quatro colunas num ecrã largo, duas num médio, uma num estreito. Não é
enfeite: a aplicação abre a 1180 mas tem de servir um portátil a 1366×768 com
escala a 125%, onde sobram cerca de 1090 píxeis — e cinco cartões lado a lado
nessa largura ficam com um número e meia palavra cada.

Um widget declara **quantas colunas quer**. Quando a grelha encolhe, o pedido
é cortado ao que existe: quem pediu 4 num arranjo de 2 recebe 2, e continua a
ocupar a linha inteira, que é o que ele queria dizer.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from aparencia import ESPACO
from core.log import obter_logger
from painel import registo
from painel.contexto import Contexto

logger = obter_logger(__name__)

#: Abaixo destas larguras (em píxeis), a grelha passa a ter menos colunas.
#:
#: **A largura é a da grelha, não a da janela** — a barra lateral já está
#: descontada quando isto é perguntado. Num portátil a 1366×768 com escala a
#: 125% sobram cerca de 1090px de janela, e cerca de 866 de grelha, que é o
#: que põe esse portátil em duas colunas.
#:
#: Os cortes vêm da largura mínima legível de um cartão com um número grande
#: e um rótulo: cerca de 230px mais o espaçamento.
CORTE_DUAS = 1040
CORTE_UMA = 560


def colunas_para(largura: int) -> int:
    """Quantas colunas cabem nesta largura."""
    if largura < CORTE_UMA:
        return 1
    if largura < CORTE_DUAS:
        return 2
    return registo.COLUNAS


class Grelha(ttk.Frame):
    """Constrói os widgets registados e arruma-os.

    Os widgets são construídos **uma vez**. Reconstruí-los ao mudar de
    tamanho perderia o que estivesse escolhido dentro deles e piscaria o ecrã
    inteiro a cada píxel de arrasto do rato.
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._construidos: Dict[str, Any] = {}
        self._ordem: List[registo.Widget] = []
        self._colunas = registo.COLUNAS
        self._ultima_largura = 0
        self._contexto = Contexto()
        self.bind("<Configure>", self._ao_redimensionar)

    # ------------------------------------------------------------ montagem

    def montar(self) -> None:
        """(Re)constrói a grelha a partir do registo.

        Chamada quando o conjunto de widgets muda — um plugin que entra ou
        sai. Não é chamada ao redimensionar: isso só muda a arrumação.
        """
        for filho in list(self._construidos.values()):
            try:
                filho.destroy()
            except tk.TclError:  # pragma: no cover - já destruído
                pass
        self._construidos = {}
        self._ordem = registo.disponiveis()

        for declarado in self._ordem:
            try:
                widget = declarado.construir(self)
            except Exception:
                # Um widget partido não pode levar o painel com ele — vai
                # haver widgets de plugins aqui dentro.
                logger.exception("O widget de painel %s falhou a construir.", declarado.id)
                continue
            self._construidos[declarado.id] = widget

        self._arrumar()

    def _arrumar(self) -> None:
        """Põe cada widget na sua célula, com as colunas que couberem."""
        for coluna in range(registo.COLUNAS):
            self.columnconfigure(coluna, weight=1 if coluna < self._colunas else 0,
                                 minsize=0)

        linha = coluna_atual = 0
        for declarado in self._ordem:
            widget = self._construidos.get(declarado.id)
            if widget is None:
                continue
            largura = min(declarado.largura, self._colunas)
            if coluna_atual + largura > self._colunas:
                linha += 1
                coluna_atual = 0
            widget.grid(
                row=linha,
                column=coluna_atual,
                columnspan=largura,
                sticky=tk.NSEW,
                padx=ESPACO["apertado"],
                pady=ESPACO["apertado"],
            )
            coluna_atual += largura
            if coluna_atual >= self._colunas:
                linha += 1
                coluna_atual = 0

    def _ao_redimensionar(self, evento) -> None:
        """Muda o arranjo quando o número de colunas muda — e só então.

        Sem esta guarda, cada píxel de arrasto do rato refazia a grelha
        inteira, e o redimensionamento ficava aos solavancos.
        """
        if evento.width == self._ultima_largura:
            return
        self._ultima_largura = evento.width
        novas = colunas_para(evento.width)
        if novas != self._colunas:
            self._colunas = novas
            self._arrumar()

    # ---------------------------------------------------------- atualização

    def atualizar_widgets(self, contexto: Contexto) -> None:
        """Dá o contexto novo a quem o saiba receber.

        Quem não tiver ``atualizar`` é desenhado uma vez e fica quieto, o que
        chega para uma nota ou uma legenda. Quem o tiver e rebentar é
        registado e ignorado: um widget partido não apaga os outros.
        """
        self._contexto = contexto
        for declarado in self._ordem:
            widget = self._construidos.get(declarado.id)
            atualizar = getattr(widget, "atualizar", None)
            if not callable(atualizar):
                continue
            try:
                atualizar(contexto)
            except Exception:
                logger.exception("O widget de painel %s falhou a atualizar.", declarado.id)

    def contexto(self) -> Contexto:
        """O contexto em vigor."""
        return self._contexto

    def widget(self, id: str) -> Optional[Any]:
        """O widget construído com este id, se existir.

        Para quem precise de lhe chamar alguma coisa — a exportação, um
        teste. Devolver ``None`` em vez de levantar: um widget pode não estar
        lá por falta de permissão, e isso não é um erro.
        """
        return self._construidos.get(id)
