"""Importar ficheiros — e sobretudo os ficheiros como eles realmente vêm.

Uma importação decide-se na leitura. Um leitor que só aceite UTF-8 separado
por vírgulas falha no primeiro ficheiro exportado de um Excel português, e a
pessoa conclui que o programa não serve — uma conclusão razoável a partir do
que viu.

A outra metade é sobre nunca escrever às cegas, e sobre um ficheiro de fora
não poder fazer mal à máquina de quem o abre.
"""

import zipfile
from pathlib import Path

import pytest

import banco_de_dados as db
import importacoes_incluidas
from core import permissoes
from importacao import leitura, motor
from importacao.leitura import (
    FicheiroIlegivelError,
    FicheiroPerigosoError,
    FicheiroVazioError,
    Tabela,
)
from importacao.motor import Campo


@pytest.fixture(autouse=True)
def registo_limpo():
    motor.limpar()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    yield
    motor.limpar()


def escrever(tmp_path, nome: str, conteudo, codificacao="utf-8") -> Path:
    caminho = tmp_path / nome
    if isinstance(conteudo, bytes):
        caminho.write_bytes(conteudo)
    else:
        caminho.write_bytes(conteudo.encode(codificacao))
    return caminho


# ======================================================= LER O QUE VEM


@pytest.mark.parametrize(
    "codificacao", ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
)
def test_le_as_codificacoes_que_aparecem_na_vida_real(tmp_path, codificacao):
    conteudo = "descricao;vencimento\nReunião de orçamento;2030-01-31\n"
    caminho = escrever(tmp_path, "t.csv", conteudo, codificacao)

    tabela = leitura.ler(caminho)
    assert tabela.linhas[0][0] == "Reunião de orçamento"


@pytest.mark.parametrize("separador", [";", ",", "\t", "|"])
def test_descobre_o_separador(tmp_path, separador):
    conteudo = f"descricao{separador}vencimento\nUma tarefa{separador}2030-01-31\n"
    tabela = leitura.ler(escrever(tmp_path, "t.csv", conteudo))

    assert tabela.separador == separador
    assert tabela.cabecalho == ["descricao", "vencimento"]


def test_uma_virgula_dentro_do_texto_nao_confunde(tmp_path):
    """Um separador a sério é regular; uma vírgula numa frase não é."""
    conteudo = (
        "descricao;vencimento\n"
        "Comprar pão, leite e ovos;2030-01-31\n"
        "Rever contrato, versão final;2030-02-01\n"
    )
    tabela = leitura.ler(escrever(tmp_path, "t.csv", conteudo))

    assert tabela.separador == ";"
    assert tabela.linhas[0][0] == "Comprar pão, leite e ovos"


def test_o_bom_do_excel_nao_entra_no_primeiro_cabecalho(tmp_path):
    """Sem isto a primeira coluna chamava-se "\\ufeffdescricao" e nunca mapeava."""
    caminho = escrever(tmp_path, "t.csv", "descricao;prazo\nUma;2030-01-01\n", "utf-8-sig")
    assert leitura.ler(caminho).cabecalho[0] == "descricao"


def test_linhas_vazias_no_fim_nao_contam_como_dados(tmp_path):
    """Quase todos os ficheiros exportados as trazem."""
    conteudo = "descricao;prazo\nUma;2030-01-01\n\n\n;\n"
    assert len(leitura.ler(escrever(tmp_path, "t.csv", conteudo))) == 1


def test_um_ficheiro_so_com_cabecalho_e_recusado(tmp_path):
    with pytest.raises(FicheiroVazioError):
        leitura.ler(escrever(tmp_path, "t.csv", "descricao;prazo\n"))


def test_um_ficheiro_vazio_e_recusado(tmp_path):
    with pytest.raises(FicheiroVazioError):
        leitura.ler(escrever(tmp_path, "t.csv", ""))


def test_um_ficheiro_que_nao_existe(tmp_path):
    with pytest.raises(FicheiroIlegivelError):
        leitura.ler(tmp_path / "nao-existe.csv")


def test_uma_extensao_desconhecida_e_recusada(tmp_path):
    with pytest.raises(FicheiroIlegivelError, match="CSV ou XLSX"):
        leitura.ler(escrever(tmp_path, "t.pdf", "seja o que for"))


# =============================================================== XLSX


