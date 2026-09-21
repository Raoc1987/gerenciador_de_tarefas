import calendar
from datetime import date, datetime
from tkinter import ttk


def montar_calendario(frame: ttk.Frame, tarefas: list[dict[str, object]]) -> None:
    for widget in frame.winfo_children():
        widget.destroy()

    hoje = date.today()
    titulo = ttk.Label(
        frame,
        text=f"{calendar.month_name[hoje.month]} {hoje.year}",
        font=("Segoe UI", 12, "bold"),
    )
    titulo.grid(row=0, column=0, columnspan=7, pady=(0, 8), sticky="w")

    for coluna, dia in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]):
        ttk.Label(frame, text=dia, font=("Segoe UI", 9, "bold")).grid(
            row=1, column=coluna, padx=4, pady=4, sticky="nsew"
        )

    tarefas_por_dia = _agrupar_por_dia(tarefas, hoje.month, hoje.year)
    for linha, semana in enumerate(calendar.monthcalendar(hoje.year, hoje.month), start=2):
        for coluna, numero_dia in enumerate(semana):
            texto = ""
            if numero_dia:
                total = len(tarefas_por_dia.get(numero_dia, []))
                texto = str(numero_dia) if total == 0 else f"{numero_dia}\n{total} tarefa(s)"
            celula = ttk.Label(frame, text=texto, relief="ridge", padding=8, anchor="n")
            celula.grid(row=linha, column=coluna, padx=2, pady=2, sticky="nsew")

    for coluna in range(7):
        frame.columnconfigure(coluna, weight=1)


def _agrupar_por_dia(
    tarefas: list[dict[str, object]],
    mes: int,
    ano: int,
) -> dict[int, list[dict[str, object]]]:
    agrupadas: dict[int, list[dict[str, object]]] = {}
    for tarefa in tarefas:
        data_limite = tarefa.get("data_limite")
        if not data_limite:
            continue
        data = datetime.strptime(str(data_limite), "%Y-%m-%d").date()
        if data.month == mes and data.year == ano:
            agrupadas.setdefault(data.day, []).append(tarefa)
    return agrupadas
