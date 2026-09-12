"""Automação por regras — e sobretudo o que a impede de se comer a si própria.

A parte difícil de um motor de regras não é executar ações. É não entrar em
ciclo. "Quando uma tarefa é criada, cria uma tarefa" é fácil de escrever sem
dar por isso, e sem defesa bloqueia a aplicação no primeiro disparo, com o
banco a encher. Metade destes testes é sobre isso.

A outra metade é sobre a fronteira: o motor não conhece tarefas. Se souber,
deixou de ser um motor.
"""

import pytest

import database as db
from core import auditoria, eventos, permissoes
from workflow import acoes, repositorio
from workflow.modelo import Acao, Condicao, Operador, Regra, RegraInvalidaError
from workflow.motor import PROFUNDIDADE_MAXIMA, Motor


@pytest.fixture(autouse=True)
def registo_limpo():
    """O catálogo de ações é global: cada teste começa com ele vazio."""
    acoes.limpar()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    yield
    acoes.limpar()


@pytest.fixture
def contador():
    """Uma ação que só conta quantas vezes foi chamada."""
    chamadas = []

    def acao(dados, argumentos):
        chamadas.append((dict(dados), dict(argumentos)))

    acoes.registar("contar", acao)
    return chamadas


@pytest.fixture
def motor():
    m = Motor()
    m.ativar()
    yield m
    m.desativar()


# ================================================================ CONDIÇÕES


@pytest.mark.parametrize(
    "operador,valor,dados,esperado",
    [
        (Operador.IGUAL, 5, {"n": 5}, True),
        (Operador.IGUAL, "5", {"n": 5}, True),
        (Operador.IGUAL, 5, {"n": 6}, False),
        (Operador.DIFERENTE, 5, {"n": 6}, True),
        (Operador.MAIOR, 10, {"n": 11}, True),
        (Operador.MAIOR, 10, {"n": 10}, False),
        (Operador.MENOR, 10, {"n": 9}, True),
        (Operador.MAIOR_OU_IGUAL, 10, {"n": 10}, True),
        (Operador.MENOR_OU_IGUAL, 10, {"n": 10}, True),
        (Operador.CONTEM, "urgente", {"n": "Tarefa URGENTE hoje"}, True),
        (Operador.COMECA_COM, "PAR", {"n": "par-01"}, True),
        (Operador.EXISTE, None, {"n": 1}, True),
        (Operador.EXISTE, None, {"n": ""}, False),
        (Operador.VAZIO, None, {}, True),
        (Operador.VAZIO, None, {"n": None}, True),
    ],
)
def test_condicoes(operador, valor, dados, esperado):
    assert Condicao("n", operador, valor).verifica(dados) is esperado


def test_um_campo_em_falta_responde_nao_a_tudo():
    """Inventar uma resposta esconderia um engano de quem escreveu a regra."""
    for operador in (Operador.IGUAL, Operador.MAIOR, Operador.CONTEM):
        assert Condicao("inexistente", operador, 1).verifica({"outro": 1}) is False


def test_texto_e_numero_comparam_se():
    """Os dados vêm de código; os valores da regra vêm de um formulário.

    Exigir que os tipos batam certo faria regras corretas nunca dispararem,
    sem dizer porquê.
    """
    assert Condicao("saldo", Operador.MENOR, "10").verifica({"saldo": 5})
    assert Condicao("saldo", Operador.MENOR, 10).verifica({"saldo": "5"})


def test_comparar_ordem_com_texto_nao_rebenta():
    assert Condicao("n", Operador.MAIOR, 1).verifica({"n": "abc"}) is False


def test_todas_as_condicoes_tem_de_se_verificar():
    regra = Regra(
        1, "r", "x",
        condicoes=(Condicao("a", Operador.IGUAL, 1), Condicao("b", Operador.IGUAL, 2)),
    )
    assert regra.aplica_se({"a": 1, "b": 2})
    assert not regra.aplica_se({"a": 1, "b": 99})


def test_sem_condicoes_aplica_se_sempre():
    assert Regra(1, "r", "x").aplica_se({})


# ================================================================== REGRAS


