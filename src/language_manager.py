import json
from pathlib import Path


IDIOMA_ATUAL = "pt"
IDIOMAS_DIR = Path(__file__).resolve().parents[1] / "assets" / "idiomas"

TEXTOS_PADRAO = {
    "pt": {
        "titulo": "Gerenciador de Tarefas",
        "nova_tarefa": "Nova tarefa",
        "dashboard": "Dashboard",
        "tarefas": "Tarefas",
        "calendario": "Calendario",
        "metricas": "Metricas",
    },
    "en": {
        "titulo": "Task Manager",
        "nova_tarefa": "New task",
        "dashboard": "Dashboard",
        "tarefas": "Tasks",
        "calendario": "Calendar",
        "metricas": "Metrics",
    },
    "es": {
        "titulo": "Gestor de Tareas",
        "nova_tarefa": "Nueva tarea",
        "dashboard": "Panel",
        "tarefas": "Tareas",
        "calendario": "Calendario",
        "metricas": "Metricas",
    },
}

# As telas usam estas mensagens como texto-base em português. Centralizar a
# conversão aqui permite reconstruir a interface em outro idioma sem manter
# estado de widgets espalhado pelos módulos.
TEXTOS_INTERFACE = {
    "en": {
        "Visão geral": "Overview", "Tarefas": "Tasks", "Agenda": "Agenda", "Projetos": "Projects",
        "Categorias": "Categories", "Relatórios": "Reports", "Configurações": "Settings",
        "ESPAÇO DE TRABALHO": "WORKSPACE", "GESTÃO PESSOAL": "PERSONAL MANAGEMENT",
        "Sprint 1  •  Interface": "Sprint 1  •  Interface", "Pesquisar tarefas…": "Search tasks…",
        "+ Nova tarefa": "+ New task", "CENTRO DE CONTROLE": "CONTROL CENTER",
        "Seu trabalho, com mais clareza.": "Your work, with more clarity.", "TOTAL": "TOTAL",
        "EM ABERTO": "OPEN", "CONCLUÍDAS": "COMPLETED", "EM ATRASO": "OVERDUE",
        "Tarefas criadas": "Tasks created", "Demandam atenção": "Need attention", "Trabalho finalizado": "Completed work", "Prazos vencidos": "Missed deadlines",
        "Ritmo por categoria": "Rhythm by category", "Volume atual": "Current volume", "Pulso de conclusão": "Completion pulse",
        "Taxa de conclusão": "Completion rate", "PRÓXIMAS ENTREGAS": "UPCOMING DEADLINES", "+  Criar uma tarefa": "+  Create a task",
        "Ainda não há tarefas para distribuir.": "There are no tasks to distribute yet.", "Sem entregas pendentes.\nQue tal registrar a próxima?": "No pending deadlines.\nReady to add the next one?",
        "Planeje o próximo movimento.": "Plan your next move.", "Adicionar ou editar tarefa": "Add or edit task", "Título": "Title", "Categoria": "Category", "Prioridade": "Priority", "Prazo (AAAA-MM-DD)": "Due date (YYYY-MM-DD)", "Hora (HH:MM)": "Time (HH:MM)", "Descrição": "Description", "Salvar": "Save", "Limpar": "Clear",
        "Refinar lista": "Refine list", "Busca": "Search", "Status": "Status", "De": "From", "Até": "To", "Aplicar": "Apply", "Lista de tarefas": "Task list", "Concluir / reabrir": "Complete / reopen", "Excluir": "Delete",
        "Tempo também é uma prioridade.": "Time is a priority too.", "Hoje": "Today", "Prazos das tarefas cadastradas": "Due dates from your tasks",
        "Leve seus dados para a decisão.": "Take your data into decisions.", "Uma base leve para abrir em qualquer planilha.": "A lightweight file for any spreadsheet.", "Tarefas e indicadores em abas prontas para análise.": "Tasks and metrics on analysis-ready sheets.", "Exportar CSV": "Export CSV", "Exportar Excel": "Export Excel", "Importar dados": "Import data", "Power BI": "Power BI", "Tabela de dados": "Data table",
        "PDF entra no Sprint 6": "PDF arrives in Sprint 6", "Faça o espaço trabalhar com você.": "Make the workspace work for you.", "Aparência": "Appearance", "Tema claro": "Light theme", "Tema escuro": "Dark theme", "Idioma": "Language", "Atualizar idioma": "Update language",
        "Lembretes": "Reminders", "Dados": "Data", "IMPORTAÇÃO E EXPORTAÇÃO": "IMPORT AND EXPORT",
    },
    "es": {
        "Visão geral": "Resumen", "Tarefas": "Tareas", "Agenda": "Agenda", "Projetos": "Proyectos",
        "Categorias": "Categorías", "Relatórios": "Informes", "Configurações": "Configuración",
        "ESPAÇO DE TRABALHO": "ESPACIO DE TRABAJO", "GESTÃO PESSOAL": "GESTIÓN PERSONAL",
        "Pesquisar tarefas…": "Buscar tareas…", "+ Nova tarefa": "+ Nueva tarea", "CENTRO DE CONTROLE": "CENTRO DE CONTROL",
        "Seu trabalho, com mais clareza.": "Tu trabajo, con más claridad.", "EM ABERTO": "ABIERTAS", "CONCLUÍDAS": "COMPLETADAS", "EM ATRASO": "ATRASADAS",
        "Tarefas criadas": "Tareas creadas", "Demandam atenção": "Necesitan atención", "Trabalho finalizado": "Trabajo terminado", "Prazos vencidos": "Plazos vencidos",
        "Ritmo por categoria": "Ritmo por categoría", "Volume atual": "Volumen actual", "Pulso de conclusão": "Pulso de finalización", "Taxa de conclusão": "Tasa de finalización", "PRÓXIMAS ENTREGAS": "PRÓXIMAS ENTREGAS", "+  Criar uma tarefa": "+  Crear tarea",
        "Planeje o próximo movimento.": "Planifica el próximo movimiento.", "Adicionar ou editar tarefa": "Añadir o editar tarea", "Título": "Título", "Categoria": "Categoría", "Prioridade": "Prioridad", "Prazo (AAAA-MM-DD)": "Fecha límite (AAAA-MM-DD)", "Hora (HH:MM)": "Hora (HH:MM)", "Descrição": "Descripción", "Salvar": "Guardar", "Limpar": "Limpiar",
        "Refinar lista": "Filtrar lista", "Busca": "Buscar", "De": "Desde", "Até": "Hasta", "Aplicar": "Aplicar", "Lista de tarefas": "Lista de tareas", "Concluir / reabrir": "Completar / reabrir", "Excluir": "Eliminar",
        "Tempo também é uma prioridade.": "El tiempo también es una prioridad.", "Hoje": "Hoy", "Prazos das tarefas cadastradas": "Fechas límite de las tareas",
        "Leve seus dados para a decisão.": "Lleva tus datos a la decisión.", "Exportar CSV": "Exportar CSV", "Exportar Excel": "Exportar Excel", "Importar dados": "Importar datos", "Tabela de dados": "Tabla de datos",
        "Faça o espaço trabalhar com você.": "Haz que el espacio trabaje contigo.", "Aparência": "Apariencia", "Tema claro": "Tema claro", "Tema escuro": "Tema oscuro", "Idioma": "Idioma", "Atualizar idioma": "Actualizar idioma",
        "Lembretes": "Recordatorios", "Dados": "Datos", "IMPORTAÇÃO E EXPORTAÇÃO": "IMPORTACIÓN Y EXPORTACIÓN",
    },
}


