"""Pesquisa global — e sobretudo o que ela não pode deixar ver.

Uma pesquisa é a porta lateral mais fácil de abrir sem querer: junta tudo o
que existe e mostra numa lista. Se uma fonte não aplicar as permissões do
sítio de onde os dados vêm, um colaborador que procure "orçamento" vê a tarefa
do colega — e a aplicação passa a contradizer-se a si própria.

Metade destes testes é sobre isso.
"""

import pytest

import database as db
import pesquisa
import pesquisas_incluidas
from core import organizacao, permissoes, utilizadores
from core.organizacao import TipoUnidade
from pesquisa import Resultado
from regras import repositorio
from regras.modelo import Acao

SENHA = "Uma-Senha-Longa-123"


@pytest.fixture(autouse=True)
def registo_limpo():
    pesquisa.limpar()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    yield
    pesquisa.limpar()


@pytest.fixture
def incluidas():
    pesquisas_incluidas.registar_incluidas()


# ================================================================= REGISTO


def test_sem_fontes_nao_ha_resultados():
    assert pesquisa.procurar("qualquer coisa") == []


def test_uma_fonte_registada_contribui():
    pesquisa.registar("teste", lambda termo, limite: [Resultado("teste", "Achado")])
    assert [r.titulo for r in pesquisa.procurar("ach")] == ["Achado"]


def test_registar_a_mesma_fonte_substitui():
    """Um plugin recarregado não pode obrigar a reiniciar a aplicação."""
    pesquisa.registar("x", lambda t, l: [Resultado("x", "antigo")])
    pesquisa.registar("x", lambda t, l: [Resultado("x", "novo")])
    assert [r.titulo for r in pesquisa.procurar("ovo")] == ["novo"]


def test_uma_fonte_de_um_plugin_sai_com_ele():
    pesquisa.registar("estoque", lambda t, l: [], dono="estoque")
    assert pesquisa.esquecer_por_dono("estoque") == 1
    assert pesquisa.fontes() == []


@pytest.mark.parametrize("mau", ["", "   "])
def test_uma_fonte_precisa_de_nome(mau):
    with pytest.raises(ValueError):
        pesquisa.registar(mau, lambda t, l: [])


def test_uma_fonte_tem_de_ser_chamavel():
    with pytest.raises(ValueError):
        pesquisa.registar("x", "isto não é uma função")


# ================================================================ PROCURAR


@pytest.mark.parametrize("termo", ["", " ", "a"])
def test_um_termo_curto_nao_devolve_tudo(termo):
    """"Tudo" não é um resultado de pesquisa: é a base de dados no ecrã."""
    pesquisa.registar("teste", lambda t, l: [Resultado("teste", "Achado")])
    assert pesquisa.procurar(termo) == []


def test_cada_fonte_tem_o_seu_limite():
    """Sem isto, uma fonte com muitos resultados esconde as outras."""
    muitos = lambda termo, limite: [Resultado("a", f"n{i}") for i in range(100)]
    pesquisa.registar("a", muitos)
    pesquisa.registar("b", lambda t, l: [Resultado("b", "único")])

    # Termo com duas letras: um de uma letra é recusado, e bem.
    resultados = pesquisa.procurar("nn", limite_por_fonte=3)
    assert len([r for r in resultados if r.fonte == "a"]) == 3


def test_uma_fonte_que_rebenta_nao_estraga_a_pesquisa():
    """Um módulo partido não pode tornar a pesquisa inútil para os outros."""
    def explode(termo, limite):
        raise RuntimeError("rebentei")

    pesquisa.registar("partida", explode)
    pesquisa.registar("boa", lambda t, l: [Resultado("boa", "Achado")])

    assert [r.titulo for r in pesquisa.procurar("ach")] == ["Achado"]


def test_os_resultados_vem_agrupados_por_fonte():
    pesquisa.registar("a", lambda t, l: [Resultado("a", "um"), Resultado("a", "dois")])
    pesquisa.registar("b", lambda t, l: [Resultado("b", "tres")])

    grupos = pesquisa.agrupados("oo")
    assert set(grupos) == {"a", "b"}
    assert len(grupos["a"]) == 2


# =========================================================== COMPARAÇÃO


