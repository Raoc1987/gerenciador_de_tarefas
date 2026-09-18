"""Testes das políticas por atributo.

O RBAC responde a "podes fazer isto?"; uma política responde a "podes fazer
isto **a isto**?". O que estes testes protegem não é o mecanismo em si — é a
propriedade que o torna seguro: **uma política só pode tirar**. Se algum dia
puder conceder, um plugin passa a poder abrir portas, e o contrato inteiro
deixa de valer.
"""

import pytest

from core import funcionalidades, permissoes
from core.permissoes import (
    Pedido,
    Permissao,
    PermissaoNegadaError,
    PoliticaNegouError,
)


def recusar_sempre(_sessao, _pedido):
    return "motivo_de_teste"


def deixar_passar(_sessao, _pedido):
    return None


@pytest.fixture
def pedido():
    return Pedido("concluir", "tarefa", {"dono": "ana"})


# ================================================================ mecanismo


def test_sem_pedido_a_resposta_e_a_do_papel():
    """O caminho antigo não muda: 42 pontos de chamada dependem disso."""
    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    permissoes.registar_politica("t.tudo", {"concluir"}, {"tarefa"}, recusar_sempre)

    assert permissoes.pode(Permissao.TAREFAS_ESCREVER) is True
    assert permissoes.pode(Permissao.SISTEMA_ADMIN) is False


def test_uma_politica_recusa_o_que_o_papel_permitia(pedido):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is True

    permissoes.registar_politica("t.nao", {"concluir"}, {"tarefa"}, recusar_sempre)
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False


def test_uma_politica_nunca_concede_o_que_o_papel_negava(pedido):
    """A propriedade que torna seguro um plugin registar políticas.

    O avaliador aqui deixa passar tudo. Se as políticas fossem consultadas
    antes do papel — ou pudessem devolver "sim" — um visualizador passava a
    escrever. Nenhuma ordem de avaliação pode permitir isto.
    """
    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    permissoes.registar_politica("t.sim", {"concluir"}, {"tarefa"}, deixar_passar)

    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False
    with pytest.raises(PermissaoNegadaError):
        permissoes.exigir(Permissao.TAREFAS_ESCREVER, pedido)


def test_o_papel_decide_primeiro_e_a_politica_nem_e_avaliada(pedido):
    """Se o papel já disse não, não se paga o custo de avaliar nada."""
    corridas = []

    def registar_passagem(_s, _p):
        corridas.append(1)
        return None

    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    permissoes.registar_politica("t.conta", {"concluir"}, {"tarefa"}, registar_passagem)

    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False
    assert corridas == [], "a política foi avaliada depois de o papel recusar"


def test_uma_politica_so_olha_para_as_suas_acoes_e_tipos():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica("t.so_remover", {"remover"}, {"tarefa"}, recusar_sempre)

    assert not permissoes.pode(Permissao.TAREFAS_ESCREVER, Pedido("remover", "tarefa"))
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, Pedido("concluir", "tarefa"))
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, Pedido("remover", "item"))


def test_uma_politica_que_rebenta_recusa(pedido):
    """Rebentar fechada.

    Uma regra de acesso partida não pode passar por regra bem sucedida: seria
    desligar a segurança sem ninguém dar por isso.
    """
    def explode(_s, _p):
        raise RuntimeError("erro de quem escreveu a política")

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica("t.parte", {"concluir"}, {"tarefa"}, explode)

    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False
    with pytest.raises(PoliticaNegouError) as erro:
        permissoes.exigir(Permissao.TAREFAS_ESCREVER, pedido)
    assert erro.value.chave_mensagem == "politica_falhou"


def test_a_recusa_diz_qual_a_politica_e_porque(pedido):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica("t.motivo", {"concluir"}, {"tarefa"}, recusar_sempre)

    negada = permissoes.recusa(pedido)
    assert negada.politica == "t.motivo"
    assert negada.motivo == "motivo_de_teste"

    with pytest.raises(PoliticaNegouError) as erro:
        permissoes.exigir(Permissao.TAREFAS_ESCREVER, pedido)
    assert erro.value.chave_mensagem == "motivo_de_teste"
    assert erro.value.politica == "t.motivo"


