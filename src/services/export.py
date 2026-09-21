import csv
import json
from datetime import date
from pathlib import Path

from database import DB_PATH, buscar_tarefas, calcular_metricas, produtividade_semanal, tarefas_por_categoria

CAMPOS_TAREFA = ("id", "titulo", "descricao", "categoria", "prioridade", "status", "data_limite", "hora_limite", "criado_em", "concluido_em")


def nome_padrao(extensao: str) -> str:
    return f"tarefas_{date.today().isoformat()}.{extensao}"


def exportar_csv(destino: str | Path, db_path: Path | str = DB_PATH) -> Path:
    caminho = Path(destino)
    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_TAREFA)
        escritor.writeheader()
        escritor.writerows(_linha_exportacao(tarefa) for tarefa in buscar_tarefas(db_path))
    return caminho


def exportar_tsv(destino: str | Path, db_path: Path | str = DB_PATH) -> Path:
    caminho = Path(destino)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_TAREFA, delimiter="\t")
        escritor.writeheader()
        escritor.writerows(_linha_exportacao(tarefa) for tarefa in buscar_tarefas(db_path))
    return caminho


def exportar_json(destino: str | Path, db_path: Path | str = DB_PATH) -> Path:
    caminho = Path(destino)
    conteudo = {
        "gerado_em": date.today().isoformat(),
        "metricas": calcular_metricas(db_path),
        "tarefas": [dict(tarefa) for tarefa in buscar_tarefas(db_path)],
    }
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def exportar_sql(destino: str | Path, db_path: Path | str = DB_PATH) -> Path:
    """Gera INSERTs portáveis para migrar os dados a outro banco."""
    caminho = Path(destino)
    linhas = ["-- Exportação gerada pelo Nexo\n"]
    for tarefa in buscar_tarefas(db_path):
        valores = []
        for campo in CAMPOS_TAREFA:
            valor = tarefa[campo]
            valores.append("NULL" if valor is None else "'" + str(valor).replace("'", "''") + "'")
        linhas.append(f"INSERT INTO tarefas ({', '.join(CAMPOS_TAREFA)}) VALUES ({', '.join(valores)});\n")
    caminho.write_text("".join(linhas), encoding="utf-8")
    return caminho


def exportar_power_bi(destino: str | Path, db_path: Path | str = DB_PATH) -> tuple[Path, Path]:
    """Cria duas tabelas CSV prontas para carregamento no Power BI.

    Power BI importa CSV nativamente; um arquivo de métricas separado permite
    relacionar a tabela de tarefas com indicadores de resumo sem dependência de
    APIs proprietárias do formato .pbix.
    """
    tarefas_path = Path(destino)
    metricas_path = tarefas_path.with_name(f"{tarefas_path.stem}_metricas.csv")
    with tarefas_path.open("w", newline="", encoding="utf-8-sig") as arquivo:
        campos = (*CAMPOS_TAREFA, "ano", "mes", "semana", "atrasada")
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for tarefa in buscar_tarefas(db_path):
            row = dict(tarefa)
            prazo = row["data_limite"] or ""
            row.update({"ano": prazo[:4], "mes": prazo[:7], "semana": prazo[:7], "atrasada": int(row["status"] == "Pendente" and bool(prazo) and prazo < date.today().isoformat())})
            escritor.writerow({campo: row.get(campo) for campo in campos})
    with metricas_path.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["indicador", "valor"])
        for chave, valor in calcular_metricas(db_path).items():
            escritor.writerow([chave, valor])
        escritor.writerow([])
        escritor.writerow(["categoria", "total"])
        escritor.writerows(tarefas_por_categoria(db_path))
        escritor.writerow([])
        escritor.writerow(["semana", "concluidas"])
        escritor.writerows(produtividade_semanal(db_path))
    return tarefas_path, metricas_path


def exportar_excel(destino: str | Path, db_path: Path | str = DB_PATH) -> Path:
    """Exporta dados e indicadores; requer openpyxl somente neste fluxo."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    caminho = Path(destino)
    workbook = Workbook()
    planilha = workbook.active
    planilha.title = "Tarefas"
    planilha.append(CAMPOS_TAREFA)
    for celula in planilha[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="172A46")
    for tarefa in buscar_tarefas(db_path):
        planilha.append([tarefa[campo] for campo in CAMPOS_TAREFA])
    for coluna, largura in {"A": 8, "B": 32, "C": 50, "D": 18, "E": 14, "F": 14, "G": 16}.items():
        planilha.column_dimensions[coluna].width = largura
    planilha.freeze_panes = "A2"
    metricas = workbook.create_sheet("Indicadores")
    metricas.append(["Indicador", "Valor"])
    for celula in metricas[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="172A46")
    for chave, valor in calcular_metricas(db_path).items():
        metricas.append([chave.replace("_", " ").title(), valor])
    metricas.column_dimensions["A"].width = 28
    metricas.column_dimensions["B"].width = 16
    categorias = workbook.create_sheet("Categorias")
    categorias.append(["Categoria", "Total de tarefas"])
    for categoria, total in tarefas_por_categoria(db_path):
        categorias.append([categoria, total])
    produtividade = workbook.create_sheet("Produtividade")
    produtividade.append(["Semana", "Tarefas concluídas"])
    for semana, total in produtividade_semanal(db_path):
        produtividade.append([semana, total])
    workbook.save(caminho)
    return caminho


def _linha_exportacao(tarefa: object) -> dict[str, object]:
    return {campo: tarefa[campo] for campo in CAMPOS_TAREFA}  # type: ignore[index]
