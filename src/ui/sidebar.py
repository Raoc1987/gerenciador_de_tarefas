import tkinter as tk
from collections.abc import Callable

from language_manager import traduzir_interface
from ui.theme import Palette

NAV_ITEMS = (
    ("dashboard", "▦", "Visão geral"),
    ("tarefas", "✓", "Tarefas"),
    ("agenda", "▣", "Agenda"),
    ("projetos", "◈", "Projetos"),
    ("categorias", "◇", "Categorias"),
    ("relatorios", "↗", "Relatórios"),
    ("dados", "▤", "Dados"),
    ("configuracoes", "⚙", "Configurações"),
)


class Sidebar(tk.Frame):
    """Navegação fixa. Símbolos Unicode evitam uma dependência de imagem."""
    def __init__(self, master: tk.Misc, cores: Palette, on_navigate: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.sidebar, width=224, highlightthickness=0)
        self.cores, self.on_navigate = cores, on_navigate
        self.buttons: dict[str, tk.Button] = {}
        self.active_id = "dashboard"
        self.pack_propagate(False)
        self._build()

    def _build(self) -> None:
        brand = tk.Frame(self, bg=self.cores.sidebar)
        brand.pack(fill=tk.X, padx=20, pady=(22, 30))
        mark = tk.Canvas(brand, width=35, height=35, bg=self.cores.sidebar, highlightthickness=0)
        mark.pack(side=tk.LEFT, padx=(0, 10))
        mark.create_oval(3, 3, 32, 32, outline=self.cores.accent, width=3)
        mark.create_line(17, 8, 17, 27, fill=self.cores.accent, width=3)
        mark.create_oval(14, 14, 20, 20, fill=self.cores.accent, outline="")
        tk.Label(brand, text="NEXO", bg=self.cores.sidebar, fg="#FFFFFF", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(2, 0))
        tk.Label(brand, text="GESTÃO PESSOAL", bg=self.cores.sidebar, fg="#A7B9D1", font=("Segoe UI", 7, "bold")).pack(anchor="w")
        tk.Label(self, text="ESPAÇO DE TRABALHO", bg=self.cores.sidebar, fg="#93A8C5", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=20, pady=(0, 7))
        for page_id, icon, label in NAV_ITEMS:
            button = tk.Button(self, text=f"{icon}   {traduzir_interface(label)}", anchor="w", command=lambda item=page_id: self.on_navigate(item), font=("Segoe UI", 10, "bold" if page_id == self.active_id else "normal"), fg="#FFFFFF", bg=self.cores.sidebar, activeforeground="#FFFFFF", activebackground=self.cores.sidebar_hover, relief=tk.FLAT, bd=0, padx=20, pady=10, cursor="hand2", highlightthickness=0)
            button.pack(fill=tk.X, padx=10, pady=2)
            self.buttons[page_id] = button
        bottom = tk.Frame(self, bg=self.cores.sidebar)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
        tk.Frame(bottom, bg="#294467", height=1).pack(fill=tk.X, pady=(0, 12))
        tk.Label(bottom, text="Sprint 1  •  Interface", bg=self.cores.sidebar, fg="#A7B9D1", font=("Segoe UI", 8)).pack(anchor="w")
        self.set_active(self.active_id)

    def set_active(self, page_id: str) -> None:
        self.active_id = page_id
        for item_id, button in self.buttons.items():
            selected = item_id == page_id
            button.configure(bg=self.cores.sidebar_hover if selected else self.cores.sidebar, font=("Segoe UI", 10, "bold" if selected else "normal"), fg=self.cores.accent if selected else "#FFFFFF")