def test_quem_apanhava_a_recusa_antiga_continua_a_apanhar(pedido):
    """`PoliticaNegouError` é subclasse: nenhum `except` existente deixa de ver."""
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica("t.sub", {"concluir"}, {"tarefa"}, recusar_sempre)

    with pytest.raises(PermissaoNegadaError):
        permissoes.exigir(Permissao.TAREFAS_ESCREVER, pedido)


def test_a_ordem_da_resposta_nao_depende_da_ordem_de_registo(pedido):
    """Duas políticas a recusar dão sempre a mesma razão."""
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica("t.zz", {"concluir"}, {"tarefa"}, lambda s, p: "zz")
    permissoes.registar_politica("t.aa", {"concluir"}, {"tarefa"}, lambda s, p: "aa")

    assert permissoes.recusa(pedido).motivo == "aa"


# ================================================================== registo


def test_um_modulo_tem_de_ficar_no_seu_espaco_de_nomes():
    with pytest.raises(ValueError):
        permissoes.registar_politica(
            "tarefas.minha", {"concluir"}, {"tarefa"}, recusar_sempre, dono="estoque"
        )


def test_uma_politica_precisa_de_dizer_a_que_se_aplica():
    for acoes, tipos in (((), {"tarefa"}), ({"concluir"}, ())):
        with pytest.raises(ValueError):
            permissoes.registar_politica("t.vaga", acoes, tipos, recusar_sempre)


def test_as_politicas_de_um_plugin_saem_com_ele(pedido):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica(
        "estoque.nao", {"concluir"}, {"tarefa"}, recusar_sempre, dono="estoque"
    )
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False

    assert permissoes.esquecer_politicas_de_dono("estoque") == 1
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is True


# ========================================================== o interruptor


def test_uma_politica_presa_a_funcionalidade_desligada_nao_recusa(pedido):
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica(
        "t.opcional", {"concluir"}, {"tarefa"}, recusar_sempre,
        funcionalidade="segregacao_de_funcoes",
    )
    assert funcionalidades.ativa("segregacao_de_funcoes") is False
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is True

    funcionalidades.definir("segregacao_de_funcoes", True)
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False


def test_uma_funcionalidade_que_nao_existe_deixa_a_politica_a_valer(pedido):
    """Declaração errada fecha, não abre."""
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.registar_politica(
        "t.inventada", {"concluir"}, {"tarefa"}, recusar_sempre,
        funcionalidade="nao_existe",
    )
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER, pedido) is False


# ============================== a política que vem com a aplicação, a sério


@pytest.fixture
def tarefas():
    """Uma tarefa da Ana, uma do Bruno e uma anterior às contas."""
    import banco_de_dados as db

    db.criar_tabela()
    return {
        "ana": db.adicionar_tarefa("Da Ana", "2030-01-01", criada_por="ana"),
        "bruno": db.adicionar_tarefa("Do Bruno", "2030-01-02", criada_por="bruno"),
        "antiga": db.adicionar_tarefa("Antiga, sem dono", "2030-01-03"),
    }


def test_por_omissao_nada_muda(tarefas):
    """A instalação de quem já usava o produto continua exatamente igual."""
    import tarefas_servico as servico

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert servico.concluir(tarefas["ana"]) is True


def test_com_segregacao_ligada_quem_cria_nao_conclui(tarefas):
    import tarefas_servico as servico

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    with pytest.raises(PoliticaNegouError) as erro:
        servico.concluir(tarefas["ana"])
    assert erro.value.chave_mensagem == "politica_quem_cria_nao_conclui"

    # E a tarefa continua por concluir: a recusa é antes de escrever.
    import banco_de_dados as db

    assert bool(db.obter_tarefa(tarefas["ana"])[3]) is False


