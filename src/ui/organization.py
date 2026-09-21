import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import messagebox, ttk

from database import (
    atualizar_projeto,
    criar_categoria,
    criar_projeto,
    excluir_categoria,
    excluir_projeto,
    listar_categorias,
    listar_projetos,
)
from ui.theme import Palette, botao


CORES_CATALOGO = ("#176BFF", "#059669", "#E58A16", "#A855F7", "#DD4558", "#0891B2")


class CategoriesView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, on_change: Callable[[], None], set_status: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_change, self.set_status = cores, on_change, set_status
        self.nome_var = tk.StringVar(); self.cor_var = tk.StringVar(value=CORES_CATALOGO[0])
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="CATEGORIAS", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text="O vocabulário do seu trabalho.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 18))
        form = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); form.pack(fill=tk.X, pady=(0, 12))
        tk.Label(form, text="Criar categoria", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 7))
        tk.Label(form, text="Nome", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=1, column=0, sticky="w", padx=16)
        ttk.Entry(form, textvariable=self.nome_var, width=35).grid(row=2, column=0, sticky="ew", padx=16, pady=(2, 14))
        tk.Label(form, text="Cor", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Combobox(form, textvariable=self.cor_var, values=CORES_CATALOGO, state="readonly", width=12).grid(row=2, column=1, padx=5, pady=(2, 14))
        botao(form, "Adicionar categoria", self._create, self.cores, primary=True).grid(row=2, column=2, padx=12, pady=(2, 14), sticky="w")
        form.columnconfigure(0, weight=1)
        card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); card.pack(fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(card, bg=self.cores.surface); toolbar.pack(fill=tk.X, padx=16, pady=(12, 7))
        tk.Label(toolbar, text="Categorias ativas", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        botao(toolbar, "Excluir categoria", self._delete, self.cores, compact=True, danger=True).pack(side=tk.RIGHT)
        self.tree = ttk.Treeview(card, columns=("id", "nome", "cor", "total"), show="headings", selectmode="browse")
        for column, label, width in (("id", "ID", 60), ("nome", "NOME", 360), ("cor", "COR", 150), ("total", "TAREFAS", 110)):
            self.tree.heading(column, text=label); self.tree.column(column, width=width, anchor=tk.W, stretch=column == "nome")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in listar_categorias():
            self.tree.insert("", tk.END, values=(row["id"], row["nome"], row["cor"], row["total_tarefas"]))

    def _create(self) -> None:
        try: criar_categoria(self.nome_var.get(), self.cor_var.get())
        except ValueError as error:
            messagebox.showerror("Categoria", str(error), parent=self.winfo_toplevel()); return
        self.nome_var.set(""); self.refresh(); self.on_change(); self.set_status("Categoria criada.")

    def _delete(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Categoria", "Selecione uma categoria primeiro.", parent=self.winfo_toplevel()); return
        values = self.tree.item(selected[0], "values")
        if not messagebox.askyesno("Excluir categoria", f"Excluir a categoria '{values[1]}'?", parent=self.winfo_toplevel()): return
        try: excluir_categoria(int(values[0]))
        except ValueError as error:
            messagebox.showwarning("Categoria em uso", str(error), parent=self.winfo_toplevel()); return
        self.refresh(); self.on_change(); self.set_status("Categoria excluída.")


class ProjectsView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, on_change: Callable[[], None], set_status: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_change, self.set_status = cores, on_change, set_status
        self.nome_var = tk.StringVar(); self.data_var = tk.StringVar(); self.status_var = tk.StringVar(value="Ativo"); self.project_id: int | None = None
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="PROJETOS", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text="Do plano ao resultado, em contexto.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 18))
        form = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); form.pack(fill=tk.X, pady=(0, 12))
        tk.Label(form, text="Novo projeto ou edição", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=5, sticky="w", padx=16, pady=(14, 7))
        self._field(form, "Nome", ttk.Entry(form, textvariable=self.nome_var), 1, 0, "ew")
        self._field(form, "Entrega (AAAA-MM-DD)", ttk.Entry(form, textvariable=self.data_var, width=15), 1, 1)
        self._field(form, "Status", ttk.Combobox(form, textvariable=self.status_var, values=("Ativo", "Pausado", "Concluido"), state="readonly", width=12), 1, 2)
        actions = tk.Frame(form, bg=self.cores.surface); actions.grid(row=2, column=3, rowspan=3, sticky="se", padx=(0, 16), pady=(18, 14))
        botao(actions, "Salvar projeto", self._save, self.cores, primary=True, compact=True).pack(side=tk.LEFT)
        botao(actions, "Limpar", self._clear, self.cores, compact=True).pack(side=tk.LEFT, padx=6)
        tk.Label(form, text="Descrição", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=3, column=0, sticky="w", padx=16, pady=(3, 2))
        self.descricao = tk.Text(form, height=3, wrap=tk.WORD, bg=self.cores.surface_alt, fg=self.cores.text, insertbackground=self.cores.text, relief=tk.FLAT, padx=8, pady=7, font=("Segoe UI", 9), highlightthickness=1, highlightbackground=self.cores.border, highlightcolor=self.cores.accent)
        self.descricao.grid(row=4, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 15)); form.columnconfigure(0, weight=1)
        card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); card.pack(fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(card, bg=self.cores.surface); toolbar.pack(fill=tk.X, padx=16, pady=(12, 7))
        tk.Label(toolbar, text="Portfólio de projetos", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        botao(toolbar, "Excluir projeto", self._delete, self.cores, compact=True, danger=True).pack(side=tk.RIGHT)
        self.tree = ttk.Treeview(card, columns=("id", "nome", "status", "tarefas", "concluidas", "entrega"), show="headings", selectmode="browse")
        for column, label, width in (("id", "ID", 55), ("nome", "PROJETO", 300), ("status", "STATUS", 105), ("tarefas", "TAREFAS", 95), ("concluidas", "CONCLUÍDAS", 110), ("entrega", "ENTREGA", 110)):
            self.tree.heading(column, text=label); self.tree.column(column, width=width, anchor=tk.W, stretch=column == "nome")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._load())
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _field(self, parent: tk.Misc, label: str, widget: tk.Widget, row: int, column: int, sticky: str = "w") -> None:
        padx = (16 if column == 0 else 5, 5)
        tk.Label(parent, text=label, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).grid(row=row, column=column, sticky="w", padx=padx, pady=(0, 2))
        widget.grid(row=row + 1, column=column, sticky=sticky, padx=padx, pady=(0, 10))

    def refresh(self) -> None:
        self.rows = {row["id"]: row for row in listar_projetos()}
        self.tree.delete(*self.tree.get_children())
        for row in self.rows.values():
            self.tree.insert("", tk.END, values=(row["id"], row["nome"], row["status"], row["total_tarefas"], row["tarefas_concluidas"], row["data_entrega"] or "—"))

    def _load(self) -> None:
        selected = self.tree.selection()
        if not selected: return
        project = self.rows[int(self.tree.item(selected[0], "values")[0])]
        self.project_id = project["id"]; self.nome_var.set(project["nome"]); self.data_var.set(project["data_entrega"] or ""); self.status_var.set(project["status"])
        self.descricao.delete("1.0", tk.END); self.descricao.insert("1.0", project["descricao"] or "")
        self.set_status(f"Editando projeto #{self.project_id}.")

    def _save(self) -> None:
        data = self._valid_date(self.data_var.get().strip())
        if self.data_var.get().strip() and data is None: return
        try:
            if self.project_id is None:
                criar_projeto(self.nome_var.get(), self.descricao.get("1.0", tk.END), data); message = "Projeto criado."
            else:
                atualizar_projeto(self.project_id, self.nome_var.get(), self.descricao.get("1.0", tk.END), self.status_var.get(), data); message = "Projeto atualizado."
        except ValueError as error:
            messagebox.showerror("Projeto", str(error), parent=self.winfo_toplevel()); return
        self._clear(); self.refresh(); self.on_change(); self.set_status(message)

    def _delete(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Projeto", "Selecione um projeto primeiro.", parent=self.winfo_toplevel()); return
        project_id, name = self.tree.item(selected[0], "values")[:2]
        if not messagebox.askyesno("Excluir projeto", f"Excluir '{name}'? As tarefas ficarão sem projeto.", parent=self.winfo_toplevel()): return
        excluir_projeto(int(project_id)); self._clear(); self.refresh(); self.on_change(); self.set_status("Projeto excluído.")

    def _clear(self) -> None:
        self.project_id = None; self.nome_var.set(""); self.data_var.set(""); self.status_var.set("Ativo"); self.descricao.delete("1.0", tk.END); self.tree.selection_remove(self.tree.selection())

    def _valid_date(self, value: str) -> str | None:
        if not value: return ""
        try: return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            messagebox.showerror("Data inválida", "Use o formato AAAA-MM-DD.", parent=self.winfo_toplevel()); return None
