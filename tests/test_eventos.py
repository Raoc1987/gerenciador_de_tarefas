"""Testes do barramento de eventos e da sua integração com o resto."""

import pytest

import database as db
from core import eventos
from core.eventos import BarramentoEventos


@pytest.fixture
def barramento():
    """Barramento isolado, para não interferir com o da aplicação."""
    return BarramentoEventos()


def coletor():
    """Devolve ``(lista, ouvinte)`` para registar o que chegou."""
    recebidos = []
    return recebidos, recebidos.append


# ------------------------------------------------------- publicar/subscrever


def test_ouvinte_recebe_o_evento(barramento):
    recebidos, ouvinte = coletor()
    barramento.subscrever("tarefa.criada", ouvinte)
    barramento.publicar("tarefa.criada", id=7, descricao="Comprar pão")

    assert len(recebidos) == 1
    evento = recebidos[0]
    assert evento.nome == "tarefa.criada"
    assert evento.dados == {"id": 7, "descricao": "Comprar pão"}
    assert evento["id"] == 7
    assert evento.obter("inexistente", "padrão") == "padrão"
    assert evento.momento


def test_evento_nao_chega_a_quem_nao_subscreveu(barramento):
    recebidos, ouvinte = coletor()
    barramento.subscrever("tarefa.criada", ouvinte)
    barramento.publicar("tarefa.removida", id=1)
    assert recebidos == []


def test_padrao_com_asterisco(barramento):
    recebidos, ouvinte = coletor()
    barramento.subscrever("tarefa.*", ouvinte)
    barramento.publicar("tarefa.criada", id=1)
    barramento.publicar("tarefa.removida", id=1)
    barramento.publicar("plugin.ativado", id="x")
    assert [e.nome for e in recebidos] == ["tarefa.criada", "tarefa.removida"]


def test_padrao_universal(barramento):
    recebidos, ouvinte = coletor()
    barramento.subscrever("*", ouvinte)
    barramento.publicar("tarefa.criada")
    barramento.publicar("plugin.ativado")
    assert len(recebidos) == 2


def test_ordem_de_entrega_e_a_de_subscricao(barramento):
    ordem = []
    barramento.subscrever("x", lambda e: ordem.append("primeiro"))
    barramento.subscrever("x", lambda e: ordem.append("segundo"))
    barramento.publicar("x")
    assert ordem == ["primeiro", "segundo"]


def test_varios_ouvintes_do_mesmo_evento(barramento):
    contagem = []
    for _ in range(3):
        barramento.subscrever("x", lambda e: contagem.append(1))
    barramento.publicar("x")
    assert len(contagem) == 3


def test_ouvinte_tem_de_ser_invocavel(barramento):
    with pytest.raises(TypeError):
        barramento.subscrever("x", "isto não é uma função")


# ------------------------------------------------------------- isolamento


def test_ouvinte_com_erro_nao_afeta_os_outros(barramento):
    recebidos, ouvinte = coletor()

    def explode(evento):
        raise RuntimeError("falha proposital no ouvinte")

    barramento.subscrever("x", explode)
    barramento.subscrever("x", ouvinte)

    # Publicar não levanta, mesmo com um ouvinte defeituoso.
    evento = barramento.publicar("x", valor=1)
    assert evento.dados == {"valor": 1}
    assert len(recebidos) == 1


def test_erro_no_ouvinte_nao_impede_publicacoes_seguintes(barramento):
    def explode(evento):
        raise ValueError("boom")

    barramento.subscrever("x", explode)
    for _ in range(3):
        barramento.publicar("x")
    assert len(barramento.historico()) == 3


# ------------------------------------------------------------ cancelamento


def test_cancelar_uma_subscricao(barramento):
    recebidos, ouvinte = coletor()
    inscricao = barramento.subscrever("x", ouvinte)
    barramento.publicar("x")
    assert barramento.cancelar(inscricao) is True
    barramento.publicar("x")
    assert len(recebidos) == 1
    assert barramento.cancelar(inscricao) is False


def test_cancelar_por_dono(barramento):
    recebidos_a, ouvinte_a = coletor()
    recebidos_b, ouvinte_b = coletor()
    barramento.subscrever("x", ouvinte_a, dono="plugin_a")
    barramento.subscrever("y", ouvinte_a, dono="plugin_a")
    barramento.subscrever("x", ouvinte_b, dono="plugin_b")

    assert barramento.cancelar_por_dono("plugin_a") == 2
    barramento.publicar("x")
    barramento.publicar("y")
    assert recebidos_a == []
    assert len(recebidos_b) == 1