def criar_xlsx(caminho: Path, linhas, partilhadas=None) -> Path:
    """Escreve um XLSX mínimo, como o Excel escreveria."""
    partilhadas = partilhadas or []
    celulas = []
    for numero, linha in enumerate(linhas, start=1):
        cs = "".join(
            f'<c r="{chr(ord("A") + i)}{numero}" t="inlineStr">'
            f"<is><t>{valor}</t></is></c>"
            for i, valor in enumerate(linha)
            if valor != ""
        )
        celulas.append(f'<row r="{numero}">{cs}</row>')

    folha = (
        '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main"><sheetData>' + "".join(celulas) + "</sheetData></worksheet>"
    )
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("xl/worksheets/sheet1.xml", folha)
    return caminho


def test_le_um_xlsx(tmp_path):
    caminho = criar_xlsx(
        tmp_path / "t.xlsx",
        [["descricao", "vencimento"], ["Rever contrato", "2030-01-31"]],
    )
    tabela = leitura.ler(caminho)

    assert tabela.cabecalho == ["descricao", "vencimento"]
    assert tabela.linhas[0] == ["Rever contrato", "2030-01-31"]


def test_uma_celula_vazia_no_meio_nao_desloca_as_outras(tmp_path):
    """O Excel omite as células vazias.

    Sem ler a referência da célula, a data ia parar à coluna do nome e
    ninguém reparava.
    """
    caminho = criar_xlsx(
        tmp_path / "t.xlsx",
        [["codigo", "nome", "minimo"], ["PAR-01", "", "10"]],
    )
    assert leitura.ler(caminho).linhas[0] == ["PAR-01", "", "10"]


def test_um_xlsx_e_lido_mesmo_com_a_extensao_errada(tmp_path):
    """As pessoas renomeiam ficheiros; recusar pelo nome é recusar por nada."""
    caminho = criar_xlsx(tmp_path / "t.csv", [["a", "b"], ["1", "2"]])
    assert leitura.ler(caminho).cabecalho == ["a", "b"]


def test_um_zip_que_nao_e_xlsx(tmp_path):
    caminho = tmp_path / "t.xlsx"
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("qualquer.txt", "nada a ver")
    with pytest.raises(FicheiroIlegivelError):
        leitura.ler(caminho)


# ================================================ UM FICHEIRO DE FORA


def test_um_xlsx_com_entidades_xml_e_recusado(tmp_path):
    """O ataque *billion laughs*: 1 KB que consome toda a memória.

    A biblioteca padrão expande entidades declaradas no documento, e a
    aplicação não tem `defusedxml` porque não tem dependências (ADR-0002). A
    defesa é recusar antes de analisar — uma folha de cálculo a sério não traz
    declarações de entidades.
    """
    bomba = (
        '<?xml version="1.0"?>'
        "<!DOCTYPE lol [<!ENTITY lol 'aa'>"
        "<!ENTITY lol2 '&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;'>]>"
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData><row><c><v>&lol2;</v></c></row></sheetData></worksheet>"
    )
    caminho = tmp_path / "bomba.xlsx"
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("xl/worksheets/sheet1.xml", bomba)

    with pytest.raises(FicheiroPerigosoError, match="entidades"):
        leitura.ler(caminho)


def test_o_mesmo_vale_para_a_tabela_de_strings(tmp_path):
    """As duas partes de um XLSX são XML, e as duas vêm de fora."""
    caminho = tmp_path / "bomba.xlsx"
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><sst/>',
        )
        pacote.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")

    with pytest.raises(FicheiroPerigosoError):
        leitura.ler(caminho)


# ============================================================ DESTINOS


def destino_simples(**extra):
    return motor.registar(
        "teste",
        campos=[Campo("nome", obrigatorio=True), Campo("nota")],
        validar=lambda d: [] if d.get("nome") else ["sem nome"],
        criar=lambda d: criados.append(d),
        **extra,
    )


criados = []


@pytest.fixture(autouse=True)
def limpar_criados():
    criados.clear()


def test_um_destino_registado_aparece():
    destino_simples()
    assert [d.nome for d in motor.disponiveis()] == ["teste"]


@pytest.mark.parametrize("mau", ["", "   "])
def test_um_destino_precisa_de_nome(mau):
    with pytest.raises(ValueError):
        motor.registar(mau, [Campo("x")], lambda d: [], lambda d: None)


def test_um_destino_precisa_de_campos():
    with pytest.raises(ValueError, match="campos"):
        motor.registar("x", [], lambda d: [], lambda d: None)


def test_um_modulo_tem_de_prefixar_o_seu_destino():
    with pytest.raises(ValueError, match="prefixar"):
        motor.registar("itens", [Campo("x")], lambda d: [], lambda d: None, dono="estoque")


def test_um_destino_sem_permissao_nao_aparece():
    """Oferecer para depois recusar é pior do que não oferecer."""
    destino_simples(permissao="sistema.admin")
    permissoes.definir_sessao("olga", "colaborador", persistir=False)
    assert motor.disponiveis() == []


