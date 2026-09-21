from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    name: str
    background: str
    surface: str
    surface_alt: str
    sidebar: str
    sidebar_hover: str
    text: str
    muted: str
    border: str
    accent: str
    accent_dark: str
    accent_soft: str
    success: str
    warning: str
    danger: str
    chart_grid: str
    selection: str


# Direção SAV-inspired: azul técnico profundo, azul elétrico para ação e
# superfícies claras que mantêm tabelas densas e legíveis no uso diário.
LIGHT = Palette("light", "#F4F7FC", "#FFFFFF", "#EAF0F8", "#081E44", "#10336D", "#13203A", "#64748B", "#D7E2F0", "#176BFF", "#0A4ECC", "#E2ECFF", "#059669", "#E58A16", "#DD4558", "#E7EDF6", "#DFEAFF")
DARK = Palette("dark", "#071326", "#0E1C33", "#152845", "#040E20", "#102C5B", "#EAF1FF", "#9DB0CD", "#243C62", "#5C93FF", "#2F72E8", "#172F5C", "#45C68D", "#F6B75A", "#FF7F93", "#1C3152", "#153565")


def obter_paleta(nome: str) -> Palette:
    return DARK if nome == "dark" else LIGHT


def aplicar_tema(root: tk.Tk, cores: Palette) -> None:
    """Configura os widgets ttk e a paleta base usada pelas páginas."""
    estilo = ttk.Style(root)
    estilo.theme_use("clam")
    root.configure(background=cores.background)
    estilo.configure(".", font=("Segoe UI", 10), background=cores.background, foreground=cores.text)
    estilo.configure("TFrame", background=cores.background)
    estilo.configure("TLabel", background=cores.background, foreground=cores.text)
    estilo.configure("TEntry", fieldbackground=cores.surface, foreground=cores.text, bordercolor=cores.border)
    estilo.configure("TCombobox", fieldbackground=cores.surface, background=cores.surface, foreground=cores.text)
    estilo.map("TCombobox", fieldbackground=[("readonly", cores.surface)], foreground=[("readonly", cores.text)])
    estilo.configure("Treeview", background=cores.surface, fieldbackground=cores.surface, foreground=cores.text, rowheight=34, borderwidth=0)
    estilo.map("Treeview", background=[("selected", cores.selection)], foreground=[("selected", cores.text)])
    estilo.configure("Treeview.Heading", background=cores.surface_alt, foreground=cores.muted, font=("Segoe UI", 9, "bold"), relief="flat")
    estilo.map("Treeview.Heading", background=[("active", cores.surface_alt)])
    estilo.configure("TScrollbar", background=cores.surface_alt, troughcolor=cores.background, bordercolor=cores.background)


def botao(parent: tk.Misc, text: str, command: object, cores: Palette, *, primary: bool = False, compact: bool = False, danger: bool = False) -> tk.Button:
    """Botão consistente com feedback de foco, hover e ação principal clara."""
    if danger:
        background, hover, foreground = cores.danger, "#B93145", "#FFFFFF"
    elif primary:
        background, hover, foreground = cores.accent, cores.accent_dark, "#FFFFFF"
    else:
        background, hover, foreground = cores.surface_alt, cores.border, cores.text
    button = tk.Button(
        parent, text=text, command=command, font=("Segoe UI", 9, "bold"), fg=foreground,
        bg=background, activeforeground=foreground, activebackground=hover, relief=tk.FLAT,
        bd=0, cursor="hand2", padx=10 if compact else 14, pady=6 if compact else 8,
        highlightthickness=1, highlightbackground=background, highlightcolor=cores.accent,
        takefocus=True,
    )
    button.bind("<Enter>", lambda _: button.configure(bg=hover))
    button.bind("<Leave>", lambda _: button.configure(bg=background))
    return button
