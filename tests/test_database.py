import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from database import (  # noqa: E402
    adicionar_tarefa,
    adiar_lembrete,
    atualizar_tarefa,
    atualizar_status,
    buscar_tarefa_por_id,
    buscar_tarefas,
    calcular_metricas,
    criar_categoria,
    criar_projeto,
    criar_tabela,
    dispensar_lembrete,
    excluir_categoria,
    excluir_projeto,
    listar_categorias,
    listar_lembretes_devidos,
    listar_projetos,
    produtividade_semanal,
    tarefas_por_categoria,
)
from services.export import exportar_csv, exportar_excel, exportar_json, exportar_power_bi, exportar_sql, exportar_tsv  # noqa: E402
from services.importer import importar_planilha  # noqa: E402


class DatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "tarefas_test.db"
        criar_tabela(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_adiciona_busca_e_conclui_tarefa(self) -> None:
        tarefa_id = adicionar_tarefa(
            "Planejar dashboard",
            categoria="Trabalho",
            prioridade="Alta",
            db_path=self.db_path,
        )

        tarefas = buscar_tarefas(self.db_path)
        self.assertEqual(1, len(tarefas))
        self.assertEqual("Planejar dashboard", tarefas[0]["titulo"])

        atualizar_status(tarefa_id, "Concluida", self.db_path)
        metricas = calcular_metricas(self.db_path)

        self.assertEqual(1, metricas["total"])
        self.assertEqual(1, metricas["concluidas"])
        self.assertEqual(100.0, metricas["taxa_conclusao"])

    def test_metricas_identificam_tarefa_atrasada(self) -> None:
        adicionar_tarefa(
            "Enviar relatorio",
            data_limite="2000-01-01",
            db_path=self.db_path,
        )

        metricas = calcular_metricas(self.db_path)

        self.assertEqual(1, metricas["pendentes"])
        self.assertEqual(1, metricas["atrasadas"])

    def test_agrupa_tarefas_por_categoria(self) -> None:
        adicionar_tarefa("Tarefa A", categoria="Estudo", db_path=self.db_path)
        adicionar_tarefa("Tarefa B", categoria="Estudo", db_path=self.db_path)
        adicionar_tarefa("Tarefa C", categoria="Pessoal", db_path=self.db_path)

        categorias = dict(tarefas_por_categoria(self.db_path))

        self.assertEqual(2, categorias["Estudo"])
        self.assertEqual(1, categorias["Pessoal"])

    def test_atualiza_tarefa_completa(self) -> None:
        tarefa_id = adicionar_tarefa("Rascunho", db_path=self.db_path)

        atualizar_tarefa(
            tarefa_id,
            "Preparar relatorio",
            descricao="Consolidar indicadores",
            categoria="Trabalho",
            prioridade="Alta",
            data_limite="2026-08-15",
            db_path=self.db_path,
        )

        tarefa = buscar_tarefa_por_id(tarefa_id, self.db_path)

        self.assertIsNotNone(tarefa)
        self.assertEqual("Preparar relatorio", tarefa["titulo"])
        self.assertEqual("Trabalho", tarefa["categoria"])
        self.assertEqual("Alta", tarefa["prioridade"])
        self.assertEqual("2026-08-15", tarefa["data_limite"])

    def test_filtra_por_status_categoria_e_periodo(self) -> None:
        tarefa_id = adicionar_tarefa(
            "Estudar metricas",
            categoria="Estudo",
            data_limite="2026-08-10",
            db_path=self.db_path,
        )
        atualizar_status(tarefa_id, "Concluida", self.db_path)
        adicionar_tarefa(
            "Comprar material",
            categoria="Pessoal",
            data_limite="2026-09-01",
            db_path=self.db_path,
        )

        tarefas = buscar_tarefas(
            self.db_path,
            status="Concluida",
            categoria="Estudo",
            data_inicio="2026-08-01",
            data_fim="2026-08-31",
        )

        self.assertEqual(1, len(tarefas))
        self.assertEqual("Estudar metricas", tarefas[0]["titulo"])

    def test_produtividade_semanal_conta_concluidas(self) -> None:
        tarefa_id = adicionar_tarefa("Fechar sprint", db_path=self.db_path)
        atualizar_status(tarefa_id, "Concluida", self.db_path)

        produtividade = produtividade_semanal(self.db_path)

        self.assertEqual(1, sum(total for _, total in produtividade))

    def test_hora_e_lembrete_podem_ser_adiados_ou_dispensados(self) -> None:
        agora = datetime.now()
        tarefa_id = adicionar_tarefa(
            "Participar da reunião",
            data_limite=agora.date().isoformat(),
            hora_limite=(agora - timedelta(minutes=2)).strftime("%H:%M"),
            db_path=self.db_path,
        )
        instante = agora.strftime("%Y-%m-%d %H:%M:%S")

        self.assertEqual([tarefa_id], [row["id"] for row in listar_lembretes_devidos(instante, self.db_path)])
        adiar_lembrete(tarefa_id, (agora + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"), self.db_path)
        self.assertEqual([], listar_lembretes_devidos(instante, self.db_path))
        dispensar_lembrete(tarefa_id, instante, self.db_path)
        self.assertEqual([], listar_lembretes_devidos((agora + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), self.db_path))

    def test_importa_csv_e_exporta_formatos_analiticos(self) -> None:
        origem = Path(self.temp_dir.name) / "importacao.csv"
        with origem.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(["Título", "Categoria", "Prioridade", "Prazo", "Hora", "Status"])
            escritor.writerow(["Analisar dados", "Trabalho", "Alta", "2026-08-31", "09:30", "Concluida"])
            escritor.writerow(["", "Geral", "Media", "", "", ""])

        resultado = importar_planilha(origem, self.db_path)
        self.assertEqual(1, resultado.importadas)
        self.assertEqual(1, resultado.ignoradas)
        tarefa = buscar_tarefas(self.db_path)[0]
        self.assertEqual("09:30", tarefa["hora_limite"])
        self.assertEqual("Concluida", tarefa["status"])

        csv_path = exportar_csv(Path(self.temp_dir.name) / "tarefas.csv", self.db_path)
        tsv_path = exportar_tsv(Path(self.temp_dir.name) / "tarefas.tsv", self.db_path)
        json_path = exportar_json(Path(self.temp_dir.name) / "tarefas.json", self.db_path)
        sql_path = exportar_sql(Path(self.temp_dir.name) / "tarefas.sql", self.db_path)
        powerbi_path, metricas_path = exportar_power_bi(Path(self.temp_dir.name) / "powerbi.csv", self.db_path)

        self.assertIn("hora_limite", csv_path.read_text(encoding="utf-8-sig"))
        self.assertIn("Analisar dados", tsv_path.read_text(encoding="utf-8"))
        self.assertEqual(1, len(json.loads(json_path.read_text(encoding="utf-8"))["tarefas"]))
        self.assertIn("INSERT INTO tarefas", sql_path.read_text(encoding="utf-8"))
        self.assertTrue(powerbi_path.exists())
        self.assertIn("indicador", metricas_path.read_text(encoding="utf-8-sig"))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl não disponível neste ambiente de teste")
    def test_exporta_e_reimporta_planilha_excel(self) -> None:
        adicionar_tarefa(
            "Preparar base para Power BI",
            descricao="Consolidar dimensões de tarefa",
            categoria="Trabalho",
            prioridade="Alta",
            data_limite="2026-09-01",
            hora_limite="14:00",
            db_path=self.db_path,
        )
        workbook_path = exportar_excel(Path(self.temp_dir.name) / "analise.xlsx", self.db_path)
        destino = Path(self.temp_dir.name) / "importado.db"
        criar_tabela(destino)

        resultado = importar_planilha(workbook_path, destino)

        self.assertTrue(workbook_path.exists())
        self.assertEqual(1, resultado.importadas)
        tarefa = buscar_tarefas(destino)[0]
        self.assertEqual("Preparar base para Power BI", tarefa["titulo"])
        self.assertEqual("14:00", tarefa["hora_limite"])

    def test_categorias_e_projetos_sao_catalogos_reais(self) -> None:
        categoria_id = criar_categoria("Produto", "#A855F7", self.db_path)
        projeto_id = criar_projeto(
            "Lançamento",
            "Preparar a versão comercial",
            "2026-09-20",
            db_path=self.db_path,
        )
        tarefa_id = adicionar_tarefa(
            "Definir escopo",
            categoria="Produto",
            projeto_id=projeto_id,
            db_path=self.db_path,
        )

        categorias = {row["id"]: row for row in listar_categorias(self.db_path)}
        projeto = listar_projetos(self.db_path)[0]
        tarefa = buscar_tarefa_por_id(tarefa_id, self.db_path)

        self.assertEqual("Produto", categorias[categoria_id]["nome"])
        self.assertEqual(1, categorias[categoria_id]["total_tarefas"])
        self.assertEqual("Lançamento", projeto["nome"])
        self.assertEqual(1, projeto["total_tarefas"])
        self.assertEqual("Lançamento", tarefa["projeto"])

        excluir_projeto(projeto_id, self.db_path)
        self.assertIsNone(buscar_tarefa_por_id(tarefa_id, self.db_path)["projeto_id"])
        atualizar_tarefa(tarefa_id, "Definir escopo", categoria="Geral", db_path=self.db_path)
        excluir_categoria(categoria_id, self.db_path)
        self.assertNotIn(categoria_id, {row["id"] for row in listar_categorias(self.db_path)})


if __name__ == "__main__":
    unittest.main()
