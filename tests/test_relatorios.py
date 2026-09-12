"""Testes dos relatórios e dos três exportadores.

O XLSX e o PDF são escritos à mão (ADR-0002). Para não ficar pela fé, os
testes **leem de volta** o que foi gerado com openpyxl e pypdf — bibliotecas
de teste, que não entram no executável. Se não estiverem instaladas, esses
testes são ignorados em vez de dar falsa confiança.
"""

import csv
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree

import pytest

from reporting import exportadores, exportar, nome_sugerido
from reporting.construtor import relatorio_de_tarefas, tabela_de_tarefas
from reporting.modelo import Indicadores, Lista, Relatorio, Tabela, como_linhas

HOJE = date(2026, 6, 15)


def tarefas_de_exemplo():
    """Tarefas com concluídas, pendentes, atrasadas e acentos."""
    return [
        (1, "Preparar relatório anual", "2026-06-10", 1, "2026-06-01", "2026-06-08"),
        (2, "Rever orçamento & custos", "2026-06-01", 0, "2026-05-20", None),
        (3, "Reunião com direção", "2026-06-15", 0, "2026-06-12", None),
        (4, "Tarefa sem prazo", None, 0, "2026-06-05", None),
        (5, "Ação concluída", "2026-06-14", 1, "2026-06-02", "2026-06-14"),
    ]


@pytest.fixture
def relatorio():
    return relatorio_de_tarefas(dias=30, hoje=HOJE, tarefas=tarefas_de_exemplo())


# =================================================================== MODELO


def test_tabela_valida_o_numero_de_colunas():
    tabela = Tabela("T", colunas=["A", "B"], linhas=[["1", "2"], ["3"]])
    with pytest.raises(ValueError) as erro:
        tabela.validar()
    assert "Linha 1" in str(erro.value)


def test_secoes_vazias_ficam_de_fora():
    relatorio = Relatorio(
        titulo="R",
        secoes=[
            Indicadores("Vazia"),
            Lista("Com conteúdo", ["um"]),
            Tabela("Tabela vazia", colunas=["A"]),
        ],
    )
    assert [s.titulo for s in relatorio.secoes_com_conteudo()] == ["Com conteúdo"]


def test_como_linhas_normaliza_qualquer_seccao():
    assert como_linhas(Indicadores("I", [("a", "1")])) == [["a", "1"]]
    assert como_linhas(Lista("L", ["x"])) == [["x"]]
    assert como_linhas(Tabela("T", ["A"], [["1"]])) == [["A"], ["1"]]


def test_periodo_so_aparece_quando_existe():
    assert Relatorio(titulo="R").periodo == ""
    com_periodo = Relatorio(titulo="R", inicio=date(2026, 6, 1), fim=date(2026, 6, 30))
    assert com_periodo.periodo == "01/06/2026 – 30/06/2026"


# ================================================================ CONSTRUTOR


def test_relatorio_tem_as_tres_seccoes(relatorio):
    titulos = [s.titulo for s in relatorio.secoes]
    assert titulos == ["Indicadores", "Análise", "Tarefas"]
    relatorio.validar()


def test_indicadores_batem_com_a_analise(relatorio):
    from analytics import fontes

    visao = fontes.panorama(dias=30, hoje=HOJE, tarefas=tarefas_de_exemplo())
    valores = dict(relatorio.secoes[0].itens)
    assert valores["Pendentes"] == str(visao.kpis.pendentes)
    assert valores["Atrasadas"] == str(visao.kpis.atrasadas)
    assert valores["Criadas (30d)"] == str(visao.fluxo.criadas)


def test_tabela_poe_as_atrasadas_primeiro():
    tabela = tabela_de_tarefas(tarefas_de_exemplo(), hoje=HOJE)
    assert tabela.linhas[0][0] == "Rever orçamento & custos"
    assert tabela.linhas[0][2] == "Atrasada", "estado de uma tarefa vai no singular"


def test_tabela_respeita_o_limite():
    tabela = tabela_de_tarefas(tarefas_de_exemplo(), hoje=HOJE, limite=2)
    assert len(tabela.linhas) == 2


def test_tarefa_sem_datas_nao_inventa_texto():
    tabela = tabela_de_tarefas(tarefas_de_exemplo(), hoje=HOJE)
    linha = next(l for l in tabela.linhas if l[0] == "Tarefa sem prazo")
    assert linha[1] == "" and linha[4] == ""


def test_analise_usa_as_mesmas_frases_do_dashboard(relatorio):
    analise = relatorio.secoes[1]
    assert analise.itens
    assert any("atrasada" in item.lower() for item in analise.itens)


