"""Widget de calendário mensal em Tkinter puro.

Sem dependências externas: desenha uma grelha do mês, permite navegar entre
meses e selecionar um dia. Dias com tarefas são destacados.
"""

from __future__ import annotations

from aparencia import fonte
import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Callable, Iterable, Optional, Set

from language_manager import carregar_texto


class CalendarioWidget(ttk.Frame):
    """Calendário mensal navegável.

    Args:
        master: widget pai.
        ao_selecionar: chamado com a data ISO (``AAAA-MM-DD``) do dia clicado.
        dias_marcados: datas ISO a destacar (ex.: dias com tarefas).
    """

    def __init__(
        self,
        master: tk.Misc,
        ao_selecionar: Optional[Callable[[str], None]] = None,
        dias_marcados: Optional[Iterable[str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._ao_selecionar = ao_selecionar
        self._dias_marcados: Set[str] = set(dias_marcados or ())
        hoje = date.today()
        self._ano = hoje.year
        self._mes = hoje.month
        self._selecionado: Optional[str] = None

        self._cabecalho = ttk.Frame(self)
        self._cabecalho.pack(fill=tk.X)
        ttk.Button(self._cabecalho, text="◀", width=3, command=self._mes_anterior).pack(side=tk.LEFT)
        self._rotulo_mes = ttk.Label(self._cabecalho, anchor=tk.CENTER, font=fonte("destaque", negrito=True))
        self._rotulo_mes.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(self._cabecalho, text="▶", width=3, command=self._mes_seguinte).pack(side=tk.LEFT)

        self._grelha = ttk.Frame(self)
        self._grelha.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        ttk.Button(self, text=carregar_texto("hoje"), command=self.ir_para_hoje).pack(pady=(4, 0))

        self.redesenhar()

    # ------------------------------------------------------------------ API

    def definir_dias_marcados(self, dias: Iterable[str]) -> None:
        """Substitui o conjunto de dias destacados e redesenha."""
        self._dias_marcados = set(dias or ())
        self.redesenhar()

    def data_selecionada(self) -> Optional[str]:
        """Data ISO atualmente selecionada, se houver."""
        return self._selecionado

    def ir_para_hoje(self) -> None:
        """Volta ao mês corrente e seleciona o dia de hoje."""
        hoje = date.today()
        self._ano, self._mes = hoje.year, hoje.month
        self.redesenhar()
        self._selecionar(hoje.isoformat())

    def redesenhar(self) -> None:
        """Reconstrói a grelha do mês (também reaplica o idioma atual)."""
        for filho in self._grelha.winfo_children():
            filho.destroy()

        meses = carregar_texto("meses").split(",")
        nome_mes = meses[self._mes - 1] if len(meses) == 12 else str(self._mes)
        self._rotulo_mes.config(text=f"{nome_mes} {self._ano}")

        dias_semana = carregar_texto("dias_semana").split(",")
        for coluna, nome in enumerate(dias_semana[:7]):
            ttk.Label(self._grelha, text=nome, anchor=tk.CENTER, width=4).grid(
                row=0, column=coluna, padx=1, pady=1
            )

        for linha, semana in enumerate(calendar.monthcalendar(self._ano, self._mes), start=1):
            for coluna, dia in enumerate(semana):
                if dia == 0:
                    continue
                iso = date(self._ano, self._mes, dia).isoformat()
                texto = f"{dia}•" if iso in self._dias_marcados else str(dia)
                botao = ttk.Button(
                    self._grelha,
                    text=texto,
                    width=4,
                    command=lambda d=iso: self._selecionar(d),
                )
                botao.grid(row=linha, column=coluna, padx=1, pady=1)

    # ------------------------------------------------------------- internos

    def _selecionar(self, data_iso: str) -> None:
        self._selecionado = data_iso
        if self._ao_selecionar is not None:
            self._ao_selecionar(data_iso)

    def _mes_anterior(self) -> None:
        self._mes -= 1
        if self._mes == 0:
            self._mes, self._ano = 12, self._ano - 1
        self.redesenhar()

    def _mes_seguinte(self) -> None:
        self._mes += 1
        if self._mes == 13:
            self._mes, self._ano = 1, self._ano + 1
        self.redesenhar()
