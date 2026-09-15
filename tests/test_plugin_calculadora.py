"""A calculadora: as contas certas, e os números errados recusados.

Uma calculadora que devolve um resultado errado é pior do que uma que não
existe, porque ninguém confere. Por isso a maior parte destes testes é sobre
os casos em que a resposta certa é **recusar**: dividir por zero, raiz de
negativo, converter metros em quilos, tirar mais do que existe.

E há um teste que não é sobre contas nenhumas: o que verifica que não há
`eval()`.
"""

import ast
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parent.parent / "plugins" / "available" / "calculadora"


def carregar(nome: str):
    """Importa um módulo do plugin sem o carregar como plugin."""
    chave = f"calculadora_{nome}_teste"
    especificacao = importlib.util.spec_from_file_location(chave, PASTA / f"{nome}.py")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[chave] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


calculo = carregar("calculo")
conversoes = carregar("conversoes")
financeiro = carregar("financeiro")


# ========================================== SEM EXECUÇÃO DE CÓDIGO


def test_nao_ha_eval_em_lado_nenhum():
    """A forma rápida de fazer isto seria `eval`, e é a errada.

    `eval` executa código, não aritmética. Numa aplicação que guarda tarefas,
    contas e inventário de uma empresa, uma caixa de texto ligada ao `eval` é
    um buraco por onde entra tudo.
    """
    perigosas = {"eval", "exec", "compile", "__import__", "globals", "locals"}
    for arquivo in PASTA.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                assert no.func.id not in perigosas, f"{arquivo.name} chama {no.func.id}"


@pytest.mark.parametrize(
    "hostil",
    [
        "__import__('os')",
        "open('x')",
        "1; import os",
        "[].__class__",
        "lambda: 1",
        "exec('x=1')",
    ],
)
def test_texto_hostil_e_recusado_como_expressao(hostil):
    """Não é bloqueado por uma lista negra: simplesmente não existe."""
    with pytest.raises(calculo.ErroDeCalculo):
        calculo.avaliar(hostil)


# ========================================================= ARITMÉTICA


@pytest.mark.parametrize(
    "expressao,esperado",
    [
        ("2+3", 5),
        ("2+3*4", 14),
        ("(2+3)*4", 20),
        ("10/4", 2.5),
        ("7//2", 3),
        ("7%3", 1),
        ("2^10", 1024),
        ("-5", -5),
        ("--5", 5),
        ("3 - -2", 5),
        ("1.5*2", 3),
        ("100 % 7", 2),
    ],
)
def test_contas_simples(expressao, esperado):
    assert calculo.avaliar(expressao) == pytest.approx(esperado)


def test_a_potencia_associa_a_direita():
    """2^3^2 é 2^(3^2) = 512, não (2^3)^2 = 64."""
    assert calculo.avaliar("2^3^2") == 512


def test_o_menos_unario_nao_engole_a_potencia():
    """-2^2 é -(2^2) = -4, como em qualquer calculadora científica."""
    assert calculo.avaliar("-2^2") == -4
    assert calculo.avaliar("(-2)^2") == 4


def test_espacos_e_simbolos_do_teclado_real():
    """As pessoas colam contas de folhas de cálculo e documentos."""
    assert calculo.avaliar("  2 × 3  ") == 6
    assert calculo.avaliar("10 ÷ 4") == 2.5
    assert calculo.avaliar("2 ** 3") == 8


# ============================================================ CIENTÍFICA


def test_trigonometria_em_graus():
    assert calculo.avaliar("sin(90)") == pytest.approx(1)
    assert calculo.avaliar("cos(0)") == pytest.approx(1)


def test_cosseno_de_90_e_zero_e_nao_quase_zero():
    """6.1e-17 é matematicamente defensável e assusta quem só queria 0."""
    assert calculo.avaliar("cos(90)") == 0.0


def test_trigonometria_em_radianos():
    assert calculo.avaliar("sin(pi/2)", calculo.Angulo.RADIANOS) == pytest.approx(1)


