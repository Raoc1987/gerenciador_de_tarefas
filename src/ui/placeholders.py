import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ui.theme import Palette, botao


class ComingSoonView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, eyebrow: str, title: str, description: str, sprint: str) -> None:
        super().__init__(master, bg=cores.background)
        tk.Label(self, text=eyebrow, bg=cores.background, fg=cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text=title, bg=cores.background, fg=cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 18))
        card = tk.Frame(self, bg=cores.surface, highlightbackground=cores.border, highlightthickness=1); card.pack(fill=tk.X)
        tk.Label(card, text=sprint, bg=cores.accent_soft, fg=cores.accent_dark, font=("Segoe UI", 9, "bold"), padx=9, pady=5).pack(anchor="w", padx=18, pady=(18, 12))
        tk.Label(card, text=description, bg=cores.surface, fg=cores.muted, wraplength=740, justify=tk.LEFT, font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 18))


class SettingsView(tk.Frame):
    def __init__(self, master: tk.Misc, cores: Palette, current_theme: str, current_language: str, on_theme: Callable[[str], None], on_language: Callable[[str], None]) -> None:
        super().__init__(master, bg=cores.background)
        self.cores, self.on_theme, self.on_language = cores, on_theme, on_language
        self.theme_var = tk.StringVar(value=current_theme); self.language_var = tk.StringVar(value=current_language)
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="CONFIGURAÇÕES", bg=self.cores.background, fg=self.cores.accent, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(self, text="Faça o espaço trabalhar com você.", bg=self.cores.background, fg=self.cores.text, font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(3, 18))
        card = tk.Frame(self, bg=self.cores.surface, highlightbackground=self.cores.border, highlightthickness=1); card.pack(fill=tk.X)
        tk.Label(card, text="Aparência", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 6))
        tk.Radiobutton(card, text="Tema claro", variable=self.theme_var, value="light", command=self._apply_theme, bg=self.cores.surface, fg=self.cores.text, activebackground=self.cores.surface, selectcolor=self.cores.surface_alt, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", padx=18, pady=3)
        tk.Radiobutton(card, text="Tema escuro", variable=self.theme_var, value="dark", command=self._apply_theme, bg=self.cores.surface, fg=self.cores.text, activebackground=self.cores.surface, selectcolor=self.cores.surface_alt, font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", padx=18, pady=(3, 16))
        tk.Frame(card, bg=self.cores.border, height=1).grid(row=3, column=0, sticky="ew")
        tk.Label(card, text="Idioma", bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")).grid(row=4, column=0, sticky="w", padx=18, pady=(16, 4))
        ttk.Combobox(card, textvariable=self.language_var, values=("pt", "en", "es"), state="readonly", width=12).grid(row=5, column=0, sticky="w", padx=18, pady=(0, 5))
        botao(card, "Atualizar idioma", self._apply_language, self.cores, compact=True).grid(row=6, column=0, sticky="w", padx=18, pady=(0, 18))

    def _apply_theme(self) -> None:
        self.on_theme(self.theme_var.get())
    def _apply_language(self) -> None:
        self.on_language(self.language_var.get())
