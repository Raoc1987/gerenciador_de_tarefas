"""Tela de pesquisa global (Ctrl+F).

Uma caixa, e os resultados agrupados por onde foram encontrados. O
agrupamento não é decoração: sem ele, "Engenharia" a aparecer três vezes não
diz se são três unidades ou uma unidade, uma tarefa e uma regra.

Procura enquanto se escreve, mas **não a cada tecla**: espera que a escrita
pare. Pesquisar a cada letra faz o trabalho todo cinco vezes para deitar fora
quatro, e numa base grande nota-se.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

import pesquisa
from core.log import obter_logger
from language_manager import carregar_texto
from pesquisa import Resultado

logger = obter_logger(__name__)

COR_NEUTRA = cores()["texto_suave"]

#: Quanto tempo se espera, em ms, depois da última tecla.
ESPERA_MS = 250


class JanelaPesquisa(tk.Toplevel):
    """Procura em tudo o que estiver registado."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("pesquisa"))
        self.geometry("620x460")
        self.transient(master)
        self._agendado: Optional[str] = None
        self._resultados: List[Resultado] = []

        corpo = ttk.Frame(self, padding=12)
        corpo.pack(fill=tk.BOTH, expand=True)

        self.entrada = ttk.Entry(corpo, font=fonte("destaque"))
        self.entrada.pack(fill=tk.X)
        self.entrada.bind("<KeyRelease>", self._ao_escrever)
        self.entrada.bind("<Return>", lambda _: self.procurar())
        self.entrada.bind("<Escape>", lambda _: self.destroy())
        self.entrada.focus_set()

        self.mensagem = ttk.Label(
            corpo, foreground=COR_NEUTRA, wraplength=580, justify=tk.LEFT
        )
        self.mensagem.pack(anchor=tk.W, pady=(6, 8))
        self._dizer(carregar_texto("pesquisa_ajuda", minimo=pesquisa.MINIMO_DO_TERMO))

        self.arvore = ttk.Treeview(corpo, columns=("detalhe",), height=16)
        self.arvore.heading("#0", text=carregar_texto("pesquisa_encontrado"), anchor=tk.W)
        self.arvore.heading("detalhe", text=carregar_texto("pesquisa_contexto"), anchor=tk.W)
        self.arvore.column("#0", width=330, anchor=tk.W)
        self.arvore.column("detalhe", width=240, anchor=tk.W)
        self.arvore.pack(fill=tk.BOTH, expand=True)

        ttk.Button(corpo, text=carregar_texto("fechar"), command=self.destroy).pack(
            anchor=tk.E, pady=(10, 0)
        )

    # ---------------------------------------------------------------- apoio

    def _dizer(self, texto: str) -> None:
        self.mensagem.configure(text=texto)

    def resultados(self) -> List[Resultado]:
        """O que está a ser mostrado."""
        return list(self._resultados)

    def _ao_escrever(self, _evento=None) -> None:
        """Adia a pesquisa até a escrita parar."""
        if self._agendado is not None:
            self.after_cancel(self._agendado)
        self._agendado = self.after(ESPERA_MS, self.procurar)

    # ---------------------------------------------------------------- ação

    def procurar(self) -> List[Resultado]:
        """Procura e mostra, agrupado por fonte."""
        self._agendado = None
        for linha in self.arvore.get_children():
            self.arvore.delete(linha)

        termo = self.entrada.get().strip()
        if len(termo) < pesquisa.MINIMO_DO_TERMO:
            self._resultados = []
            self._dizer(carregar_texto("pesquisa_ajuda", minimo=pesquisa.MINIMO_DO_TERMO))
            return []

        por_fonte: Dict[str, List[Resultado]] = pesquisa.agrupados(termo)
        self._resultados = [r for lista in por_fonte.values() for r in lista]

        for fonte, resultados in sorted(por_fonte.items()):
            grupo = self.arvore.insert(
                "",
                tk.END,
                text=f"{carregar_texto('pesquisa_fonte_' + fonte, fonte)} ({len(resultados)})",
                open=True,
            )
            for resultado in resultados:
                self.arvore.insert(
                    grupo, tk.END, text=resultado.titulo, values=(resultado.detalhe,)
                )

        if self._resultados:
            self._dizer(
                carregar_texto(
                    "pesquisa_resumo", total=len(self._resultados), fontes=len(por_fonte)
                )
            )
        else:
            self._dizer(carregar_texto("pesquisa_sem_resultados", termo=termo))
        return self._resultados