def test_o_modo_de_angulo_muda_o_resultado():
    """O mesmo texto, duas respostas certas — por isso o modo é explícito."""
    graus = calculo.avaliar("sin(1)", calculo.Angulo.GRAUS)
    radianos = calculo.avaliar("sin(1)", calculo.Angulo.RADIANOS)
    assert graus != radianos


@pytest.mark.parametrize(
    "expressao,esperado",
    [
        ("raiz(16)", 4),
        ("ln(e)", 1),
        ("log(1000)", 3),
        ("log2(8)", 3),
        ("exp(0)", 1),
        ("fact(5)", 120),
        ("abs(-7)", 7),
        ("floor(2.7)", 2),
        ("ceil(2.1)", 3),
        ("round(3.14159, 2)", 3.14),
        ("max(3, 7)", 7),
        ("min(3, 7)", 3),
        ("atan(1)", 45),
    ],
)
def test_funcoes(expressao, esperado):
    assert calculo.avaliar(expressao) == pytest.approx(esperado)


# =================================================== O QUE TEM DE SER RECUSADO


@pytest.mark.parametrize("expressao", ["1/0", "1//0", "1%0"])
def test_divisao_por_zero(expressao):
    with pytest.raises(calculo.DominioError):
        calculo.avaliar(expressao)


@pytest.mark.parametrize(
    "expressao", ["raiz(-1)", "ln(0)", "ln(-1)", "log(0)", "asin(2)", "acos(-5)", "fact(-1)", "fact(0.5)"]
)
def test_fora_do_dominio(expressao):
    """Inventar um resultado seria pior do que recusar."""
    with pytest.raises(calculo.DominioError):
        calculo.avaliar(expressao)


def test_um_resultado_grande_demais_e_recusado():
    """Devolver `inf` como se fosse um número é mentir com jeito."""
    with pytest.raises(calculo.DominioError):
        calculo.avaliar("9^9^9")


@pytest.mark.parametrize(
    "expressao", ["", "   ", "2+", "*2", "(2+3", "2+3)", "2 3", "1.2.3", "2 @ 3"]
)
def test_expressoes_malformadas(expressao):
    with pytest.raises(calculo.ExpressaoInvalidaError):
        calculo.avaliar(expressao)


def test_funcao_que_nao_existe():
    with pytest.raises(calculo.NomeDesconhecidoError, match="banana"):
        calculo.avaliar("banana(2)")


def test_o_erro_diz_onde_e():
    """Uma mensagem sem posição obriga a procurar o erro à vista."""
    with pytest.raises(calculo.ExpressaoInvalidaError, match="posição"):
        calculo.avaliar("2 + @")


def test_numero_errado_de_argumentos():
    with pytest.raises(calculo.ExpressaoInvalidaError):
        calculo.avaliar("sin(1, 2)")


# ============================================================= CONVERSÕES


@pytest.mark.parametrize(
    "valor,de,para,esperado",
    [
        (1, "km", "m", 1000),
        (1, "milha", "km", 1.609344),
        (1, "pol", "cm", 2.54),
        (1, "kg", "g", 1000),
        (1, "libra", "kg", 0.45359237),
        (1, "h", "min", 60),
        (1, "gib", "mib", 1024),
        (1, "gb", "mb", 1000),
        (100, "km/h", "m/s", 27.7777778),
        (1, "hectare", "m2", 10000),
    ],
)
def test_conversoes(valor, de, para, esperado):
    assert conversoes.converter(valor, de, para) == pytest.approx(esperado)


@pytest.mark.parametrize(
    "valor,de,para,esperado",
    [(0, "c", "f", 32), (100, "c", "f", 212), (-40, "c", "f", -40), (0, "c", "k", 273.15), (32, "f", "c", 0)],
)
def test_temperatura(valor, de, para, esperado):
    """A temperatura é afim, não proporcional: 0 °C não é 0 °F."""
    assert conversoes.converter_temperatura(valor, de, para) == pytest.approx(esperado)