@pytest.mark.parametrize(
    "texto,termo",
    [
        ("Tarefa Atrasada", "atrasada"),
        ("reunião de equipa", "reuniao"),
        ("Reuniao", "reunião"),
        ("ORÇAMENTO", "orcamento"),
        ("São Paulo", "sao paulo"),
    ],
)
def test_encontra_sem_acentos_e_sem_maiusculas(texto, termo):
    """Obrigar a escrever o acento certo para encontrar o que se sabe que
    existe é hostil."""
    assert pesquisa.contem(texto, termo)


def test_nao_encontra_o_que_nao_esta_la():
    assert not pesquisa.contem("Tarefa", "inventado")


def test_texto_vazio_nao_rebenta():
    assert not pesquisa.contem(None, "x")
    assert not pesquisa.contem("", "x")


# ================================================ AS FONTES DA APLICAÇÃO


def test_encontra_uma_tarefa(incluidas):
    db.adicionar_tarefa("Preparar orçamento anual", "2030-01-01", criada_por="ana")
    resultados = pesquisa.procurar("orcamento")

    assert [r.titulo for r in resultados] == ["Preparar orçamento anual"]
    assert resultados[0].fonte == "tarefas"


def test_encontra_uma_unidade_com_o_caminho(incluidas):
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, empresa.id)

    encontrados = [r for r in pesquisa.procurar("engenharia") if r.fonte == "unidades"]
    assert encontrados[0].detalhe == "Acme > Engenharia"


def test_encontra_uma_regra(incluidas):
    repositorio.criar("Repor material", "estoque.em_falta", acoes=[Acao("registar")])

    encontrados = [r for r in pesquisa.procurar("repor") if r.fonte == "regras"]
    assert encontrados[0].detalhe == "quando estoque.em_falta"


def test_encontra_uma_conta(incluidas):
    utilizadores.criar("bruno", SENHA, papel="colaborador", nome="Bruno Silva")

    encontrados = [r for r in pesquisa.procurar("bruno") if r.fonte == "contas"]
    assert encontrados[0].titulo == "Bruno Silva"


# ================================================ O QUE NÃO PODE APARECER


def test_a_pesquisa_nao_mostra_tarefas_que_a_sessao_nao_ve(incluidas):
    """O teste que define esta peça.

    Se a fonte consultasse o armazenamento em vez do serviço, a pesquisa
    mostrava o que a lista de tarefas esconde — e a aplicação passava a
    contradizer-se a si própria.
    """
    db.adicionar_tarefa("Orçamento da Ana", "2030-01-01", criada_por="ana")
    db.adicionar_tarefa("Orçamento do Bruno", "2030-01-02", criada_por="bruno")

    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    titulos = [r.titulo for r in pesquisa.procurar("orcamento")]

    assert "Orçamento da Ana" in titulos
    assert "Orçamento do Bruno" not in titulos


def test_quem_nao_gere_contas_nao_descobre_que_contas_existem(incluidas):
    """A janela de contas não lhe é mostrada; a pesquisa também não pode."""
    utilizadores.criar("bruno", SENHA, papel="colaborador", nome="Bruno Silva")

    permissoes.definir_sessao("olga", "colaborador", persistir=False)
    assert [r for r in pesquisa.procurar("bruno") if r.fonte == "contas"] == []


def test_quem_nao_administra_nao_ve_as_automacoes(incluidas):
    repositorio.criar("Repor material", "estoque.em_falta", acoes=[Acao("registar")])

    permissoes.definir_sessao("olga", "colaborador", persistir=False)
    assert [r for r in pesquisa.procurar("repor") if r.fonte == "regras"] == []


def test_um_gestor_ve_as_tarefas_de_todos(incluidas):
    """O âmbito é o do serviço, não uma regra própria da pesquisa."""
    db.adicionar_tarefa("Orçamento do Bruno", "2030-01-02", criada_por="bruno")

    permissoes.definir_sessao("chefe", "gestor", persistir=False)
    assert "Orçamento do Bruno" in [r.titulo for r in pesquisa.procurar("orcamento")]


def test_as_fontes_nao_falam_com_o_banco_diretamente():
    """A defesa acima só se aguenta enquanto isto for verdade."""
    import ast
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / "src" / "pesquisas_incluidas.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            origem = getattr(no, "module", "") or ""
            nomes = [a.name for a in no.names] + [origem]
            assert "database" not in nomes, "as fontes passam pelos serviços"