def test_outra_pessoa_conclui_a_mesma_tarefa(tarefas):
    """A segregação não bloqueia o trabalho: muda quem o fecha."""
    import tarefas_servico as servico

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("bruno", "administrador", persistir=False)
    assert servico.concluir(tarefas["ana"]) is True


def test_nem_o_administrador_escapa(tarefas):
    """Um controlo de segregação que o dono da instalação contorna não é um controlo."""
    import tarefas_servico as servico

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("chefe", "administrador", persistir=False)
    minha = servico.adicionar("Feita pelo chefe")

    with pytest.raises(PoliticaNegouError):
        servico.concluir(minha)


def test_as_tarefas_sem_dono_nao_sao_abrangidas(tarefas):
    """Ninguém as criou, por isso ninguém certifica o seu próprio trabalho."""
    import tarefas_servico as servico

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert servico.concluir(tarefas["antiga"]) is True


def test_reabrir_a_propria_tarefa_continua_a_ser_possivel(tarefas):
    """Travar o caminho de volta seria uma armadilha, não um controlo."""
    import tarefas_servico as servico

    permissoes.definir_sessao("bruno", "administrador", persistir=False)
    servico.concluir(tarefas["ana"])

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert servico.concluir(tarefas["ana"], concluida=False) is True


def test_remover_nao_e_travado_por_esta_politica(tarefas):
    """Esta política é sobre certificar trabalho, não sobre apagar.

    Fica escrito porque a fronteira é uma decisão: quem quiser travar a
    remoção regista outra política, e vê-se no inventário que o fez.
    """
    import tarefas_servico as servico

    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert servico.remover(tarefas["ana"]) is True


def test_a_porta_das_tarefas_traz_as_suas_politicas():
    """Importar `tarefas_servico` chega para as regras existirem.

    Se dependessem do arranque da interface, um caminho sem janela — um
    plugin, um teste, uma futura API — escrevia sem elas.
    """
    import importlib
    import sys

    permissoes.limpar_politicas()
    assert permissoes.politicas() == []

    sys.modules.pop("tarefas_servico", None)
    importlib.import_module("tarefas_servico")

    nomes = [p.nome for p in permissoes.politicas()]
    assert "tarefas.quem_cria_nao_conclui" in nomes


def test_a_tentativa_recusada_fica_na_trilha(tarefas):
    """É o que separa um controlo de um obstáculo.

    Um obstáculo impede e cala-se. Um controlo impede e **deixa registo** —
    quem audita quer poder perguntar "houve tentativas?", e a resposta não
    pode depender de alguém se ter lembrado de olhar para o log.
    """
    import tarefas_servico as servico
    from core import auditoria

    auditoria.ativar()
    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    with pytest.raises(PoliticaNegouError):
        servico.concluir(tarefas["ana"])

    registos = [r for r in auditoria.consultar(limite=20) if r.evento == "politica.recusou"]
    assert len(registos) == 1
    assert registos[0].utilizador == "ana"
    assert registos[0].alvo == str(tarefas["ana"])


def test_perguntar_nao_e_tentar(tarefas):
    """`pode` não suja a trilha; só `exigir` é uma tentativa.

    A interface chama `pode` para decidir se desenha um botão. Se cada
    pergunta dessas ficasse registada, a trilha enchia-se de ruído e as
    tentativas a sério deixavam de se encontrar lá dentro.
    """
    import tarefas_servico as servico
    from core import auditoria

    auditoria.ativar()
    funcionalidades.definir("segregacao_de_funcoes", True)
    permissoes.definir_sessao("ana", "administrador", persistir=False)

    for _ in range(5):
        permissoes.pode(Permissao.TAREFAS_ESCREVER, servico.pedido_sobre("concluir", tarefas["ana"]))

    assert not [r for r in auditoria.consultar(limite=20) if r.evento == "politica.recusou"]