# ========================================================== MAPEAMENTO


def test_adivinha_as_colunas_pelo_nome():
    destino = destino_simples()
    tabela = Tabela(["Nome", "Nota"], [["a", "b"]])
    assert motor.sugerir_mapa(tabela, destino) == {"nome": "Nome", "nota": "Nota"}


def test_adivinha_sem_acentos_e_com_texto_a_mais():
    """"Descrição da tarefa" tem de servir para o campo "descricao"."""
    destino = motor.registar(
        "t", [Campo("descricao")], lambda d: [], lambda d: None
    )
    tabela = Tabela(["Descrição da tarefa"], [["x"]])
    assert motor.sugerir_mapa(tabela, destino) == {"descricao": "Descrição da tarefa"}


def test_uma_coluna_nao_e_usada_duas_vezes():
    destino = destino_simples()
    tabela = Tabela(["Nome"], [["a"]])
    assert motor.sugerir_mapa(tabela, destino) == {"nome": "Nome"}


def test_o_que_nao_se_adivinha_fica_de_fora():
    destino = destino_simples()
    tabela = Tabela(["Coluna A", "Coluna B"], [["a", "b"]])
    assert motor.sugerir_mapa(tabela, destino) == {}


# ============================================================ PREVISÃO


def test_a_previsao_nao_escreve_nada():
    """O teste que define esta peça: ver antes de fazer."""
    destino = destino_simples()
    tabela = Tabela(["nome"], [["Ana"], ["Bruno"]])

    previsao = motor.prever(tabela, destino, {"nome": "nome"})
    assert len(previsao.aceites) == 2
    assert criados == [], "prever não pode criar"


def test_a_previsao_diz_qual_linha_falha_e_porque():
    destino = destino_simples()
    tabela = Tabela(["nome"], [["Ana"], [""], ["Carla"]])

    previsao = motor.prever(tabela, destino, {"nome": "nome"})
    assert len(previsao.aceites) == 2
    assert previsao.problemas[0].linha == 3, "cabeçalho é 1, primeira linha é 2"
    assert "sem nome" in previsao.problemas[0].motivo


def test_faltar_uma_coluna_obrigatoria_e_dito_de_uma_vez():
    """Repetir "falta a coluna nome" trezentas vezes não ajuda ninguém."""
    destino = destino_simples()
    tabela = Tabela(["outra"], [["x"]] * 300)

    previsao = motor.prever(tabela, destino, {"nota": "outra"})
    assert len(previsao.problemas) == 1
    assert "obrigatórias" in previsao.problemas[0].motivo


def test_um_destino_que_rebenta_a_validar_nao_passa_por_bom():
    def explode(dados):
        raise RuntimeError("rebentei")

    destino = motor.registar("x", [Campo("a")], explode, lambda d: None)
    previsao = motor.prever(Tabela(["a"], [["1"]]), destino, {"a": "a"})

    assert previsao.aceites == []
    assert "rebentei" in previsao.problemas[0].motivo


# =========================================================== IMPORTAR


def test_importa_o_que_passa():
    destino = destino_simples()
    tabela = Tabela(["nome"], [["Ana"], ["Bruno"]])

    resultado = motor.importar(tabela, destino, {"nome": "nome"})
    assert resultado.criados == 2
    assert [d["nome"] for d in criados] == ["Ana", "Bruno"]


def test_uma_linha_ma_nao_cancela_as_boas():
    """300 linhas não podem ficar reféns de uma data mal escrita na linha 7."""
    destino = destino_simples()
    tabela = Tabela(["nome"], [["Ana"], [""], ["Carla"]])

    resultado = motor.importar(tabela, destino, {"nome": "nome"})
    assert resultado.criados == 2
    assert resultado.houve_falhas


def test_uma_falha_a_escrever_aponta_a_linha_certa():
    def criar(dados):
        if dados["nome"] == "Bruno":
            raise RuntimeError("o banco recusou")
        criados.append(dados)

    destino = motor.registar(
        "x", [Campo("nome", obrigatorio=True)], lambda d: [], criar
    )
    tabela = Tabela(["nome"], [["Ana"], ["Bruno"], ["Carla"]])

    resultado = motor.importar(tabela, destino, {"nome": "nome"})
    assert resultado.criados == 2
    assert resultado.problemas[0].linha == 3


def test_importar_exige_a_permissao_do_destino():
    from core.permissoes import PermissaoNegadaError

    destino = destino_simples(permissao="sistema.admin")
    permissoes.definir_sessao("olga", "colaborador", persistir=False)

    with pytest.raises(PermissaoNegadaError):
        motor.importar(Tabela(["nome"], [["Ana"]]), destino, {"nome": "nome"})
    assert criados == []