def test_criar_e_ler_uma_regra():
    regra = repositorio.criar(
        "Avisar",
        "tarefa.criada",
        condicoes=[Condicao("id", Operador.EXISTE)],
        acoes=[Acao("registar", {"texto": "olá"})],
        criada_por="ana",
    )
    lida = repositorio.obter(regra.id)
    assert lida.nome == "Avisar"
    assert lida.evento == "tarefa.criada"
    assert lida.condicoes[0].campo == "id"
    assert lida.acoes[0].argumentos == {"texto": "olá"}


@pytest.mark.parametrize("nome", ["", "   "])
def test_uma_regra_precisa_de_nome(nome):
    with pytest.raises(RegraInvalidaError):
        repositorio.criar(nome, "tarefa.criada", acoes=[Acao("registar")])


def test_uma_regra_precisa_de_acao():
    """Uma regra que não faz nada é sempre um engano por acabar."""
    with pytest.raises(RegraInvalidaError, match="ação"):
        repositorio.criar("Vazia", "tarefa.criada", acoes=[])


def test_uma_regra_nao_pode_reagir_a_tudo():
    """Reagir a `*` inclui reagir aos eventos que a própria regra provoca."""
    with pytest.raises(RegraInvalidaError, match="todos os eventos"):
        repositorio.criar("Tudo", "*", acoes=[Acao("registar")])


def test_uma_regra_desligada_nao_e_listada_como_ativa():
    regra = repositorio.criar("R", "tarefa.criada", acoes=[Acao("registar")])
    repositorio.definir_ativa(regra.id, False)

    assert repositorio.listar(apenas_ativas=True) == []
    assert len(repositorio.listar()) == 1


def test_uma_regra_ilegivel_e_ignorada_e_nao_derruba_nada():
    """Um ficheiro editado à mão não pode impedir a aplicação de arrancar."""
    repositorio.criar("Boa", "tarefa.criada", acoes=[Acao("registar")])
    with db.conectar() as conexao:
        conexao.execute(
            "INSERT INTO regras (nome, evento, condicoes, acoes, ativa, criada_em)"
            " VALUES ('Partida', 'tarefa.criada', 'isto não é json', '[]', 1, '2026-01-01')"
        )

    listadas = repositorio.listar()
    assert [r.nome for r in listadas] == ["Boa"]


# ================================================================== AÇÕES


def test_uma_acao_desconhecida_e_um_erro_e_nao_silencio(motor, contador):
    """Um plugin removido deixa regras a apontar para o vazio."""
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("inexistente")])
    execucoes = motor.processar("tarefa.criada", {"id": 1})

    assert len(execucoes) == 1
    assert not execucoes[0].sucesso
    assert "inexistente" in execucoes[0].falhas[0]


def test_uma_acao_de_um_plugin_sai_com_ele():
    acoes.registar("estoque.encomendar", lambda d, a: None, dono="estoque")
    assert acoes.existe("estoque.encomendar")

    acoes.esquecer_por_dono("estoque")
    assert not acoes.existe("estoque.encomendar")


def test_registar_a_mesma_acao_substitui():
    """Um plugin recarregado não pode obrigar a reiniciar a aplicação."""
    acoes.registar("x", lambda d, a: 1)
    acoes.registar("x", lambda d, a: 2)
    assert acoes.obter("x").funcao({}, {}) == 2


# ================================================================== MOTOR


def test_uma_regra_dispara_com_o_evento(motor, contador):
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar", {"q": 1})])
    eventos.publicar("tarefa.criada", origem="teste", id=7)

    assert len(contador) == 1
    dados, argumentos = contador[0]
    assert dados["id"] == 7
    assert argumentos == {"q": 1}


def test_um_padrao_apanha_a_familia(motor, contador):
    repositorio.criar("R", "estoque.*", acoes=[Acao("contar")])
    eventos.publicar("estoque.entrada", origem="teste", id=1)
    eventos.publicar("estoque.saida", origem="teste", id=1)
    eventos.publicar("tarefa.criada", origem="teste", id=1)

    assert len(contador) == 2


def test_as_condicoes_filtram(motor, contador):
    repositorio.criar(
        "Só em falta",
        "estoque.saida",
        condicoes=[Condicao("saldo", Operador.MENOR, 10)],
        acoes=[Acao("contar")],
    )
    eventos.publicar("estoque.saida", origem="teste", saldo=50)
    assert contador == []

    eventos.publicar("estoque.saida", origem="teste", saldo=3)
    assert len(contador) == 1


