import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from services.export import (
    exportar_csv,
    exportar_excel,
    exportar_json,
    exportar_power_bi,
    exportar_sql,
    exportar_tsv,
    nome_padrao,
)
from services.importer import importar_planilha
from ui.theme import Palette, botao


class ReportsView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, set_status: Callable[[str], None], on_data_change: Callable[[], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.set_status, self.on_data_change = cores, set_status, on_data_change
        self.format_var = tk.StringVar(value="CSV (.csv)")
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="IMPORTAÇÃO E EXPORTAÇÃO", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text="Leve seus dados para a decisão.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 6))
        tk.Label(self, text="Troque dados com Excel, Power BI e ferramentas de análise sem perder a estrutura da sua base.", bg=self.cores.background, fg=self.cores.muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 18))
        grid = tk.Frame(self, bg=self.cores.background); grid.pack(fill=tk.X)
        for column in range(2): grid.columnconfigure(column, weight=1)
        self._card(grid, 0, 0, "IMPORTAR", "Trazer planilha", "Importe arquivos .xlsx, .xlsm ou .csv com cabeçalhos como Título, Categoria e Prazo.", "Importar dados", self._import)
        self._card(grid, 0, 1, "EXCEL", "Workbook analítico", "Cria abas de tarefas, indicadores, categorias e produtividade para continuar a análise no Excel.", "Exportar Excel", self._excel)
        self._card(grid, 1, 0, "POWER BI", "Modelo para Power BI", "Gera uma tabela de tarefas e outra de métricas no formato CSV que o Power BI lê nativamente.", "Exportar para Power BI", self._power_bi)
        self._open_data_card(grid)
        note = tk.Frame(self, bg=self.cores.surface_alt, highlightbackground=self.cores.border, highlightthickness=1); note.pack(fill=tk.X, pady=(16, 0))
        tk.Label(note, text="Como usar no Power BI", bg=self.cores.surface_alt, fg=self.cores.text, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(13, 3))
        tk.Label(note, text="No Power BI Desktop, escolha Obter dados › Texto/CSV e importe os dois arquivos gerados. A tabela de tarefas sustenta visuais por categoria, prioridade, status, data e atraso; a tabela de métricas serve para cartões executivos.", bg=self.cores.surface_alt, fg=self.cores.muted, wraplength=900, justify=tk.LEFT, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 13))

    def _card(self, parent: tk.Misc, row: int, column: int, tag: str, title: str, description: str, action: str, command: Callable[[], None]) -> None:
        card = tk.Frame(parent, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1)
        card.grid(row=row, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0), pady=(0, 10) if row == 0 else 0)
        tk.Label(card, text=tag, bg=self.cores.accent_soft, fg=self.cores.accent_dark, font=("Segoe UI", 8, "bold"), padx=9, pady=5).pack(anchor="w", padx=16, pady=(15, 11))
        tk.Label(card, text=title, bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16)
        tk.Label(card, text=description, bg=self.cores.surface, fg=self.cores.muted, wraplength=350, justify=tk.LEFT, font=("Segoe UI", 9), height=3).pack(anchor="w", padx=16, pady=(5, 12))
        botao(card, action, command, self.cores, primary=True).pack(anchor="w", padx=16, pady=(0, 16))

    def _open_data_card(self, parent: tk.Misc) -> None:
        card = tk.Frame(parent, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1)
        card.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(card, text="DADOS ABERTOS", bg=self.cores.accent_soft, fg=self.cores.accent_dark, font=("Segoe UI", 8, "bold"), padx=9, pady=5).pack(anchor="w", padx=16, pady=(15, 11))
        tk.Label(card, text="Exportação para análises", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16)
        tk.Label(card, text="Escolha um formato interoperável para notebooks, bancos de dados, ETL ou outras planilhas.", bg=self.cores.surface, fg=self.cores.muted, wraplength=350, justify=tk.LEFT, font=("Segoe UI", 9), height=2).pack(anchor="w", padx=16, pady=(5, 8))
        controls = tk.Frame(card, bg=self.cores.surface); controls.pack(anchor="w", padx=16, pady=(0, 16))
        ttk.Combobox(controls, textvariable=self.format_var, values=("CSV (.csv)", "TSV (.tsv)", "JSON (.json)", "SQL (.sql)"), state="readonly", width=17).pack(side=tk.LEFT)
        botao(controls, "Exportar", self._open_data, self.cores, compact=True).pack(side=tk.LEFT, padx=(7, 0))

    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(), title="Importar tarefas", filetypes=[("Planilhas e CSV", "*.xlsx *.xlsm *.csv"), ("Excel", "*.xlsx *.xlsm"), ("CSV", "*.csv")])
        if not path: return
        try:
            result = importar_planilha(path)
        except ImportError:
            messagebox.showwarning("OpenPyXL ausente", "Instale as dependências do projeto com: pip install -r requirements.txt", parent=self.winfo_toplevel()); return
        except (OSError, ValueError) as error:
            messagebox.showerror("Não foi possível importar", str(error), parent=self.winfo_toplevel()); return
        self.on_data_change()
        detail = f" {result.ignoradas} linha(s) ignorada(s)." if result.ignoradas else ""
        if result.avisos:
            detail += " " + " ".join(result.avisos)
        self.set_status(f"{result.importadas} tarefa(s) importada(s).{detail}")

    def _excel(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Exportar Excel", defaultextension=".xlsx", initialfile=nome_padrao("xlsx"), filetypes=[("Excel", "*.xlsx")])
        if not path: return
        try: exportar_excel(path)
        except ImportError:
            messagebox.showwarning("OpenPyXL ausente", "Instale as dependências do projeto com: pip install -r requirements.txt", parent=self.winfo_toplevel()); return
        self.set_status(f"Excel analítico exportado para {path}")

    def _power_bi(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Exportar para Power BI", defaultextension=".csv", initialfile="tarefas_powerbi.csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        tarefas, metricas = exportar_power_bi(path)
        self.set_status(f"Arquivos Power BI criados: {tarefas.name} e {metricas.name}")

    def _open_data(self) -> None:
        selected = self.format_var.get()
        extensions = {"CSV (.csv)": "csv", "TSV (.tsv)": "tsv", "JSON (.json)": "json", "SQL (.sql)": "sql"}
        extension = extensions[selected]
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), title="Exportar dados", defaultextension=f".{extension}", initialfile=nome_padrao(extension), filetypes=[(selected, f"*.{extension}")])
        if not path: return
        exporters = {"csv": exportar_csv, "tsv": exportar_tsv, "json": exportar_json, "sql": exportar_sql}
        exporters[extension](Path(path))
        self.set_status(f"Dados exportados em {selected} para {path}")
