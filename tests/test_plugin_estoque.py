"""O primeiro módulo de negócio — e, através dele, a arquitetura.

Metade destes testes é sobre o Estoque. A outra metade é sobre a promessa que
o Estoque existe para verificar: que um módulo de negócio entra como plugin
sem que o núcleo saiba dele, sem tocar nos dados de ninguém, e sem precisar de
uma exceção na plataforma.
"""

import json
from pathlib import Path

import pytest

from core import permissoes
from core.paths import diretorio_dados_plugin
from core.plugin_api import ManifestoPlugin
from core.plugin_dados import ArmazenamentoPlugin

PASTA = Path(__file__).resolve().parent.parent / "plugins" / "available" / "estoque"


def carregar_dominio():
    """Importa o domínio do módulo sem o carregar como plugin."""
    import importlib.util
    import sys

    nome = "estoque_dominio_teste"
    especificacao = importlib.util.spec_from_file_location(nome, PASTA / "dominio.py")
    modulo = importlib.util.module_from_spec(especificacao)
    # Antes de executar: o @dataclass procura o módulo em sys.modules para
    # resolver as anotações, e sem isso rebenta a meio da definição.
    sys.modules[nome] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


dominio = carregar_dominio()


@pytest.fixture
def inventario(tmp_path):
    armazem = ArmazenamentoPlugin("estoque", tmp_path)
    inv = dominio.Inventario(armazem)
    inv.preparar()
    return inv


@pytest.fixture
def parafuso(inventario):
    return inventario.criar_item("PAR-01", "Parafuso M6", minimo=10)


# ============================================================= ITENS


def test_criar_um_item(inventario):
    item = inventario.criar_item("CX-01", "Caixa", unidade="cx", minimo=5)
    assert item.codigo == "CX-01"
    assert item.quantidade == 0, "nasce vazio: não se inventa stock"
    assert item.ativo


def test_o_codigo_e_unico(inventario, parafuso):
    with pytest.raises(dominio.CodigoDuplicadoError):
        inventario.criar_item("PAR-01", "Outro parafuso")


def test_o_codigo_repetido_e_recusado_sem_olhar_a_maiusculas(inventario, parafuso):
    with pytest.raises(dominio.CodigoDuplicadoError):
        inventario.criar_item("par-01", "Outro")


@pytest.mark.parametrize(
    "codigo,nome,minimo",
    [("", "Nome", 0), ("  ", "Nome", 0), ("COD", "", 0), ("COD", "Nome", -1)],
)
def test_dados_invalidos_sao_recusados(inventario, codigo, nome, minimo):
    with pytest.raises(ValueError):
        inventario.criar_item(codigo, nome, minimo=minimo)


def test_um_item_inativo_sai_da_lista_sem_perder_historico(inventario, parafuso):
    inventario.entrada(parafuso.id, 5)
    inventario.definir_ativo(parafuso.id, False)

    assert inventario.listar() == []
    assert len(inventario.listar(incluir_inativos=True)) == 1
    assert len(inventario.movimentos(parafuso.id)) == 1


# ======================================================== MOVIMENTOS


def test_a_quantidade_vem_dos_movimentos(inventario, parafuso):
    """O saldo é derivado, não escrito à mão.

    Um total editável sem deixar rasto é uma conta bancária sem extrato:
    quando os números não batem certo, não há por onde começar.
    """
    inventario.entrada(parafuso.id, 100)
    inventario.saida(parafuso.id, 30)
    inventario.entrada(parafuso.id, 5)

    assert inventario.exigir(parafuso.id).quantidade == 75


def test_nao_se_tira_mais_do_que_existe(inventario, parafuso):
    """Um saldo negativo não descreve nada no mundo real."""
    inventario.entrada(parafuso.id, 10)
    with pytest.raises(dominio.SaldoInsuficienteError) as erro:
        inventario.saida(parafuso.id, 11)

    assert erro.value.disponivel == 10
    assert erro.value.pedido == 11
    assert inventario.exigir(parafuso.id).quantidade == 10, "nada foi registado"


def test_tirar_exatamente_o_que_existe_e_permitido(inventario, parafuso):
    inventario.entrada(parafuso.id, 10)
    inventario.saida(parafuso.id, 10)
    assert inventario.exigir(parafuso.id).quantidade == 0


@pytest.mark.parametrize("quantidade", [0, -1])
def test_um_movimento_precisa_de_quantidade(inventario, parafuso, quantidade):
    with pytest.raises(ValueError):
        inventario.entrada(parafuso.id, quantidade)


