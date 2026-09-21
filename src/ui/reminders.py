import tkinter as tk
from collections.abc import Callable

from ui.theme import Palette, botao


class ReminderDialog(tk.Toplevel):
    """Alerta compacto, inspirado nos lembretes de agenda, sem serviço externo."""
    def __init__(self, parent: tk.Misc, cores: Palette, task: dict[str, object], on_snooze: Callable[[], None], on_dismiss: Callable[[], None], on_open: Callable[[], None]) -> None:
        super().__init__(parent)
        self.cores, self.task = cores, task
        self.title("Lembrete de calendário")
        self.configure(bg=cores.surface)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", on_snooze)
        self._build(on_snooze, on_dismiss, on_open)
        self.after(100, self._place_near_parent)
        self.bell()

    def _build(self, on_snooze: Callable[[], None], on_dismiss: Callable[[], None], on_open: Callable[[], None]) -> None:
        band = tk.Frame(self, bg=self.cores.accent, height=7); band.pack(fill=tk.X)
        body = tk.Frame(self, bg=self.cores.surface); body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)
        tk.Label(body, text="LEMBRETE", bg=self.cores.surface, fg=self.cores.accent_dark, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(body, text=str(self.task["titulo"]), bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 15, "bold"), wraplength=360, justify=tk.LEFT).pack(anchor="w", pady=(4, 8))
        when = f"{self.task['data_limite']} • {self.task['hora_limite']}" if self.task.get("data_limite") else str(self.task.get("hora_limite") or "")
        tk.Label(body, text=when, bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 10)).pack(anchor="w")
        description = str(self.task.get("descricao") or "")
        if description:
            tk.Label(body, text=description[:180], bg=self.cores.surface, fg=self.cores.muted, font=("Segoe UI", 9), wraplength=360, justify=tk.LEFT).pack(anchor="w", pady=(8, 14))
        actions = tk.Frame(body, bg=self.cores.surface); actions.pack(anchor="e", pady=(18, 0))
        botao(actions, "Adiar 10 min", on_snooze, self.cores, compact=True).pack(side=tk.LEFT)
        botao(actions, "Dispensar", on_dismiss, self.cores, compact=True).pack(side=tk.LEFT, padx=6)
        botao(actions, "Abrir tarefa", on_open, self.cores, primary=True, compact=True).pack(side=tk.LEFT)

    def _place_near_parent(self) -> None:
        parent = self.master
        x = parent.winfo_rootx() + max(parent.winfo_width() - self.winfo_width() - 38, 0)
        y = parent.winfo_rooty() + 82
        self.geometry(f"+{x}+{y}")
