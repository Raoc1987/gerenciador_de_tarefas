"""Calendar Integration — mostra as tarefas num calendário mensal.

Este é um plugin real e completo, não uma demonstração vazia: reutiliza o
widget de calendário que já existe na aplicação (:mod:`calendar_widget`) e
liga-o às tarefas através do :class:`~core.plugin_api.ContextoPlugin`.

Nota de arquitetura: o plugin pode importar widgets reutilizáveis da
aplicação, mas **não** acede ao banco nem à janela principal diretamente —
tudo o que precisa (tarefas, tradução, configuração, UI) chega pelo contexto.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import List, Optional

from calendar_widget import CalendarioWidget
from core.plugin_api import Plugin
from utils import formatar_data

CHAVE_ULTIMA_DATA = "ultima_data"


class PainelCalendario(ttk.Frame):
    """Calendário à esquerda, tarefas do dia selecionado à direita."""

    def __init__(self, master: tk.Misc, contexto) -> None:
        super().__init__(master)
        self._contexto = contexto
        self._data: Optional[str] = None

        esquerda = ttk.Frame(self)
        esquerda.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        self._calendario = CalendarioWidget(
            esquerda,
            ao_selecionar=self.mostrar_dia,
            dias_marcados=self._dias_com_tarefas(),
        )
        self._calendario.pack()

        direita = ttk.Frame(self)
        direita.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._titulo = ttk.Label(direita, font=("Arial", 12, "bold"))
        self._titulo.pack(anchor=tk.W)

        self._lista = tk.Listbox(direita, height=12)
        self._lista.pack(fill=tk.BOTH, expand=True, pady=6)

        formulario = ttk.Frame(direita)
        formulario.pack(fill=tk.X)
        self._entrada = ttk.Entry(formulario)
        self._entrada.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._botao = ttk.Button(
            formulario,
            text=contexto.traduzir("adicionar"),
            command=self._adicionar,
        )
        self._botao.pack(side=tk.LEFT, padx=(6, 0))

        guardada = contexto.config().get(CHAVE_ULTIMA_DATA)
        self.mostrar_dia(guardada or date.today().isoformat())

    # ------------------------------------------------------------ interno

    def _dias_com_tarefas(self) -> List[str]:
        if self._contexto.tarefas is None:
            return []
        return [t[2] for t in self._contexto.tarefas.listar() if t[2]]

    def mostrar_dia(self, data_iso: str) -> None:
        """Apresenta as tarefas com vencimento em ``data_iso``."""
        self._data = data_iso
        self._titulo.config(
            text=self._contexto.traduzir(
                "tarefas_do_dia", data=formatar_data(data_iso)
            )
        )
        self._lista.delete(0, tk.END)

        tarefas = (
            self._contexto.tarefas.listar_por_data(data_iso)
            if self._contexto.tarefas
            else []
        )
        if not tarefas:
            self._lista.insert(tk.END, self._contexto.traduzir("sem_tarefas_dia"))
            return
        for tarefa in tarefas:
            marca = "[✔]" if tarefa[3] else "[  ]"
            self._lista.insert(tk.END, f"{marca} {tarefa[1]}")

        guardada = self._contexto.config()
        guardada[CHAVE_ULTIMA_DATA] = data_iso
        self._contexto.guardar_config(guardada)

    def _adicionar(self) -> None:
        descricao = self._entrada.get().strip()
        if not descricao or self._data is None or self._contexto.tarefas is None:
            return
        self._contexto.tarefas.adicionar(descricao, self._data)
        self._entrada.delete(0, tk.END)
        self._calendario.definir_dias_marcados(self._dias_com_tarefas())
        self.mostrar_dia(self._data)

    def atualizar(self) -> None:
        """Relê as tarefas (usado quando a aba volta a ficar visível)."""
        self._calendario.definir_dias_marcados(self._dias_com_tarefas())
        if self._data:
            self.mostrar_dia(self._data)


class CalendarPlugin(Plugin):
    """Regista uma aba de calendário na janela principal."""

    def __init__(self, contexto) -> None:
        super().__init__(contexto)
        self._painel: Optional[PainelCalendario] = None

    def inicializar(self) -> None:
        self.contexto.logger.info("Calendar Integration carregado.")

    def ativar(self) -> None:
        if self.contexto.ui is None:
            # Sem interface (por exemplo, em testes): nada a mostrar.
            self.contexto.logger.info("Sem interface disponível; aba não registada.")
            return
        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba"),
            self._construir_painel,
        )

    def _construir_painel(self, pai):
        self._painel = PainelCalendario(pai, self.contexto)
        return self._painel

    def desativar(self) -> None:
        # As abas são removidas pela aplicação; aqui apenas largamos a referência.
        self._painel = None

    def finalizar(self) -> None:
        self.contexto.logger.info("Calendar Integration descarregado.")
