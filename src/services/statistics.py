from datetime import date

from database import buscar_tarefas, calcular_metricas, produtividade_semanal, tarefas_por_categoria


def resumo_dashboard() -> dict[str, object]:
    """Fornece todos os dados do dashboard em um ponto de extensão único."""
    tarefas = [dict(tarefa) for tarefa in buscar_tarefas()]
    proximas = [tarefa for tarefa in tarefas if tarefa["status"] == "Pendente" and tarefa["data_limite"]][:5]
    return {"metricas": calcular_metricas(), "categorias": tarefas_por_categoria(), "produtividade": produtividade_semanal(), "proximas": proximas, "hoje": date.today()}