def test_movimentar_um_item_inexistente(inventario):
    with pytest.raises(dominio.ItemNaoEncontradoError):
        inventario.entrada(999, 1)


def test_o_historico_guarda_quem_e_porque(inventario, parafuso):
    inventario.entrada(parafuso.id, 7, motivo="compra", quem="ana")
    movimento = inventario.movimentos(parafuso.id)[0]

    assert movimento.tipo == dominio.Tipo.ENTRADA
    assert movimento.motivo == "compra"
    assert movimento.quem == "ana"
    assert movimento.momento


def test_o_historico_vem_do_mais_recente(inventario, parafuso):
    for quantidade in (1, 2, 3):
        inventario.entrada(parafuso.id, quantidade)
    assert [m.quantidade for m in inventario.movimentos(parafuso.id)] == [3, 2, 1]


# ========================================================== EM FALTA


def test_abaixo_do_minimo_e_sinalizado(inventario, parafuso):
    inventario.entrada(parafuso.id, 9)  # mínimo é 10
    assert inventario.exigir(parafuso.id).abaixo_do_minimo
    assert [i.codigo for i in inventario.em_falta()] == ["PAR-01"]


def test_no_minimo_nao_esta_em_falta(inventario, parafuso):
    inventario.entrada(parafuso.id, 10)
    assert not inventario.exigir(parafuso.id).abaixo_do_minimo


def test_sem_minimo_definido_nunca_esta_em_falta(inventario):
    item = inventario.criar_item("X-1", "Sem mínimo", minimo=0)
    assert not inventario.exigir(item.id).abaixo_do_minimo
    assert inventario.em_falta() == []


# =============================================== O MÓDULO E A PLATAFORMA


def test_o_modulo_nao_pede_nada_ao_nucleo():
    """O Estoque não toca em tarefas, e o manifesto di-lo."""
    manifesto = ManifestoPlugin.ler_de_pasta(PASTA)
    assert manifesto.permissoes == frozenset()


def test_o_modulo_traz_as_permissoes_do_seu_dominio():
    manifesto = ManifestoPlugin.ler_de_pasta(PASTA)
    assert set(manifesto.permissoes_proprias) == {"estoque.ler", "estoque.escrever"}
    assert "visualizador" in manifesto.permissoes_proprias["estoque.ler"]
    assert "visualizador" not in manifesto.permissoes_proprias["estoque.escrever"]


def test_o_nucleo_nao_sabe_que_o_estoque_existe():
    """A prova de que é um módulo e não uma funcionalidade disfarçada.

    Olha para o **código**, não para o texto: o núcleo usa "estoque" como
    exemplo em documentação (``ex.: estoque.ler``), e isso é o contrário de um
    problema — mostra que o contrato foi pensado para módulos que ainda não
    existem. O que não pode haver é um import, um nome ou uma string em
    execução a referi-lo.
    """
    import ast

    raiz = Path(__file__).resolve().parent.parent / "src"
    for arquivo in raiz.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {
            no.body[0].value
            for no in ast.walk(arvore)
            if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and no.body
            and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
            and isinstance(no.body[0].value.value, str)
        }
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                if no not in docstrings:
                    assert "estoque" not in no.value.lower(), (
                        f"{arquivo.name} refere o módulo em código"
                    )
            elif isinstance(no, ast.Name):
                assert "estoque" not in no.id.lower(), f"{arquivo.name}: {no.id}"
            elif isinstance(no, (ast.Import, ast.ImportFrom)):
                origem = getattr(no, "module", "") or ""
                nomes = [a.name for a in no.names] + [origem]
                assert not any("estoque" in (n or "").lower() for n in nomes), (
                    f"{arquivo.name} importa o módulo"
                )


def test_o_modulo_nao_importa_o_que_nao_pode():
    import ast

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


def test_o_dominio_nao_conhece_a_interface():
    """As regras de negócio têm de servir a janela, um relatório ou uma API."""
    texto = (PASTA / "dominio.py").read_text(encoding="utf-8")
    assert "tkinter" not in texto
    assert "plugin_api" not in texto


def test_os_dados_do_modulo_ficam_no_ficheiro_dele(tmp_path):
    armazem = ArmazenamentoPlugin("estoque", tmp_path)
    inv = dominio.Inventario(armazem)
    inv.preparar()
    inv.criar_item("A-1", "Item")

    assert armazem.existe
    assert armazem.caminho.parent == tmp_path