def test_relatorio_sem_tarefas_nao_rebenta():
    vazio = relatorio_de_tarefas(dias=30, hoje=HOJE, tarefas=[])
    vazio.validar()
    assert [s.titulo for s in vazio.secoes_com_conteudo()] == ["Indicadores"]


def test_relatorio_segue_o_idioma():
    import language_manager as lm

    lm.definir_idioma("en", persistir=False)
    relatorio = relatorio_de_tarefas(dias=30, hoje=HOJE, tarefas=tarefas_de_exemplo())
    assert relatorio.titulo == "Task Report"
    assert [s.titulo for s in relatorio.secoes] == ["Indicators", "Analysis", "Tasks"]


# ================================================================= SERVIÇO


def test_formatos_disponiveis():
    assert exportadores.FORMATOS == ("pdf", "xlsx", "csv")


def test_formato_desconhecido():
    with pytest.raises(ValueError):
        exportadores.obter("docx")


def test_formato_deduzido_da_extensao(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "saida.csv")
    assert destino.is_file()


def test_nome_sugerido_tem_data_e_extensao(relatorio):
    nome = nome_sugerido(relatorio, "pdf")
    assert nome.endswith(".pdf")
    assert relatorio.gerado_em.strftime("%Y%m%d") in nome
    assert " " not in nome


def test_exportar_exige_permissao(relatorio, tmp_path):
    from core import permissoes
    from core.permissoes import PermissaoNegadaError

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    with pytest.raises(PermissaoNegadaError):
        exportar(relatorio, tmp_path / "saida.pdf")
    assert not (tmp_path / "saida.pdf").exists()


def test_supervisor_le_mas_nao_exporta(relatorio, tmp_path):
    from core import permissoes
    from core.permissoes import PermissaoNegadaError

    permissoes.definir_sessao("carla", "supervisor", persistir=False)
    with pytest.raises(PermissaoNegadaError):
        exportar(relatorio, tmp_path / "saida.pdf")


def test_cria_a_pasta_de_destino(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "nova" / "pasta" / "r.csv")
    assert destino.is_file()


# ====================================================================== CSV


def test_csv_tem_todas_as_seccoes(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "r.csv")
    with open(destino, encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=";"))

    achatado = [celula for linha in linhas for celula in linha]
    assert "Relatório de Tarefas" in achatado
    assert "Indicadores" in achatado
    assert "Tarefas" in achatado
    assert "Preparar relatório anual" in achatado


def test_csv_preserva_acentos(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "r.csv")
    texto = destino.read_text(encoding="utf-8-sig")
    assert "Reunião com direção" in texto
    assert "orçamento" in texto


def test_csv_tem_bom_para_o_excel(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "r.csv")
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf")


# ===================================================================== XLSX


def test_xlsx_e_um_zip_com_as_partes_certas(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "r.xlsx")
    with zipfile.ZipFile(destino) as pacote:
        nomes = pacote.namelist()
        for parte in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"):
            assert parte in nomes
        # Todas as partes têm de ser XML bem formado. O conteúdo é gerado por
        # nós neste mesmo teste, por isso não há entrada não confiável aqui.
        for nome in nomes:
            ElementTree.fromstring(pacote.read(nome))


def test_xlsx_lido_de_volta_pelo_openpyxl(relatorio, tmp_path):
    openpyxl = pytest.importorskip("openpyxl", reason="openpyxl é só para validar")

    destino = exportar(relatorio, tmp_path / "r.xlsx")
    livro = openpyxl.load_workbook(destino)

    assert livro.sheetnames == ["Indicadores", "Análise", "Tarefas"]

    indicadores = livro["Indicadores"]
    assert indicadores["A1"].value == "Relatório de Tarefas"

    tarefas = livro["Tarefas"]
    cabecalho = [celula.value for celula in tarefas[1]]
    assert cabecalho[0] == "Descrição"
    assert tarefas[1][0].font.bold, "o cabeçalho da tabela vai a negrito"

    valores = [celula.value for linha in tarefas.iter_rows() for celula in linha]
    assert "Reunião com direção" in valores
    assert "Rever orçamento & custos" in valores, "o & tem de sobreviver ao XML"