def test_o_zero_absoluto_e_um_limite():
    with pytest.raises(conversoes.ConversaoError):
        conversoes.converter_temperatura(-300, "c", "f")


def test_nao_se_converte_entre_grandezas_diferentes():
    """A multiplicação era possível; o resultado não queria dizer nada."""
    with pytest.raises(conversoes.ConversaoError, match="diferentes"):
        conversoes.converter(1, "m", "kg")


def test_unidade_desconhecida():
    with pytest.raises(conversoes.UnidadeDesconhecidaError):
        conversoes.converter(1, "m", "parsec")


def test_ida_e_volta_nao_perde_o_valor():
    for de, para in (("km", "milha"), ("kg", "libra"), ("l", "galao_us")):
        ida = conversoes.converter(7, de, para)
        assert conversoes.converter(ida, para, de) == pytest.approx(7)


def test_a_tabela_mostra_a_familia_toda():
    linhas = dict(conversoes.tabela(1, "m"))
    assert linhas["km"] == pytest.approx(0.001)
    assert linhas["cm"] == pytest.approx(100)


def test_nao_ha_moedas():
    """Taxas de câmbio exigem rede; uma taxa gravada no código mentiria."""
    todas = {u for familia in conversoes.familias() for u in conversoes.unidades_de(familia)}
    assert not {"eur", "usd", "brl", "gbp"} & todas


# ============================================================= FINANCEIRA


def test_a_prestacao_de_um_emprestimo():
    taxa = financeiro.taxa_nominal_para_periodo(Decimal("0.06"))
    assert financeiro.prestacao(100000, taxa, 360) == Decimal("599.55")


def test_sem_juros_a_prestacao_e_a_divisao():
    assert financeiro.prestacao(1200, 0, 12) == Decimal("100.00")


def test_a_tabela_de_amortizacao_fecha_em_zero():
    """Sem isto, 360 meses acabam a dever cêntimos a ninguém."""
    taxa = financeiro.taxa_nominal_para_periodo(Decimal("0.06"))
    parcelas = financeiro.amortizacao(100000, taxa, 360)

    assert len(parcelas) == 360
    assert parcelas[-1].saldo == Decimal("0.00")
    assert sum(p.amortizacao for p in parcelas) == Decimal("100000.00")


def test_os_juros_descem_e_a_amortizacao_sobe():
    """É a forma da tabela francesa, e serve de controlo ao cálculo."""
    taxa = financeiro.taxa_nominal_para_periodo(Decimal("0.06"))
    parcelas = financeiro.amortizacao(50000, taxa, 120)

    assert parcelas[0].juros > parcelas[-1].juros
    assert parcelas[0].amortizacao < parcelas[-1].amortizacao


def test_a_taxa_equivalente_nao_e_a_divisao():
    """Dividir 12% por 12 dá 1%; composto, isso são 12,68% ao ano, não 12%."""
    equivalente = financeiro.taxa_equivalente(Decimal("0.12"))
    nominal = financeiro.taxa_nominal_para_periodo(Decimal("0.12"))

    assert equivalente < nominal
    # Composta doze vezes, a equivalente devolve exatamente a taxa anual
    # anunciada — é isso que a torna equivalente. Comparado em Decimal: passar
    # por float aqui seria trocar a precisão que o módulo existe para manter.
    composta = (Decimal(1) + equivalente) ** 12
    assert abs(composta - Decimal("1.12")) < Decimal("0.000000001")


def test_juros_compostos():
    assert financeiro.juros_compostos(1000, Decimal("0.10"), 2) == Decimal("1210.00")


def test_juros_compostos_com_depositos():
    assert financeiro.juros_compostos(0, Decimal("0.10"), 3, deposito=100) == Decimal("331.00")