def test_uma_regra_desligada_nao_corre(motor, contador):
    regra = repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar")])
    repositorio.definir_ativa(regra.id, False)
    eventos.publicar("tarefa.criada", origem="teste", id=1)

    assert contador == []


def test_uma_acao_que_falha_nao_impede_as_outras(motor, contador):
    """Uma automação partida não pode impedir alguém de criar uma tarefa."""
    def explode(dados, argumentos):
        raise RuntimeError("rebentei")

    acoes.registar("explodir", explode)
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("explodir"), Acao("contar")])

    execucoes = motor.processar("tarefa.criada", {"id": 1})
    assert len(contador) == 1, "a segunda ação correu na mesma"
    assert execucoes[0].falhas


def test_uma_acao_que_falha_nao_impede_quem_publicou(motor):
    def explode(dados, argumentos):
        raise RuntimeError("rebentei")

    acoes.registar("explodir", explode)
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("explodir")])

    tarefa = db.adicionar_tarefa("Tem de existir na mesma", "2030-01-01")
    assert db.obter_tarefa(tarefa) is not None


# ============================================= O CICLO, QUE É O QUE INTERESSA


def test_uma_regra_que_se_alimenta_a_si_propria_para(motor):
    """"Quando uma tarefa é criada, cria uma tarefa" — o ciclo clássico.

    Sem defesa, isto bloqueia a aplicação para sempre no primeiro disparo, com
    o banco a encher. Tem de parar sozinho, e depressa.
    """
    criadas = []

    def criar_outra(dados, argumentos):
        criadas.append(dados)
        eventos.publicar("tarefa.criada", origem="acao", id=len(criadas))

    acoes.registar("criar_outra", criar_outra)
    repositorio.criar("Ciclo", "tarefa.criada", acoes=[Acao("criar_outra")])

    eventos.publicar("tarefa.criada", origem="teste", id=0)

    assert 0 < len(criadas) <= PROFUNDIDADE_MAXIMA, (
        f"a cadeia devia parar em {PROFUNDIDADE_MAXIMA} níveis, correu {len(criadas)}"
    )


def test_um_ciclo_indireto_tambem_para(motor):
    """A → B → A é o ciclo que passa despercebido a quem escreve as regras."""
    passos = []

    def publicar_b(dados, argumentos):
        passos.append("a")
        eventos.publicar("evento.b", origem="acao")

    def publicar_a(dados, argumentos):
        passos.append("b")
        eventos.publicar("evento.a", origem="acao")

    acoes.registar("publicar_b", publicar_b)
    acoes.registar("publicar_a", publicar_a)
    repositorio.criar("A", "evento.a", acoes=[Acao("publicar_b")])
    repositorio.criar("B", "evento.b", acoes=[Acao("publicar_a")])

    eventos.publicar("evento.a", origem="teste")
    assert len(passos) <= PROFUNDIDADE_MAXIMA * 2


def test_a_mesma_regra_nao_corre_duas_vezes_na_mesma_cadeia(motor):
    corridas = []

    def encadear(dados, argumentos):
        corridas.append(1)
        eventos.publicar("evento.b", origem="acao")

    def voltar(dados, argumentos):
        eventos.publicar("evento.a", origem="acao")

    acoes.registar("encadear", encadear)
    acoes.registar("voltar", voltar)
    repositorio.criar("A", "evento.a", acoes=[Acao("encadear")])
    repositorio.criar("B", "evento.b", acoes=[Acao("voltar")])

    eventos.publicar("evento.a", origem="teste")
    assert len(corridas) == 1, "a regra A não se repete na mesma reação em cadeia"


def test_uma_cadeia_longa_de_regras_diferentes_e_cortada(motor):
    """O limite de profundidade guarda o que a outra defesa não apanha.

    Uma regra que se repete é travada pela cadeia; uma sequência de regras
    **todas diferentes** — A dispara B, que dispara C… — não se repete nunca e
    mesmo assim não pode descer sem fim.
    """
    avisos = []
    eventos.subscrever(eventos.WORKFLOW_LIMITE, avisos.append)
    corridas = []

    def encadear(dados, argumentos):
        seguinte = argumentos["seguinte"]
        corridas.append(seguinte)
        eventos.publicar(f"cadeia.{seguinte}", origem="acao")

    acoes.registar("encadear", encadear)
    # Mais regras do que o limite permite descer, todas distintas.
    for passo in range(PROFUNDIDADE_MAXIMA + 3):
        repositorio.criar(
            f"Passo {passo}",
            f"cadeia.{passo}",
            acoes=[Acao("encadear", {"seguinte": passo + 1})],
        )

    eventos.publicar("cadeia.0", origem="teste")

    assert len(corridas) == PROFUNDIDADE_MAXIMA, (
        f"a cadeia devia parar em {PROFUNDIDADE_MAXIMA} níveis, correu {len(corridas)}"
    )
    assert avisos, "parar em silêncio seria pior do que o ciclo"