def test_cancelar_dono_inexistente(barramento):
    assert barramento.cancelar_por_dono("ninguem") == 0
    assert barramento.cancelar_por_dono("") == 0


def test_subscritores(barramento):
    _, ouvinte = coletor()
    barramento.subscrever("tarefa.*", ouvinte)
    barramento.subscrever("plugin.ativado", ouvinte)
    assert len(barramento.subscritores()) == 2
    assert len(barramento.subscritores("tarefa.criada")) == 1
    assert len(barramento.subscritores("outra.coisa")) == 0


# --------------------------------------------------------------- histórico


def test_historico_guarda_a_ordem(barramento):
    barramento.publicar("a")
    barramento.publicar("b")
    assert [e.nome for e in barramento.historico()] == ["a", "b"]
    assert [e.nome for e in barramento.historico(limite=1)] == ["b"]


def test_historico_filtra_por_padrao(barramento):
    barramento.publicar("tarefa.criada")
    barramento.publicar("plugin.ativado")
    assert [e.nome for e in barramento.historico(padrao="tarefa.*")] == ["tarefa.criada"]


def test_historico_e_limitado(barramento):
    pequeno = BarramentoEventos(tamanho_historico=3)
    for indice in range(10):
        pequeno.publicar("x", indice=indice)
    historico = pequeno.historico()
    assert len(historico) == 3
    assert [e.dados["indice"] for e in historico] == [7, 8, 9]


def test_limpar(barramento):
    recebidos, ouvinte = coletor()
    barramento.subscrever("x", ouvinte)
    barramento.publicar("x")

    barramento.limpar()
    assert barramento.historico() == []
    assert barramento.subscritores() == []

    barramento.publicar("x")
    assert len(recebidos) == 1, "o ouvinte cancelado não deve voltar a receber"
    assert len(barramento.historico()) == 1


# ------------------------------------------------- integração com o banco


def test_criar_tarefa_publica_evento():
    recebidos, ouvinte = coletor()
    eventos.subscrever(eventos.TAREFA_CRIADA, ouvinte)
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Preparar relatório", "2026-10-01")

    assert len(recebidos) == 1
    assert recebidos[0].dados == {
        "id": tarefa_id,
        "descricao": "Preparar relatório",
        "data_vencimento": "2026-10-01",
    }
    assert recebidos[0].origem == "database"


def test_concluir_e_reabrir_publicam_eventos_diferentes():
    recebidos, ouvinte = coletor()
    eventos.subscrever("tarefa.*", ouvinte)
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Tarefa")
    db.concluir_tarefa(tarefa_id)
    db.concluir_tarefa(tarefa_id, False)

    assert [e.nome for e in recebidos] == [
        eventos.TAREFA_CRIADA,
        eventos.TAREFA_CONCLUIDA,
        eventos.TAREFA_REABERTA,
    ]


def test_remover_publica_evento():
    recebidos, ouvinte = coletor()
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Temporária")
    eventos.subscrever(eventos.TAREFA_REMOVIDA, ouvinte)
    db.remover_tarefa(tarefa_id)
    assert [e.dados["id"] for e in recebidos] == [tarefa_id]


def test_operacao_sem_efeito_nao_publica():
    """Concluir ou remover algo inexistente não gera evento."""
    recebidos, ouvinte = coletor()
    db.criar_tabela()
    eventos.subscrever("tarefa.*", ouvinte)
    db.concluir_tarefa(999)
    db.remover_tarefa(999)
    assert recebidos == []


def test_descricao_vazia_nao_publica():
    recebidos, ouvinte = coletor()
    db.criar_tabela()
    eventos.subscrever("tarefa.*", ouvinte)
    with pytest.raises(ValueError):
        db.adicionar_tarefa("   ")
    assert recebidos == []


def test_ouvinte_defeituoso_nao_quebra_a_criacao_de_tarefas():
    """O caso que interessa: um plugin mau não impede o utilizador de trabalhar."""
    db.criar_tabela()

    def explode(evento):
        raise RuntimeError("plugin com defeito")

    eventos.subscrever("tarefa.*", explode, dono="plugin_mau")
    tarefa_id = db.adicionar_tarefa("Tarefa que tem de ser criada")
    assert db.obter_tarefa(tarefa_id) is not None


def test_catalogo_de_eventos_do_nucleo():
    """Os nomes publicados pelo núcleo estão declarados no catálogo."""
    for nome in (
        eventos.TAREFA_CRIADA,
        eventos.TAREFA_CONCLUIDA,
        eventos.PLUGIN_ATIVADO,
        eventos.PLUGIN_REMOVIDO,
    ):
        assert nome in eventos.eventos_conhecidos()