def test_valor_presente_desfaz_o_valor_futuro():
    futuro = financeiro.juros_compostos(1000, Decimal("0.05"), 10)
    assert financeiro.valor_presente(futuro, Decimal("0.05"), 10) == Decimal("1000.00")


def test_dinheiro_e_decimal_e_nao_float():
    """0.1 + 0.2 não dá 0.3 em binário, e numa tabela isso acumula."""
    total = financeiro.dinheiro("0.1") + financeiro.dinheiro("0.2")
    assert total == Decimal("0.30")
    assert 0.1 + 0.2 != 0.3, "é por isto que não se usa float com dinheiro"


def test_retirar_iva_nao_e_subtrair_a_percentagem():
    """100 + 23% = 123, mas 123 − 23% dá 94,71 — que não é o que se quer."""
    assert financeiro.acrescentar_percentagem(100, 23) == Decimal("123.00")
    assert financeiro.retirar_percentagem(123, 23) == Decimal("100.00")


def test_variacao_percentual():
    assert financeiro.variacao(100, 150) == Decimal("50.0000")
    assert financeiro.variacao(150, 100) == Decimal("-33.3333")


def test_nao_ha_variacao_a_partir_de_zero():
    with pytest.raises(financeiro.FinanceiroError):
        financeiro.variacao(0, 100)


@pytest.mark.parametrize("capital", [0, -1000])
def test_um_emprestimo_precisa_de_capital(capital):
    with pytest.raises(financeiro.FinanceiroError):
        financeiro.prestacao(capital, Decimal("0.01"), 12)


@pytest.mark.parametrize("periodos", [0, -5])
def test_um_emprestimo_precisa_de_prazo(periodos):
    with pytest.raises(financeiro.FinanceiroError):
        financeiro.prestacao(1000, Decimal("0.01"), periodos)


def test_valores_absurdos_sao_recusados():
    with pytest.raises(financeiro.FinanceiroError):
        financeiro.dinheiro("isto não é um número")


# =========================================== O PLUGIN E A PLATAFORMA


def test_nao_pede_nem_traz_permissoes():
    """Uma ferramenta que não toca em dados não devia pedir nada."""
    from core.plugin_api import ManifestoPlugin

    manifesto = ManifestoPlugin.ler_de_pasta(PASTA)
    assert manifesto.permissoes == frozenset()
    assert manifesto.permissoes_proprias == {}


def test_as_contas_nao_conhecem_a_interface():
    """O motor tem de servir a janela, um relatório ou um script."""
    for nome in ("calculo", "conversoes", "financeiro"):
        texto = (PASTA / f"{nome}.py").read_text(encoding="utf-8")
        assert "tkinter" not in texto
        assert "plugin_api" not in texto


def test_nao_importa_o_que_nao_pode():
    proibidos = {"banco_de_dados", "gui", "tarefas_servico", "core.plugin_manager"}
    for arquivo in PASTA.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                nomes = [no.module]
            for nome in nomes:
                assert nome not in proibidos, f"{arquivo.name} importa {nome}"


def test_os_idiomas_estao_completos():
    import json

    ficheiros = sorted(p.stem for p in (PASTA / "idiomas").glob("*.json"))
    assert ficheiros == ["en", "es", "pt"]
    chaves = [
        set(json.loads((PASTA / "idiomas" / f"{c}.json").read_text(encoding="utf-8")))
        for c in ficheiros
    ]
    assert chaves[0] == chaves[1] == chaves[2]


@pytest.fixture
def calculadora_instalada(gerenciador, pasta_plugins):
    import shutil

    shutil.copytree(PASTA, pasta_plugins / "calculadora")
    gerenciador.descobrir()
    return gerenciador


def test_carrega_na_plataforma(calculadora_instalada):
    from core import permissoes

    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    resultado = calculadora_instalada.carregar("calculadora")
    assert resultado.sucesso, resultado.detalhes