def test_o_modulo_nao_alcanca_as_tarefas(tmp_path):
    import sqlite3

    import banco_de_dados

    banco_de_dados.criar_tabela()
    banco_de_dados.adicionar_tarefa("Tarefa da aplicação", "2030-01-01")

    armazem = ArmazenamentoPlugin("estoque", tmp_path)
    inv = dominio.Inventario(armazem)
    inv.preparar()
    with pytest.raises(sqlite3.OperationalError, match="tarefas"):
        armazem.consultar("SELECT * FROM tarefas")


def test_os_idiomas_do_modulo_estao_completos():
    """Um módulo traz os seus textos, nos mesmos idiomas que a aplicação."""
    ficheiros = sorted(p.stem for p in (PASTA / "idiomas").glob("*.json"))
    assert ficheiros == ["en", "es", "pt"]

    chaves = [
        set(json.loads((PASTA / "idiomas" / f"{c}.json").read_text(encoding="utf-8")))
        for c in ficheiros
    ]
    assert chaves[0] == chaves[1] == chaves[2]


# ================================================ CICLO DE VIDA NA PLATAFORMA


@pytest.fixture
def estoque_instalado(gerenciador, pasta_plugins):
    """Instala o módulo real na área de plugins dos testes."""
    import shutil

    shutil.copytree(PASTA, pasta_plugins / "estoque")
    gerenciador.descobrir()
    return gerenciador


def test_o_modulo_carrega_na_plataforma(estoque_instalado):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    resultado = estoque_instalado.carregar("estoque")
    assert resultado.sucesso, resultado.detalhes


def test_carregar_faz_as_permissoes_do_modulo_existirem(estoque_instalado):
    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    assert permissoes.pode("estoque.ler") is False, "antes de carregar, não existe"

    estoque_instalado.carregar("estoque")
    assert permissoes.pode("estoque.ler") is True
    assert permissoes.pode("estoque.escrever") is True


def test_descarregar_leva_as_permissoes_com_ele(estoque_instalado):
    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    estoque_instalado.carregar("estoque")
    estoque_instalado.descarregar("estoque")

    assert permissoes.pode("estoque.ler") is False


def test_um_papel_de_leitura_nao_escreve(estoque_instalado):
    estoque_instalado.carregar("estoque")
    permissoes.definir_sessao("olga", "visualizador", persistir=False)

    assert permissoes.pode("estoque.ler") is True
    assert permissoes.pode("estoque.escrever") is False


def test_o_servico_do_modulo_aplica_as_suas_permissoes(estoque_instalado):
    from core.permissoes import PermissaoNegadaError

    estoque_instalado.carregar("estoque")
    instancia = estoque_instalado.obter("estoque").instancia
    permissoes.definir_sessao("olga", "visualizador", persistir=False)

    assert instancia.servico.listar() == []
    with pytest.raises(PermissaoNegadaError):
        instancia.servico.criar_item("A-1", "Item")


def test_o_modulo_regista_quem_movimentou(estoque_instalado):
    estoque_instalado.carregar("estoque")
    instancia = estoque_instalado.obter("estoque").instancia
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    item = instancia.servico.criar_item("A-1", "Item")
    instancia.servico.entrada(item.id, 5)

    assert instancia.servico.movimentos(item.id)[0].quem == "ana"


def test_o_modulo_publica_os_seus_eventos(estoque_instalado):
    from core import eventos

    estoque_instalado.carregar("estoque")
    instancia = estoque_instalado.obter("estoque").instancia
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    recebidos = []
    eventos.subscrever("estoque.*", recebidos.append)

    item = instancia.servico.criar_item("A-1", "Item", minimo=10)
    instancia.servico.entrada(item.id, 3)

    nomes = [e.nome for e in recebidos]
    assert "estoque.item_criado" in nomes
    assert "estoque.entrada" in nomes
    # Abaixo do mínimo: quem quiser encomendar não tem de recalcular nada.
    assert "estoque.em_falta" in nomes


def test_remover_o_modulo_leva_os_dados_dele(estoque_instalado):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    estoque_instalado.carregar("estoque")
    instancia = estoque_instalado.obter("estoque").instancia
    instancia.servico.criar_item("A-1", "Item")

    armazem = ArmazenamentoPlugin("estoque", diretorio_dados_plugin("estoque"))
    assert armazem.existe

    assert estoque_instalado.remover("estoque", remover_dados=True).sucesso
    assert not armazem.existe


def test_remover_o_modulo_nao_toca_nas_tarefas(estoque_instalado):
    import banco_de_dados

    banco_de_dados.criar_tabela()
    banco_de_dados.adicionar_tarefa("Continua aqui", "2030-01-01")

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    estoque_instalado.carregar("estoque")
    estoque_instalado.remover("estoque", remover_dados=True)

    assert [t[1] for t in banco_de_dados.buscar_tarefas()] == ["Continua aqui"]