def test_os_eventos_do_proprio_motor_nao_disparam_regras(motor, contador):
    """Seriam a forma mais curta de um ciclo, e não descrevem negócio nenhum."""
    repositorio.criar("R", "workflow.*", acoes=[Acao("contar")])
    eventos.publicar(eventos.WORKFLOW_EXECUTADA, origem="teste", id="x")

    assert contador == []


# ================================================================ REGISTO


def test_a_execucao_fica_no_historico(motor, contador):
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar")])
    eventos.publicar("tarefa.criada", origem="teste", id=1)

    historico = motor.historico()
    assert historico[0].regra == "R"
    assert historico[0].acoes_corridas == 1
    assert historico[0].sucesso


def test_uma_automacao_que_correu_fica_na_auditoria(motor, contador):
    """Senão haveria alterações no sistema sem autor aparente."""
    auditoria.ativar()
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar")])
    eventos.publicar("tarefa.criada", origem="teste", id=1)

    registos = [r for r in auditoria.consultar() if r.evento == eventos.WORKFLOW_EXECUTADA]
    assert len(registos) == 1
    assert registos[0].alvo == "R"


def test_ativar_duas_vezes_nao_duplica(contador):
    m = Motor()
    m.ativar()
    m.ativar()
    try:
        repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar")])
        eventos.publicar("tarefa.criada", origem="teste", id=1)
        assert len(contador) == 1
    finally:
        m.desativar()


def test_desativar_para_mesmo(contador):
    m = Motor()
    m.ativar()
    m.desativar()
    repositorio.criar("R", "tarefa.criada", acoes=[Acao("contar")])
    eventos.publicar("tarefa.criada", origem="teste", id=1)

    assert contador == []


# ======================================================= AS AÇÕES INCLUÍDAS


def test_preencher_troca_os_campos_do_evento():
    import automacoes

    assert automacoes.preencher("Comprar {nome}", {"nome": "Parafuso"}) == "Comprar Parafuso"


def test_um_campo_que_falta_fica_a_vista():
    """Ver o que faltou é melhor do que rebentar ou apagar em silêncio."""
    import automacoes

    assert automacoes.preencher("Olá {ninguem}", {}) == "Olá {ninguem}"


@pytest.mark.parametrize(
    "modelo", ["{0.__class__}", "{a.b}", "{__import__}", "{a[0]}"]
)
def test_o_modelo_nao_navega_dentro_dos_objetos(modelo):
    """`str.format` faria isto; escrito à mão, não faz.

    O modelo vem de uma regra guardada no banco — texto que alguém pode
    alterar. Texto alterável não deve virar código a correr.
    """
    import automacoes

    assert automacoes.preencher(modelo, {"a": object()}) == modelo


def test_a_acao_de_criar_tarefa_cria_mesmo(motor):
    import automacoes

    automacoes.registar_incluidas()
    repositorio.criar(
        "Comprar o que falta",
        "estoque.em_falta",
        acoes=[Acao("tarefa.criar", {"descricao": "Encomendar item {id}"})],
    )
    eventos.publicar("estoque.em_falta", origem="teste", id=42, saldo=2)

    assert "Encomendar item 42" in [t[1] for t in db.buscar_tarefas()]


def test_a_acao_respeita_as_permissoes_de_quem_esta_em_sessao(motor):
    """Uma regra não é a forma de fazer por automação o que não se pode à mão."""
    import automacoes

    automacoes.registar_incluidas()
    repositorio.criar(
        "R", "estoque.em_falta", acoes=[Acao("tarefa.criar", {"descricao": "X"})]
    )
    permissoes.definir_sessao("olga", "visualizador", persistir=False)

    execucoes = motor.processar("estoque.em_falta", {"id": 1})
    assert not execucoes[0].sucesso
    assert db.buscar_tarefas() == []