# ==================================================== TAREFAS, A SÉRIO


@pytest.mark.parametrize(
    "escrita,esperado",
    [
        ("2030-01-31", "2030-01-31"),
        ("31/01/2030", "2030-01-31"),
        ("31-01-2030", "2030-01-31"),
        ("31.01.2030", "2030-01-31"),
        ("2030-01-31T10:00:00", "2030-01-31"),
        ("", ""),
    ],
)
def test_as_datas_vem_escritas_de_muitas_maneiras(escrita, esperado):
    """Recusar "31/12/2030" seria recusar o formato em que o ficheiro vem."""
    assert importacoes_incluidas.interpretar_data(escrita) == esperado


def test_uma_data_que_nao_e_data_e_recusada():
    """Guardar "amanhã" como prazo dá uma lista que nunca mais faz sentido."""
    with pytest.raises(ValueError):
        importacoes_incluidas.interpretar_data("amanhã")


def test_importar_tarefas_de_um_ficheiro(tmp_path):
    importacoes_incluidas.registar_incluidos()
    conteudo = (
        "Descrição;Vencimento\n"
        "Rever contrato;31/01/2030\n"
        "Preparar orçamento;2030-02-15\n"
        "Sem prazo;\n"
    )
    tabela = leitura.ler(escrever(tmp_path, "t.csv", conteudo, "cp1252"))
    destino = motor.obter("tarefas")
    mapa = motor.sugerir_mapa(tabela, destino)

    assert mapa == {"descricao": "Descrição", "vencimento": "Vencimento"}
    resultado = motor.importar(tabela, destino, mapa)

    assert resultado.criados == 3
    guardadas = {t[1]: t[2] for t in db.buscar_tarefas()}
    assert guardadas["Rever contrato"] == "2030-01-31"
    assert guardadas["Sem prazo"] in (None, "")


def test_uma_tarefa_sem_descricao_nao_entra(tmp_path):
    importacoes_incluidas.registar_incluidos()
    tabela = Tabela(["descricao"], [["Boa"], [""]])

    resultado = motor.importar(tabela, motor.obter("tarefas"), {"descricao": "descricao"})
    assert resultado.criados == 1
    assert [t[1] for t in db.buscar_tarefas()] == ["Boa"]


def test_importar_respeita_quem_esta_em_sessao(tmp_path):
    """A importação passa pelo serviço: não é uma porta para escrever mais."""
    from core.permissoes import PermissaoNegadaError

    importacoes_incluidas.registar_incluidos()
    permissoes.definir_sessao("olga", "visualizador", persistir=False)

    with pytest.raises(PermissaoNegadaError):
        motor.importar(
            Tabela(["descricao"], [["Uma"]]),
            motor.obter("tarefas"),
            {"descricao": "descricao"},
        )
    assert db.buscar_tarefas() == []


def test_uma_linha_repetida_no_proprio_ficheiro_e_apanhada_na_previsao():
    """A previsao tem de dizer a verdade sobre o que vai entrar.

    O destino valida contra o que ja esta guardado, e ao prever ainda nada foi
    escrito -- por isso duas linhas com a mesma chave passavam as duas, e a
    segunda so falhava ao escrever. A previsao dizia 3 e entravam 2.

    Encontrado a correr uma importacao a serio, nao a ler o codigo.
    """
    destino = motor.registar(
        "x",
        campos=[Campo("codigo", obrigatorio=True, chave=True), Campo("nome")],
        validar=lambda d: [],
        criar=lambda d: criados.append(d),
    )
    tabela = Tabela(["codigo", "nome"], [["A", "um"], ["B", "dois"], ["a", "repetido"]])

    previsao = motor.prever(tabela, destino, {"codigo": "codigo", "nome": "nome"})
    assert len(previsao.aceites) == 2
    assert previsao.problemas[0].linha == 4
    assert "repetido" in previsao.problemas[0].motivo

    resultado = motor.importar(tabela, destino, {"codigo": "codigo", "nome": "nome"})
    assert resultado.criados == len(previsao.aceites), "o que foi previsto e o que entra"


def test_uma_chave_vazia_nao_conta_como_repeticao():
    """Duas linhas sem codigo sao duas linhas incompletas, nao duplicados."""
    destino = motor.registar(
        "x",
        campos=[Campo("codigo", chave=True)],
        validar=lambda d: [],
        criar=lambda d: criados.append(d),
    )
    previsao = motor.prever(Tabela(["codigo"], [[""], [""]]), destino, {"codigo": "codigo"})
    assert len(previsao.aceites) == 2