def test_nem_o_administrador_tem_o_que_nao_existe(estoque_instalado):
    """O atalho de "administra tudo" não pode inventar permissões.

    Dizer que sim a uma permissão não registada esconderia um erro de escrita
    de quem administra, e mostrá-lo-ia só a quem não administra — o pior sítio
    para um defeito aparecer.
    """
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    assert permissoes.pode("estoque.escrever") is False, "o módulo ainda não carregou"
    assert permissoes.pode("estoque.inventada") is False

    estoque_instalado.carregar("estoque")
    assert permissoes.pode("estoque.escrever") is True
    assert permissoes.pode("estoque.inventada") is False, "erro de escrita continua não"

    estoque_instalado.descarregar("estoque")
    assert permissoes.pode("estoque.escrever") is False, "saiu com o módulo"


def test_o_administrador_tem_tudo_o_que_o_modulo_registou(estoque_instalado):
    """Registada é registada: quem administra não precisa de constar da lista."""
    estoque_instalado.carregar("estoque")
    manifesto = ManifestoPlugin.ler_de_pasta(PASTA)
    assert "administrador" in manifesto.permissoes_proprias["estoque.escrever"]

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert all(permissoes.pode(nome) for nome in manifesto.permissoes_proprias)


# ===================================== o módulo como prova da multiempresa
#
# O Estoque existe para verificar a arquitetura, e esta é a verificação mais
# exigente até agora: a plataforma **não pode** isolar os dados de um módulo
# sozinha, porque não conhece as tabelas dele. O que ela dá é a resposta a
# "de que empresa é esta sessão"; quem é dono do esquema decide o resto.


@pytest.fixture
def inventario_de_empresa(tmp_path):
    """Um inventário cuja empresa se pode trocar de teste para teste."""
    dominio = carregar_dominio()
    atual = {"empresa": None}
    dados = ArmazenamentoPlugin("estoque", tmp_path)
    inventario = dominio.Inventario(dados, lambda: atual["empresa"])
    inventario.preparar()
    return inventario, atual, dominio


def test_o_esquema_chega_a_versao_que_tem_a_empresa(inventario_de_empresa):
    inventario, _, _ = inventario_de_empresa
    assert inventario._dados.versao() == 2


def test_cada_empresa_ve_so_os_seus_itens(inventario_de_empresa):
    inventario, atual, _ = inventario_de_empresa

    atual["empresa"] = 1
    inventario.criar_item("CX-01", "Caixa da Acme")
    atual["empresa"] = 2
    inventario.criar_item("PAR-01", "Parafuso da Rival")

    assert [i.nome for i in inventario.listar()] == ["Parafuso da Rival"]
    atual["empresa"] = 1
    assert [i.nome for i in inventario.listar()] == ["Caixa da Acme"]


def test_o_mesmo_codigo_em_empresas_diferentes_deixa_de_ser_conflito(inventario_de_empresa):
    """Os códigos vêm dos fornecedores; duas empresas repetem-nos naturalmente.

    É por isto que a chave única teve de ser reconstruída — e é por isso que
    o contrato precisou de saber substituir uma tabela.
    """
    inventario, atual, _ = inventario_de_empresa

    atual["empresa"] = 1
    inventario.criar_item("CX-01", "Caixa da Acme")
    atual["empresa"] = 2
    criado = inventario.criar_item("CX-01", "Caixa da Rival")
    assert criado.codigo == "CX-01"


def test_dentro_da_mesma_empresa_o_codigo_continua_unico(inventario_de_empresa):
    inventario, atual, dominio = inventario_de_empresa

    atual["empresa"] = 1
    inventario.criar_item("CX-01", "Caixa")
    with pytest.raises(dominio.CodigoDuplicadoError):
        inventario.criar_item("cx-01", "Outra caixa")


def test_um_id_de_outra_empresa_nao_abre(inventario_de_empresa):
    """A forma clássica de um isolamento ter buracos: chegar pelo id.

    Se ``obter`` não tivesse âmbito, um item que não aparece na lista abria
    na mesma — e ``exigir`` (que guarda a escrita) passa por ``obter``.
    """
    inventario, atual, dominio = inventario_de_empresa

    atual["empresa"] = 1
    da_acme = inventario.criar_item("CX-01", "Caixa da Acme")

    atual["empresa"] = 2
    assert inventario.obter(da_acme.id) is None
    with pytest.raises(dominio.ItemNaoEncontradoError):
        inventario.exigir(da_acme.id)