def definir_idioma(idioma: str) -> None:
    global IDIOMA_ATUAL
    if idioma not in TEXTOS_PADRAO:
        raise ValueError(f"Idioma nao suportado: {idioma}")
    IDIOMA_ATUAL = idioma


def idioma_atual() -> str:
    return IDIOMA_ATUAL


def carregar_texto(chave: str) -> str:
    textos = _carregar_arquivo_idioma(IDIOMA_ATUAL)
    return textos.get(chave, TEXTOS_PADRAO[IDIOMA_ATUAL].get(chave, chave))


def traduzir_interface(texto: str) -> str:
    """Traduz texto visível usado pelas telas, preservando valores dinâmicos."""
    return TEXTOS_INTERFACE.get(IDIOMA_ATUAL, {}).get(texto, texto)


def traduzir_widgets(widget: object) -> None:
    """Atualiza widgets Tk que expõem a opção ``text`` e todos os descendentes."""
    try:
        texto = widget.cget("text")  # type: ignore[attr-defined]
        if isinstance(texto, str):
            widget.configure(text=traduzir_interface(texto))  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        for filho in widget.winfo_children():  # type: ignore[attr-defined]
            traduzir_widgets(filho)
    except Exception:
        pass


def _carregar_arquivo_idioma(idioma: str) -> dict[str, str]:
    caminho = IDIOMAS_DIR / f"{idioma}.json"
    if not caminho.exists() or caminho.stat().st_size == 0:
        return TEXTOS_PADRAO[idioma]

    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return {**TEXTOS_PADRAO[idioma], **dados}
