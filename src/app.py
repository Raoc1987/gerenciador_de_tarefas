import tkinter as tk
from datetime import datetime

from database import adiar_lembrete, criar_tabela, dispensar_lembrete, listar_lembretes_devidos
from language_manager import carregar_texto, definir_idioma, idioma_atual, traduzir_interface, traduzir_widgets
from ui.calendar import CalendarView
from ui.dashboard import DashboardView
from ui.data import DataView
from ui.organization import CategoriesView, ProjectsView
from ui.placeholders import SettingsView
from ui.reports import ReportsView
from ui.sidebar import Sidebar
from ui.reminders import ReminderDialog
from ui.tasks import TasksView
from ui.theme import Palette, aplicar_tema, botao, obter_paleta

PAGE_TITLES = {
    "dashboard": "Visão geral", "tarefas": "Tarefas", "agenda": "Agenda",
    "projetos": "Projetos", "categorias": "Categorias", "relatorios": "Relatórios", "dados": "Dados", "configuracoes": "Configurações",
}


class TaskManagerApp:
    """Shell da aplicação: navegação, tema e coordenação entre páginas."""
    def __init__(self) -> None:
        criar_tabela()
        self.root = tk.Tk()
        self.root.title(carregar_texto("titulo"))
        self.root.geometry("1280x800")
        self.root.minsize(1010, 650)
        self.theme_name = "light"; self.cores: Palette = obter_paleta(self.theme_name); self.current_page = "dashboard"; self.sidebar_visible = True
        self.status_var = tk.StringVar(value="Pronto para organizar seu dia."); self.search_var = tk.StringVar(); self.search_after_id: str | None = None; self.views: dict[str, tk.Frame] = {}; self.reminder_open = False
        self._build_shell()
        self.root.bind("<Control-k>", self._focus_search); self.root.bind("<Configure>", self._responsive_layout); self._update_clock(); self.root.after(2_000, self._check_reminders)

    def run(self) -> None:
        self.root.mainloop()

    def _build_shell(self) -> None:
        aplicar_tema(self.root, self.cores)
        self.shell = tk.Frame(self.root, bg=self.cores.background); self.shell.pack(fill=tk.BOTH, expand=True)
        self.sidebar = Sidebar(self.shell, self.cores, self.show_page); self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.main_frame = tk.Frame(self.shell, bg=self.cores.background); self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_topbar(self.main_frame)
        self.content = tk.Frame(self.main_frame, bg=self.cores.background); self.content.pack(fill=tk.BOTH, expand=True, padx=24, pady=(18, 8)); self.content.rowconfigure(0, weight=1); self.content.columnconfigure(0, weight=1)
        self._build_views()
        footer = tk.Frame(self.main_frame, bg=self.cores.background); footer.pack(fill=tk.X, padx=24, pady=(3, 12))
        tk.Label(footer, textvariable=self.status_var, bg=self.cores.background, fg=self.cores.muted, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.clock_label = tk.Label(footer, bg=self.cores.background, fg=self.cores.muted, font=("Segoe UI", 8)); self.clock_label.pack(side=tk.RIGHT)
        self.show_page(self.current_page)
        traduzir_widgets(self.shell)

    def _build_topbar(self, parent: tk.Misc) -> None:
        topbar = tk.Frame(parent, bg=self.cores.surface, height=64, highlightbackground=self.cores.border, highlightthickness=1); topbar.pack(fill=tk.X); topbar.pack_propagate(False)
        botao(topbar, "☰", self._toggle_sidebar, self.cores, compact=True).pack(side=tk.LEFT, padx=(14, 8), pady=13)
        self.page_label = tk.Label(topbar, text=traduzir_interface(PAGE_TITLES[self.current_page]), bg=self.cores.surface, fg=self.cores.text, font=("Segoe UI", 11, "bold")); self.page_label.pack(side=tk.LEFT)
        self.search_entry = tk.Entry(topbar, textvariable=self.search_var, bg=self.cores.surface_alt, fg=self.cores.muted, insertbackground=self.cores.text, relief=tk.FLAT, highlightthickness=1, highlightbackground=self.cores.border, highlightcolor=self.cores.accent, font=("Segoe UI", 9), width=31)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=42, pady=16); self.search_entry.insert(0, "Pesquisar tarefas…")
        self.search_entry.bind("<FocusIn>", self._clear_search_placeholder); self.search_entry.bind("<FocusOut>", self._restore_search_placeholder); self.search_var.trace_add("write", self._schedule_search)
        botao(topbar, "◐", lambda: self.change_theme("dark" if self.theme_name == "light" else "light"), self.cores, compact=True).pack(side=tk.RIGHT, padx=(0, 8), pady=13)
        botao(topbar, "+ Nova tarefa", lambda: self.show_page("tarefas"), self.cores, primary=True, compact=True).pack(side=tk.RIGHT, padx=(0, 14), pady=13)

    def _build_views(self) -> None:
        dashboard = DashboardView(self.content, self.cores, lambda: self.show_page("tarefas")); tasks = TasksView(self.content, self.cores, self.refresh_data, self.set_status); agenda = CalendarView(self.content, self.cores, self.set_status)
        views: dict[str, tk.Frame] = {
            "dashboard": dashboard, "tarefas": tasks, "agenda": agenda,
            "projetos": ProjectsView(self.content, self.cores, self.refresh_data, self.set_status),
            "categorias": CategoriesView(self.content, self.cores, self.refresh_data, self.set_status),
            "relatorios": ReportsView(self.content, self.cores, self.set_status, self.refresh_data),
            "dados": DataView(self.content, self.cores, lambda: self.show_page("relatorios")),
            "configuracoes": SettingsView(self.content, self.cores, self.theme_name, idioma_atual(), self.change_theme, self.change_language),
        }
        for view in views.values(): view.grid(row=0, column=0, sticky="nsew")
        self.views = views; tasks.refresh(); dashboard.refresh(); agenda.refresh()
        views["projetos"].refresh(); views["categorias"].refresh()

    def show_page(self, page_id: str) -> None:
        if page_id not in self.views: return
        self.current_page = page_id; self.page_label.configure(text=traduzir_interface(PAGE_TITLES[page_id])); self.sidebar.set_active(page_id)
        view = self.views[page_id]; view.tkraise(); refresh = getattr(view, "refresh", None)
        if callable(refresh): refresh()
        self.set_status(f"{PAGE_TITLES[page_id]} aberto.")

    def refresh_data(self) -> None:
        tasks = self.views.get("tarefas")
        if isinstance(tasks, TasksView):
            tasks.refresh_catalogs()
        for name in ("dashboard", "agenda", "dados", "projetos", "categorias"):
            refresh = getattr(self.views[name], "refresh", None)
            if callable(refresh): refresh()

    def change_theme(self, theme_name: str) -> None:
        if theme_name == self.theme_name: return
        self.theme_name = theme_name; self.cores = obter_paleta(theme_name); self.shell.destroy(); self.views = {}; self._build_shell(); self.set_status("Tema atualizado.")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def change_language(self, language: str) -> None:
        definir_idioma(language)
        self.root.title(carregar_texto("titulo"))
        self.shell.destroy(); self.views = {}; self._build_shell()
        self.set_status("Idioma atualizado.")

    def _toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible: self.sidebar.pack(side=tk.LEFT, fill=tk.Y, before=self.main_frame)
        else: self.sidebar.pack_forget()

    def _responsive_layout(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is self.root and event.width < 1080 and self.sidebar_visible:
            self.sidebar_visible = False; self.sidebar.pack_forget()

    def _schedule_search(self, *_: object) -> None:
        if self.search_after_id is not None: self.root.after_cancel(self.search_after_id)
        self.search_after_id = self.root.after(180, self._run_search)

    def _run_search(self) -> None:
        query = self.search_var.get().strip()
        if query != "Pesquisar tarefas…":
            self.show_page("tarefas")
            tasks = self.views["tarefas"]
            if isinstance(tasks, TasksView): tasks.apply_search(query)
        self.search_after_id = None

    def _focus_search(self, _: tk.Event[tk.Misc]) -> str:
        self.search_entry.focus_set(); return "break"
    def _clear_search_placeholder(self, _: tk.Event[tk.Misc]) -> None:
        if self.search_var.get() == "Pesquisar tarefas…": self.search_var.set(""); self.search_entry.configure(fg=self.cores.text)
    def _restore_search_placeholder(self, _: tk.Event[tk.Misc]) -> None:
        if not self.search_var.get().strip(): self.search_var.set("Pesquisar tarefas…"); self.search_entry.configure(fg=self.cores.muted)
    def _update_clock(self) -> None:
        self.clock_label.configure(text=datetime.now().strftime("%d/%m/%Y  •  %H:%M")); self.root.after(1_000, self._update_clock)

    def _check_reminders(self) -> None:
        if not self.reminder_open:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reminders = listar_lembretes_devidos(now)
            if reminders:
                self._show_reminder(dict(reminders[0]))
        self.root.after(30_000, self._check_reminders)

    def _show_reminder(self, task: dict[str, object]) -> None:
        self.reminder_open = True

        def close() -> None:
            if dialog.winfo_exists(): dialog.destroy()
            self.reminder_open = False
            self.root.after(350, self._check_reminders)

        def snooze() -> None:
            from datetime import timedelta
            adiar_lembrete(int(task["id"]), (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"))
            self.set_status("Lembrete adiado por 10 minutos.")
            close()

        def dismiss() -> None:
            dispensar_lembrete(int(task["id"]), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.set_status("Lembrete dispensado.")
            close()

        def open_task() -> None:
            dismiss(); self.show_page("tarefas")
            tasks = self.views["tarefas"]
            if isinstance(tasks, TasksView):
                tasks.focus_task(int(task["id"]))

        dialog = ReminderDialog(self.root, self.cores, task, snooze, dismiss, open_task)