def test_nao_se_pode_mexer_no_stock_de_outra_empresa(inventario_de_empresa):
    """A escrita é guardada pela mesma porta que a leitura."""
    inventario, atual, dominio = inventario_de_empresa

    atual["empresa"] = 1
    da_acme = inventario.criar_item("CX-01", "Caixa da Acme")
    inventario.entrada(da_acme.id, 10)

    atual["empresa"] = 2
    with pytest.raises(dominio.ItemNaoEncontradoError):
        inventario.entrada(da_acme.id, 5)
    with pytest.raises(dominio.ItemNaoEncontradoError):
        inventario.definir_ativo(da_acme.id, False)


def test_o_historico_nao_mostra_movimentos_de_outra_empresa(inventario_de_empresa):
    """Senão dava a ver códigos e quantidades pela porta das traseiras."""
    inventario, atual, _ = inventario_de_empresa

    atual["empresa"] = 1
    da_acme = inventario.criar_item("CX-01", "Caixa da Acme")
    inventario.entrada(da_acme.id, 10)

    atual["empresa"] = 2
    da_rival = inventario.criar_item("PAR-01", "Parafuso")
    inventario.entrada(da_rival.id, 3)

    vistos = inventario.movimentos()
    assert [m.item_id for m in vistos] == [da_rival.id]


# ------------------------------------ o que a migração não podia ter partido


def test_o_que_ja_estava_la_continua_visivel_a_todos(tmp_path):
    """A regra das tarefas, aplicada aos dados de um módulo.

    Um item criado antes de haver estrutura não pertence a empresa nenhuma.
    Escondê-lo faria desaparecer o inventário inteiro no dia em que a segunda
    empresa fosse criada — e o dado continuaria lá, sem ninguém acreditar.
    """
    dominio = carregar_dominio()
    dados = ArmazenamentoPlugin("estoque", tmp_path)

    # Uma instalação anterior: só a v1, e um item sem empresa.
    antes = dominio.Inventario(dados)
    antes.preparar()
    antes.criar_item("ANTIGO-01", "Comprado antes da estrutura")

    # Agora com empresas.
    atual = {"empresa": 7}
    depois = dominio.Inventario(dados, lambda: atual["empresa"])
    assert [i.codigo for i in depois.listar()] == ["ANTIGO-01"]

    atual["empresa"] = 9
    assert [i.codigo for i in depois.listar()] == ["ANTIGO-01"]


def test_a_migracao_nao_perde_itens_nem_movimentos(tmp_path):
    dominio = carregar_dominio()
    dados = ArmazenamentoPlugin("estoque", tmp_path)

    # O esquema antigo, e uma linha escrita como ele a escrevia: sem coluna
    # de empresa, porque nessa versão ela não existia. Passar pelo
    # ``criar_item`` de hoje seria testar a migração com dados que a versão
    # antiga nunca teria produzido.
    for versao, *instrucoes in dominio.MIGRACOES:
        dados.migrar(versao, *instrucoes)
    item_id = dados.executar(
        "INSERT INTO itens (codigo, nome, unidade, minimo, ativo, criado_em) "
        "VALUES ('CX-01', 'Caixa', 'un', 5, 1, '2026-01-01T00:00:00')"
    )
    dados.executar(
        "INSERT INTO movimentos (item_id, tipo, quantidade, motivo, quem, momento) "
        "VALUES (?, 'entrada', 12, 'compra', 'ana', '2026-01-02T00:00:00')",
        (item_id,),
    )

    # A reconstrução.
    for versao, *instrucoes in dominio.RECONSTRUCOES:
        assert dados.migrar(versao, *instrucoes, reconstroi_tabelas=True)

    novo = dominio.Inventario(dados)
    reposto = novo.exigir(item_id)
    assert (reposto.codigo, reposto.nome, reposto.minimo) == ("CX-01", "Caixa", 5)
    assert reposto.quantidade == 12, "o saldo vem dos movimentos, que têm de estar lá"
    assert [m.motivo for m in novo.movimentos()] == ["compra"]


def test_sem_empresa_o_modulo_comporta_se_como_sempre(tmp_path):
    """Uma instalação com uma empresa só não nota diferença nenhuma."""
    dominio = carregar_dominio()
    inventario = dominio.Inventario(ArmazenamentoPlugin("estoque", tmp_path))
    inventario.preparar()

    inventario.criar_item("CX-01", "Caixa")
    inventario.criar_item("PAR-01", "Parafuso")
    assert len(inventario.listar()) == 2
