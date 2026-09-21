import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from database import buscar_tarefas
from ui.theme import Palette, botao


class DataView(tk.Frame):
    """Pré-visualização tabular para decisões e integrações analíticas."""
    def __init__(self, master: tk.Misc, cores: Palette, on_reports: Callable[[], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_reports = cores, on_reports
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="DADOS", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text="Uma tabela pronta para análise.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 18))
        hint = tk.Frame(self, bg=self.cores.accent_soft, highlightbackground=self.cores.border, highlightthickness=1)
        hint.pack(fill=tk.X, pady=(0, 12))
        tk.Label(hint, text="MODELO ANALÍTICO", bg=self.cores.accent_soft, fg=self.cores.accent_dark, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=15, pady=(12, 2))
        tk.Label(hint, text="Cada linha representa uma tarefa; categoria, prioridade, status e prazo podem ser usados como dimensões em Excel, Power BI ou notebooks de dados.", bg=self.cores.accent_soft, fg=self.cores.text, font=("Segoe UI", 9), justify=tk.LEFT, wraplength=850).pack(anchor="w", padx=15, pady=(0, 12))
        botao(hint, "Abrir importação e exportação", self.on_reports, self.cores, primary=True, compact=True).pack(anchor="e", padx=15, pady=(0, 12))
        table_card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); table_card.pack(fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(table_card, bg=self.cores.surface); toolbar.pack(fill=tk.X, padx=16, pady=(13, 7))
        tk.Label(toolbar, text="Tabela fato: tarefas", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        self.summary = tk.Label(toolbar, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 9)); self.summary.pack(side=tk.RIGHT)
        columns = ("id", "titulo", "categoria", "prioridade", "status", "data", "hora")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings")
        labels = {"id": "ID", "titulo": "TÍTULO", "categoria": "CATEGORIA", "prioridade": "PRIORIDADE", "status": "STATUS", "data": "DATA", "hora": "HORA"}
        widths = {"id": 55, "titulo": 360, "categoria": 135, "prioridade": 105, "status": 110, "data": 100, "hora": 70}
        for column in columns:
            self.tree.heading(column, text=labels[column]); self.tree.column(column, width=widths[column], anchor=tk.W, stretch=column == "titulo")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        rows = buscar_tarefas()
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", tk.END, values=(row["id"], row["titulo"], row["categoria"], row["prioridade"], row["status"], row["data_limite"] or "—", row["hora_limite"] or "—"))
        self.summary.configure(text=f"{len(rows)} linha(s) disponíveis")
