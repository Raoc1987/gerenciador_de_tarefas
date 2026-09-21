import calendar as calendar_module
import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime

from database import buscar_tarefas
from ui.theme import Palette, botao


class CalendarView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, set_status: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.set_status = cores, set_status
        today = date.today(); self.year, self.month = today.year, today.month
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self, bg=self.cores.background); header.pack(fill=tk.X, pady=(4, 18))
        tk.Label(header, text="AGENDA", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(header, text="Tempo também é uma prioridade.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(side=tk.LEFT, pady=(3, 0))
        botao(header, "Hoje", self._today, self.cores, compact=True).pack(side=tk.RIGHT, pady=(6, 0))
        card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); card.pack(fill=tk.BOTH, expand=True)
        controls = tk.Frame(card, bg=self.cores.surface); controls.pack(fill=tk.X, padx=18, pady=15)
        botao(controls, "‹", self._previous, self.cores, compact=True).pack(side=tk.LEFT)
        self.title_label = tk.Label(controls, bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 13, "bold")); self.title_label.pack(side=tk.LEFT, padx=14)
        botao(controls, "›", self._next, self.cores, compact=True).pack(side=tk.LEFT)
        tk.Label(controls, text="Prazos das tarefas cadastradas", bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 9)).pack(side=tk.RIGHT, pady=6)
        tk.Frame(card, bg=self.cores.border, height=1).pack(fill=tk.X, padx=18)
        self.grid_frame = tk.Frame(card, bg=self.cores.surface); self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(13, 18))

    def refresh(self) -> None:
        self.title_label.configure(text=f"{calendar_module.month_name[self.month].capitalize()} {self.year}")
        for child in self.grid_frame.winfo_children(): child.destroy()
        tasks_by_day: dict[int, list[dict[str, object]]] = {}
        for row in buscar_tarefas():
            task = dict(row); deadline = task["data_limite"]
            if not deadline: continue
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            if deadline_date.year == self.year and deadline_date.month == self.month: tasks_by_day.setdefault(deadline_date.day, []).append(task)
        for column, day_name in enumerate(("SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM")):
            tk.Label(self.grid_frame, text=day_name, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 8, "bold"), anchor="w").grid(row=0, column=column, sticky="ew", padx=4, pady=(0, 7)); self.grid_frame.columnconfigure(column, weight=1, uniform="calendar")
        today = date.today()
        for row_index, week in enumerate(calendar_module.monthcalendar(self.year, self.month), start=1):
            self.grid_frame.rowconfigure(row_index, weight=1)
            for column, day in enumerate(week):
                cell_bg = self.cores.surface_alt if day else self.cores.surface
                cell = tk.Frame(self.grid_frame, bg=cell_bg, highlightbackground=self.cores.border if day else self.cores.surface, highlightthickness=1 if day else 0); cell.grid(row=row_index, column=column, sticky="nsew", padx=3, pady=3)
                if not day: continue
                is_today = (self.year, self.month, day) == (today.year, today.month, today.day)
                tk.Label(cell, text=str(day), bg=cell_bg, fg=self.cores.accent if is_today else self.cores.text, font=("Segoe UI", 10, "bold"), anchor="w").pack(anchor="w", padx=8, pady=(7, 2))
                for task in tasks_by_day.get(day, [])[:2]:
                    color = self.cores.success if task["status"] == "Concluida" else self.cores.accent
                    horario = f"{task['hora_limite']} " if task.get("hora_limite") else ""
                    tk.Label(cell, text=f"• {horario}{task['titulo'][:16]}", bg=cell_bg, fg=color, font=("Segoe UI", 8), anchor="w").pack(fill=tk.X, padx=7, pady=1)
                more = len(tasks_by_day.get(day, [])) - 2
                if more > 0: tk.Label(cell, text=f"+{more} tarefa(s)", bg=cell_bg, fg=self.cores.muted, font=("Segoe UI", 7)).pack(anchor="w", padx=8, pady=1)

    def _previous(self) -> None:
        self.year, self.month = (self.year - 1, 12) if self.month == 1 else (self.year, self.month - 1); self.refresh()
    def _next(self) -> None:
        self.year, self.month = (self.year + 1, 1) if self.month == 12 else (self.year, self.month + 1); self.refresh()
    def _today(self) -> None:
        today = date.today(); self.year, self.month = today.year, today.month; self.refresh()