def test_xlsx_grava_numeros_como_numeros(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")

    relatorio = Relatorio(
        titulo="Números",
        secoes=[Tabela("Dados", ["Texto", "Inteiro", "Decimal", "Código"],
                       [["abc", "42", "3,5", "007"]])],
    )
    destino = exportar(relatorio, tmp_path / "n.xlsx")
    folha = openpyxl.load_workbook(destino)["Dados"]

    # A primeira folha leva também o cabeçalho do relatório: procurar a tabela.
    linhas = list(folha.iter_rows(values_only=True))
    indice = next(i for i, linha in enumerate(linhas) if linha and linha[0] == "Texto")
    dados = linhas[indice + 1]

    assert dados[0] == "abc"
    assert dados[1] == 42
    assert dados[2] == 3.5
    assert dados[3] == "007", "zeros à esquerda não podem ser perdidos"


def test_xlsx_nome_de_folha_invalido_e_saneado(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")

    relatorio = Relatorio(
        titulo="R",
        secoes=[Lista("Nome/inválido: com [chars]" + "x" * 40, ["item"])],
    )
    destino = exportar(relatorio, tmp_path / "s.xlsx")
    nomes = openpyxl.load_workbook(destino).sheetnames
    assert len(nomes[0]) <= 31
    assert not set(nomes[0]) & set("[]:*?/\\")


def test_xlsx_titulos_repetidos_nao_colidem(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")

    relatorio = Relatorio(
        titulo="R",
        secoes=[Lista("Igual", ["a"]), Lista("Igual", ["b"])],
    )
    destino = exportar(relatorio, tmp_path / "d.xlsx")
    nomes = openpyxl.load_workbook(destino).sheetnames
    assert len(nomes) == len(set(nomes)) == 2


# ====================================================================== PDF


def test_pdf_tem_estrutura_valida(relatorio, tmp_path):
    destino = exportar(relatorio, tmp_path / "r.pdf")
    conteudo = destino.read_bytes()
    assert conteudo.startswith(b"%PDF-1.4")
    assert conteudo.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in conteudo
    assert b"startxref" in conteudo


def test_pdf_lido_de_volta_pelo_pypdf(relatorio, tmp_path):
    pypdf = pytest.importorskip("pypdf", reason="pypdf é só para validar")

    destino = exportar(relatorio, tmp_path / "r.pdf")
    leitor = pypdf.PdfReader(str(destino))
    assert len(leitor.pages) >= 1

    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    assert "Relatório de Tarefas" in texto
    assert "Indicadores" in texto
    assert "Preparar relatório anual" in texto
    assert "Reunião com direção" in texto, "acentos têm de sobreviver ao WinAnsi"


def test_pdf_pagina_quando_ha_muitas_linhas(tmp_path):
    pypdf = pytest.importorskip("pypdf")

    muitas = [
        (i, f"Tarefa {i}", "2026-06-20", 0, "2026-06-01", None) for i in range(1, 121)
    ]
    relatorio = relatorio_de_tarefas(dias=30, hoje=HOJE, tarefas=muitas)
    destino = exportar(relatorio, tmp_path / "grande.pdf")

    leitor = pypdf.PdfReader(str(destino))
    assert len(leitor.pages) > 1, "120 tarefas não cabem numa página"

    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    assert "Tarefa 1" in texto and "Tarefa 120" in texto
    # O cabeçalho da tabela repete-se nas páginas seguintes.
    assert texto.count("Descrição") >= 2


def test_pdf_numera_as_paginas(tmp_path):
    pypdf = pytest.importorskip("pypdf")

    muitas = [(i, f"T{i}", None, 0, "2026-06-01", None) for i in range(1, 121)]
    relatorio = relatorio_de_tarefas(dias=30, hoje=HOJE, tarefas=muitas)
    destino = exportar(relatorio, tmp_path / "n.pdf")

    leitor = pypdf.PdfReader(str(destino))
    total = len(leitor.pages)
    texto = leitor.pages[0].extract_text() or ""
    assert f"1/{total}" in texto


def test_pdf_com_caractere_fora_do_winansi_nao_corrompe(tmp_path):
    pypdf = pytest.importorskip("pypdf")

    relatorio = Relatorio(titulo="Relatório ☃ 日本", secoes=[Lista("L", ["emoji: 🚀"])])
    destino = exportar(relatorio, tmp_path / "u.pdf")
    leitor = pypdf.PdfReader(str(destino))
    assert len(leitor.pages) == 1
    assert "Relat" in (leitor.pages[0].extract_text() or "")


def test_pdf_sem_seccoes(tmp_path):
    pypdf = pytest.importorskip("pypdf")

    destino = exportar(Relatorio(titulo="Vazio"), tmp_path / "v.pdf")
    leitor = pypdf.PdfReader(str(destino))
    assert "Vazio" in (leitor.pages[0].extract_text() or "")


# ============================================================ ARQUITETURA


def test_exportadores_cumprem_o_contrato():
    for formato in exportadores.FORMATOS:
        modulo = exportadores.obter(formato)
        assert modulo.EXTENSAO.startswith(".")
        assert modulo.DESCRICAO
        assert callable(modulo.exportar)
