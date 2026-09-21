import tkinter as tk
from collections.abc import Callable
from datetime import date

from services.statistics import resumo_dashboard
from ui.theme import Palette, botao


class DashboardView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, on_open_tasks: Callable[[], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_open_tasks = cores, on_open_tasks
        self.metric_cards: dict[str, tuple[tk.Frame, tk.Label]] = {}
        self.last_card_columns = 0
        self._build()
        self.bind("<Configure>", self._on_resize)

    def _build(self) -> None:
        greeting = tk.Frame(self, bg=self.cores.background)
        greeting.pack(fill=tk.X, pady=(4, 18))
        tk.Label(greeting, text="CENTRO DE CONTROLE", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(greeting, text="Seu trabalho, com mais clareza.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 23, "bold")).pack(side=tk.LEFT, anchor="w", pady=(4, 0))
        tk.Label(greeting, text=date.today().strftime("%d.%m.%Y"), bg=self.cores.background, fg=self.cores.muted, font=("Segoe UI", 10)).pack(side=tk.RIGHT, pady=(10, 0))
        self.metrics_frame = tk.Frame(self, bg=self.cores.background)
        self.metrics_frame.pack(fill=tk.X, pady=(0, 18))
        for key, label, caption, icon, color in (("total", "TOTAL", "Tarefas criadas", "▦", self.cores.accent), ("pendentes", "EM ABERTO", "Demandam atenção", "◌", self.cores.warning), ("concluidas", "CONCLUÍDAS", "Trabalho finalizado", "✓", self.cores.success), ("atrasadas", "EM ATRASO", "Prazos vencidos", "!", self.cores.danger)):
            card = tk.Frame(self.metrics_frame, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1)
            tk.Label(card, text=icon, bg=self.cores.accent_soft if key == "total" else self.cores.surface_alt, fg=color, font=("Segoe UI Symbol", 13, "bold"), width=3, height=1).pack(anchor="w", padx=15, pady=(14, 7))
            value = tk.Label(card, text="0", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 22, "bold"))
            value.pack(anchor="w", padx=15)
            tk.Label(card, text=label, bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=15, pady=(2, 0))
            tk.Label(card, text=caption, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8)).pack(anchor="w", padx=15, pady=(2, 14))
            self.metric_cards[key] = (card, value)
        content = tk.Frame(self, bg=self.cores.background)
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=6); content.columnconfigure(1, weight=4); content.rowconfigure(0, weight=1)
        left = tk.Frame(content, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        right = tk.Frame(content, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        header = tk.Frame(left, bg=self.cores.surface); header.pack(fill=tk.X, padx=18, pady=(17, 4))
        tk.Label(header, text="Ritmo por categoria", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Volume atual", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8)).pack(side=tk.RIGHT)
        self.category_canvas = tk.Canvas(left, bg=self.cores.surface, highlightthickness=0, height=245)
        self.category_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 12))
        self.category_canvas.bind("<Configure>", lambda _: self.refresh())
        tk.Label(right, text="Pulso de conclusão", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(17, 0))
        self.progress_canvas = tk.Canvas(right, bg=self.cores.surface, highlightthickness=0, height=122)
        self.progress_canvas.pack(fill=tk.X, padx=10, pady=(4, 4))
        tk.Frame(right, bg=self.cores.border, height=1).pack(fill=tk.X, padx=18, pady=(4, 12))
        tk.Label(right, text="PRÓXIMAS ENTREGAS", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18)
        self.upcoming_list = tk.Frame(right, bg=self.cores.surface)
        self.upcoming_list.pack(fill=tk.BOTH, expand=True, padx=18, pady=(7, 8))
        botao(right, "+  Criar uma tarefa", self.on_open_tasks, self.cores, primary=True).pack(anchor="w", padx=18, pady=(0, 16))

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        columns = 4 if event.width >= 1050 else 2
        if columns != self.last_card_columns: self._layout_cards(columns)

    def _layout_cards(self, columns: int) -> None:
        self.last_card_columns = columns
        for card, _ in self.metric_cards.values(): card.grid_forget()
        for index, (card, _) in enumerate(self.metric_cards.values()):
            card.grid(row=index // columns, column=index % columns, sticky="nsew", padx=(0 if index % columns == 0 else 5, 0 if index % columns == columns - 1 else 5), pady=(0, 9 if index < columns else 0))
        for column in range(4): self.metrics_frame.columnconfigure(column, weight=1 if column < columns else 0)

    def refresh(self) -> None:
        dados = resumo_dashboard(); metricas = dados["metricas"]
        for key, (_, value) in self.metric_cards.items(): value.configure(text=str(metricas[key]))
        self._draw_categories(dados["categorias"]); self._draw_progress(float(metricas["taxa_conclusao"])); self._render_upcoming(dados["proximas"])
        if not self.last_card_columns: self._layout_cards(4 if self.winfo_width() >= 1050 else 2)

    def _draw_categories(self, categories: object) -> None:
        canvas = self.category_canvas; canvas.delete("all"); data = list(categories)[:5]; width = max(canvas.winfo_width(), 360)
        if not data:
            canvas.create_text(18, 45, anchor="w", text="Ainda não há tarefas para distribuir.", fill=self.cores.muted, font=("Segoe UI", 10)); return
        maximum = max(total for _, total in data)
        for index, (category, total) in enumerate(data):
            y = 32 + index * 41
            canvas.create_text(18, y, anchor="w", text=str(category), fill=self.cores.text, font=("Segoe UI", 9, "bold")); canvas.create_text(width - 18, y, anchor="e", text=str(total), fill=self.cores.muted, font=("Segoe UI", 9, "bold"))
            canvas.create_rectangle(18, y + 12, width - 18, y + 19, fill=self.cores.chart_grid, outline="")
            canvas.create_rectangle(18, y + 12, 18 + int((width - 36) * (total / maximum)), y + 19, fill=self.cores.accent, outline="")

    def _draw_progress(self, percentage: float) -> None:
        canvas = self.progress_canvas; canvas.delete("all"); size, x, y = 90, 20, 12
        canvas.create_oval(x, y, x + size, y + size, outline=self.cores.chart_grid, width=10)
        canvas.create_arc(x, y, x + size, y + size, start=90, extent=-max(1, min(360, int(percentage * 3.6))), style=tk.ARC, outline=self.cores.accent, width=10)
        canvas.create_text(x + size / 2, y + size / 2, text=f"{percentage:.0f}%", fill=self.cores.text, font=("Segoe UI", 16, "bold"))
        canvas.create_text(132, 38, anchor="w", text="Taxa de conclusão", fill=self.cores.text, font=("Segoe UI", 10, "bold"))
        canvas.create_text(132, 59, anchor="w", text="Acompanhe o que já saiu\ndo papel nesta base.", fill=self.cores.muted, font=("Segoe UI", 8), justify=tk.LEFT)

    def _render_upcoming(self, tasks: object) -> None:
        for child in self.upcoming_list.winfo_children(): child.destroy()
        items = list(tasks)
        for task in items[:4]:
            row = tk.Frame(self.upcoming_list, bg=self.cores.surface); row.pack(fill=tk.X, pady=3)
            tk.Label(row, text="•", bg=self.cores.surface, fg=self.cores.accent, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
            tk.Label(row, text=task["titulo"], bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 9), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(row, text=task["data_limite"] or "sem prazo", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8)).pack(side=tk.RIGHT)
        if not items: tk.Label(self.upcoming_list, text="Sem entregas pendentes.\nQue tal registrar a próxima?", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 9), justify=tk.LEFT).pack(anchor="w", pady=5)
