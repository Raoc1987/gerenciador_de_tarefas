import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import messagebox, ttk

from database import adicionar_tarefa, atualizar_status, atualizar_tarefa, buscar_tarefa_por_id, buscar_tarefas, excluir_tarefa, listar_categorias, listar_projetos
from ui.theme import Palette, botao

PRIORIDADES = ("Baixa", "Media", "Alta")
CATEGORIAS = ("Geral", "Trabalho", "Estudo", "Pessoal", "Saude", "Financas")


class TasksView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, on_change: Callable[[], None], set_status: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_change, self.set_status = cores, on_change, set_status
        self.titulo_var = tk.StringVar(); self.categoria_var = tk.StringVar(value=CATEGORIAS[0]); self.projeto_var = tk.StringVar(value="Sem projeto"); self.prioridade_var = tk.StringVar(value="Media")
        self.data_limite_var = tk.StringVar(); self.hora_limite_var = tk.StringVar(); self.busca_var = tk.StringVar(); self.filtro_status_var = tk.StringVar(value="Todos")
        self.filtro_categoria_var = tk.StringVar(value="Todas"); self.filtro_inicio_var = tk.StringVar(); self.filtro_fim_var = tk.StringVar(); self.summary_var = tk.StringVar(value="0 tarefas")
        self.tarefa_em_edicao_id: int | None = None
        self.project_ids: dict[str, int] = {}
        self._build()
        self.refresh_catalogs()

    def _build(self) -> None:
        header = tk.Frame(self, bg=self.cores.background); header.pack(fill=tk.X, pady=(4, 16))
        tk.Label(header, text="TAREFAS", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(header, text="Planeje o próximo movimento.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(side=tk.LEFT, pady=(3, 0))
        tk.Label(header, textvariable=self.summary_var, bg=self.cores.background, fg=self.cores.muted, font=("Segoe UI", 9)).pack(side=tk.RIGHT, pady=(10, 0))
        form = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); form.pack(fill=tk.X, pady=(0, 12))
        tk.Label(form, text="Adicionar ou editar tarefa", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=8, sticky="w", padx=16, pady=(14, 9))
        self._field(form, "Título", ttk.Entry(form, textvariable=self.titulo_var), 1, 0, sticky="ew")
        self.categoria_combo = ttk.Combobox(form, textvariable=self.categoria_var, values=CATEGORIAS, state="readonly", width=13)
        self._field(form, "Categoria", self.categoria_combo, 1, 1)
        self.projeto_combo = ttk.Combobox(form, textvariable=self.projeto_var, values=("Sem projeto",), state="readonly", width=15)
        self._field(form, "Projeto", self.projeto_combo, 1, 2)
        self._field(form, "Prioridade", ttk.Combobox(form, textvariable=self.prioridade_var, values=PRIORIDADES, state="readonly", width=10), 1, 3)
        self._field(form, "Prazo (AAAA-MM-DD)", ttk.Entry(form, textvariable=self.data_limite_var, width=14), 1, 4)
        self._field(form, "Hora (HH:MM)", ttk.Entry(form, textvariable=self.hora_limite_var, width=9), 1, 5)
        actions = tk.Frame(form, bg=self.cores.surface); actions.grid(row=2, column=6, rowspan=2, sticky="se", padx=(0, 16), pady=(23, 15))
        botao(actions, "Salvar", self._save, self.cores, primary=True, compact=True).pack(side=tk.LEFT)
        botao(actions, "Limpar", self._clear, self.cores, compact=True).pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(form, text="Descrição", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=3, column=0, sticky="w", padx=16, pady=(8, 2))
        self.descricao_text = tk.Text(form, height=3, wrap=tk.WORD, bg=self.cores.surface_alt, fg=self.cores.text, insertbackground=self.cores.text, relief=tk.FLAT, padx=8, pady=7, font=("Segoe UI", 9), highlightthickness=1, highlightbackground=self.cores.border, highlightcolor=self.cores.accent)
        self.descricao_text.grid(row=4, column=0, columnspan=6, sticky="ew", padx=16, pady=(0, 15)); form.columnconfigure(0, weight=4)
        filter_card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); filter_card.pack(fill=tk.X, pady=(0, 10))
        tk.Label(filter_card, text="Refinar lista", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=7, sticky="w", padx=16, pady=(12, 6))
        self._field(filter_card, "Busca", ttk.Entry(filter_card, textvariable=self.busca_var), 1, 0, sticky="ew")
        self._field(filter_card, "Status", ttk.Combobox(filter_card, textvariable=self.filtro_status_var, values=("Todos", "Pendente", "Concluida"), state="readonly", width=12), 1, 1)
        self._field(filter_card, "Categoria", ttk.Combobox(filter_card, textvariable=self.filtro_categoria_var, values=("Todas", *CATEGORIAS), state="readonly", width=14), 1, 2)
        self._field(filter_card, "De", ttk.Entry(filter_card, textvariable=self.filtro_inicio_var, width=12), 1, 3)
        self._field(filter_card, "Até", ttk.Entry(filter_card, textvariable=self.filtro_fim_var, width=12), 1, 4)
        botao(filter_card, "Aplicar", self.refresh, self.cores, primary=True, compact=True).grid(row=2, column=5, padx=(3, 16), pady=(0, 10), sticky="e"); filter_card.columnconfigure(0, weight=3)
        table_card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); table_card.pack(fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(table_card, bg=self.cores.surface); toolbar.pack(fill=tk.X, padx=16, pady=(12, 7))
        tk.Label(toolbar, text="Lista de tarefas", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        botao(toolbar, "Concluir / reabrir", self._toggle_status, self.cores, compact=True).pack(side=tk.RIGHT)
        botao(toolbar, "Excluir", self._delete, self.cores, compact=True, danger=True).pack(side=tk.RIGHT, padx=(0, 6))
        columns = ("id", "titulo", "projeto", "categoria", "prioridade", "status", "data_limite", "hora_limite")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")
        headers = {"id": "ID", "titulo": "TÍTULO", "projeto": "PROJETO", "categoria": "CATEGORIA", "prioridade": "PRIORIDADE", "status": "STATUS", "data_limite": "PRAZO", "hora_limite": "HORA"}; widths = {"id": 50, "titulo": 250, "projeto": 130, "categoria": 110, "prioridade": 90, "status": 95, "data_limite": 100, "hora_limite": 65}
        for column in columns: self.tree.heading(column, text=headers[column]); self.tree.column(column, width=widths[column], anchor=tk.W, stretch=column == "titulo")
        self.tree.tag_configure("pending", background=self.cores.surface); self.tree.tag_configure("done", background=self.cores.accent_soft); self.tree.tag_configure("late", background="#FCE8EA" if self.cores.name == "light" else "#40212C")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._load_selected()); self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _field(self, parent: tk.Misc, label: str, widget: tk.Widget, row: int, column: int, *, sticky: str = "w") -> None:
        padx = (16 if column == 0 else 5, 5)
        tk.Label(parent, text=label, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=row, column=column, sticky="w", padx=padx, pady=(0, 2))
        widget.grid(row=row + 1, column=column, sticky=sticky, padx=padx, pady=(0, 10))

    def apply_search(self, query: str) -> None:
        self.busca_var.set(query); self.refresh()

    def refresh_catalogs(self) -> None:
        categorias = [row["nome"] for row in listar_categorias()]
        projetos = list(listar_projetos(apenas_ativos=True))
        self.project_ids = {row["nome"]: row["id"] for row in projetos}
        self.categoria_combo.configure(values=tuple(categorias or CATEGORIAS))
        self.projeto_combo.configure(values=("Sem projeto", *self.project_ids))
        if self.categoria_var.get() not in categorias:
            self.categoria_var.set(categorias[0] if categorias else CATEGORIAS[0])
        if self.projeto_var.get() not in self.project_ids:
            self.projeto_var.set("Sem projeto")

    def focus_task(self, task_id: int) -> None:
        """Seleciona uma tarefa a partir de alertas ou links internos."""
        self.refresh()
        for item in self.tree.get_children():
            if int(self.tree.item(item, "values")[0]) == task_id:
                self.tree.selection_set(item); self.tree.focus(item); self.tree.see(item)
                self._load_selected()
                return

    def refresh(self) -> None:
        start = self._valid_date(self.filtro_inicio_var.get().strip(), show_error=False); end = self._valid_date(self.filtro_fim_var.get().strip(), show_error=False)
        if (self.filtro_inicio_var.get().strip() and start is None) or (self.filtro_fim_var.get().strip() and end is None): self.set_status("Use AAAA-MM-DD para filtrar por prazo."); return
        tasks = [dict(row) for row in buscar_tarefas(termo=self.busca_var.get().strip(), status=self.filtro_status_var.get(), categoria=self.filtro_categoria_var.get(), data_inicio=start or "", data_fim=end or "")]
        self.tree.delete(*self.tree.get_children()); today = datetime.now().date()
        for task in tasks:
            tag = "done" if task["status"] == "Concluida" else "pending"
            if task["status"] == "Pendente" and task["data_limite"] and datetime.strptime(task["data_limite"], "%Y-%m-%d").date() < today: tag = "late"
            self.tree.insert("", tk.END, values=(task["id"], task["titulo"], task["projeto"] or "—", task["categoria"], task["prioridade"], task["status"], task["data_limite"] or "—", task["hora_limite"] or "—"), tags=(tag,))
        self.summary_var.set(f"{len(tasks)} tarefa(s) na lista")

    def _save(self) -> None:
        deadline = self._valid_date(self.data_limite_var.get().strip())
        if self.data_limite_var.get().strip() and deadline is None: return
        reminder_time = self._valid_time(self.hora_limite_var.get().strip())
        if self.hora_limite_var.get().strip() and reminder_time is None: return
        try:
            if self.tarefa_em_edicao_id is None:
                adicionar_tarefa(self.titulo_var.get(), self.descricao_text.get("1.0", tk.END), self.categoria_var.get(), self.prioridade_var.get(), deadline, hora_limite=reminder_time, projeto_id=self.project_ids.get(self.projeto_var.get())); message = "Tarefa criada."
            else:
                atualizar_tarefa(self.tarefa_em_edicao_id, self.titulo_var.get(), self.descricao_text.get("1.0", tk.END), self.categoria_var.get(), self.prioridade_var.get(), deadline, hora_limite=reminder_time, projeto_id=self.project_ids.get(self.projeto_var.get())); message = "Tarefa atualizada."
        except ValueError as error:
            messagebox.showerror("Dados da tarefa", str(error), parent=self.winfo_toplevel()); return
        self._clear(); self.refresh(); self.on_change(); self.set_status(message)

    def _load_selected(self) -> None:
        selected = self._selected(show_error=False)
        if selected is None: return
        task = buscar_tarefa_por_id(selected[0])
        if task is None: return
        self.tarefa_em_edicao_id = selected[0]; self.titulo_var.set(task["titulo"]); self.categoria_var.set(task["categoria"]); self.projeto_var.set(task["projeto"] or "Sem projeto"); self.prioridade_var.set(task["prioridade"]); self.data_limite_var.set(task["data_limite"] or ""); self.hora_limite_var.set(task["hora_limite"] or "")
        self.descricao_text.delete("1.0", tk.END); self.descricao_text.insert("1.0", task["descricao"] or ""); self.set_status(f"Editando tarefa #{selected[0]}.")

    def _clear(self) -> None:
        self.tarefa_em_edicao_id = None; self.titulo_var.set(""); self.categoria_var.set(self.categoria_combo.cget("values")[0]); self.projeto_var.set("Sem projeto"); self.prioridade_var.set("Media"); self.data_limite_var.set(""); self.hora_limite_var.set("")
        self.descricao_text.delete("1.0", tk.END); self.tree.selection_remove(self.tree.selection())

    def _selected(self, *, show_error: bool = True) -> tuple[int, str] | None:
        selected = self.tree.selection()
        if not selected:
            if show_error: messagebox.showinfo("Selecione uma tarefa", "Escolha uma tarefa na lista primeiro.", parent=self.winfo_toplevel())
            return None
        values = self.tree.item(selected[0], "values"); return int(values[0]), str(values[5])

    def _toggle_status(self) -> None:
        selected = self._selected()
        if selected is None: return
        task_id, status = selected; new_status = "Pendente" if status == "Concluida" else "Concluida"; atualizar_status(task_id, new_status)
        self.refresh(); self.on_change(); self.set_status(f"Tarefa marcada como {new_status.lower()}.")

    def _delete(self) -> None:
        selected = self._selected()
        if selected is None: return
        if not messagebox.askyesno("Excluir tarefa", "Excluir a tarefa selecionada? Esta ação não pode ser desfeita.", parent=self.winfo_toplevel()): return
        excluir_tarefa(selected[0]); self._clear(); self.refresh(); self.on_change(); self.set_status("Tarefa excluída.")

    def _valid_date(self, value: str, *, show_error: bool = True) -> str | None:
        if not value: return ""
        try: datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            if show_error: messagebox.showerror("Data inválida", "Use o formato AAAA-MM-DD.", parent=self.winfo_toplevel())
            return None
        return value

    def _valid_time(self, value: str, *, show_error: bool = True) -> str | None:
        if not value: return ""
        try: return datetime.strptime(value, "%H:%M").strftime("%H:%M")
        except ValueError:
            if show_error: messagebox.showerror("Hora inválida", "Use o formato HH:MM, por exemplo 09:30.", parent=self.winfo_toplevel())
            return None