def test_funciona_para_quem_nao_tem_permissoes(calculadora_instalada):
    """Quem só vê tarefas continua a poder somar dois números."""
    from core import permissoes

    permissoes.definir_sessao("olga", "visualizador", persistir=False)
    assert calculadora_instalada.carregar("calculadora").sucesso


# ==================================================== A JANELA, A SÉRIO


@pytest.fixture
def painel(calculadora_instalada):
    """O painel real, construído como a aplicação o constrói."""
    tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")
    from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

    if not TKINTER_DISPONIVEL:
        pytest.skip("ambiente sem interface gráfica")

    from core import permissoes

    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    calculadora_instalada.carregar("calculadora")
    instancia = calculadora_instalada.obter("calculadora").instancia

    raiz = criar_janela_com_retentativa(tk.Tk)
    raiz.withdraw()
    tela = instancia._construir(raiz)
    yield tela
    raiz.destroy()


def test_as_quatro_modalidades_estao_la(painel):
    assert len(painel.abas.tabs()) == 4


def test_a_conta_simples_mostra_o_resultado(painel):
    painel.simples.entrada.insert(0, "2+3*4")
    assert painel.simples.calcular() == 14
    assert painel.simples.entrada.get() == "14"


def test_uma_conta_impossivel_vira_mensagem_e_nao_excecao(painel):
    """Um erro de quem escreve não pode rebentar a aba."""
    painel.simples.entrada.insert(0, "1/0")
    assert painel.simples.calcular() is None
    assert painel.simples.mensagem.cget("text")


def test_a_memoria_guarda_e_devolve(painel):
    painel.simples.entrada.insert(0, "6*7")
    painel.simples.guardar_memoria()
    assert painel.simples.memoria == 42

    painel.simples.limpar()
    painel.simples.usar_memoria()
    assert painel.simples.entrada.get() == "42"


def test_o_historico_da_cientifica_guarda_as_contas(painel):
    painel.cientifico.entrada.insert(0, "raiz(81)")
    painel.cientifico.calcular()
    assert painel.cientifico.historico == ["raiz(81) = 9"]


def test_o_modo_de_angulo_fica_guardado(painel, calculadora_instalada):
    """É a única coisa que este plugin persiste."""
    painel.cientifico.angulo_var.set("radianos")
    painel.cientifico.mudar_angulo()

    instancia = calculadora_instalada.obter("calculadora").instancia
    assert instancia.contexto.config()["angulo"] == "radianos"


def test_a_conversao_preenche_a_tabela(painel):
    painel.conversoes.familia_var.set("comprimento")
    painel.conversoes.mudar_familia()
    painel.conversoes.unidade_var.set("km")
    painel.conversoes.entrada.delete(0, "end")
    painel.conversoes.entrada.insert(0, "1")

    assert painel.conversoes.converter() is True
    linhas = {
        painel.conversoes.tabela.item(i, "values")[0]
        for i in painel.conversoes.tabela.get_children()
    }
    assert "m" in linhas and "milha" in linhas


def test_um_valor_que_nao_e_numero_avisa(painel):
    painel.conversoes.entrada.delete(0, "end")
    painel.conversoes.entrada.insert(0, "abc")
    assert painel.conversoes.converter() is False
    assert painel.conversoes.mensagem.cget("text")


def test_o_emprestimo_preenche_a_tabela_toda(painel):
    assert painel.financeiro.emprestimo() is True
    assert len(painel.financeiro.tabela.get_children()) == 360
    assert "599.55" in painel.financeiro.resumo.cget("text")


def test_o_emprestimo_com_dados_absurdos_avisa(painel):
    painel.financeiro.campos["capital"].delete(0, "end")
    painel.financeiro.campos["capital"].insert(0, "0")
    assert painel.financeiro.emprestimo() is False
    assert painel.financeiro.resumo.cget("text")


def test_a_poupanca_calcula_o_rendimento(painel):
    assert painel.financeiro.poupanca() is True
    assert painel.financeiro.resumo.cget("text")
