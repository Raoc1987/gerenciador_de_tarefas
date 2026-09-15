"""A vigilância: dizer o que mudou, e calar-se no resto.

O problema difícil de um sistema de alertas não é detetar. É não repetir.
"Há 15 tarefas atrasadas" continua verdade amanhã, e depois. Se cada avaliação
anunciasse, uma regra ligada a ela criava a mesma tarefa todos os dias — e um
alerta que se repete é um alerta que se deixa de ler.

Quase todos estes testes são sobre o silêncio.
"""

from datetime import date, timedelta

import pytest

import alertas
import banco_de_dados as db
from analitica.insights import Insight, Nivel
from core import auditoria, eventos, permissoes

HOJE = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def sessao():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()


def com_atrasos(quantas: int = 12):
    """Tarefas vencidas e por concluir — o insight mais simples de provocar."""
    ontem = (HOJE - timedelta(days=3)).isoformat()
    return [(i, f"Tarefa {i}", ontem, 0, "2026-06-01") for i in range(1, quantas + 1)]


# ============================================================= ANUNCIAR


def test_uma_conclusao_nova_e_anunciada():
    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)

    mudanca = alertas.avaliar(com_atrasos(), hoje=HOJE)

    assert mudanca.novos, "devia ter encontrado alguma coisa"
    assert recebidos
    assert recebidos[0].dados["id"] == mudanca.novos[0].chave
    assert recebidos[0].dados["nivel"] in ("atencao", "critico")


def test_o_evento_leva_os_numeros_para_a_regra_usar():
    """Uma regra tem de poder escrever "há {total} atrasadas" na tarefa."""
    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
    alertas.avaliar(com_atrasos(), hoje=HOJE)

    assert len(recebidos[0].dados) > 3, "os parâmetros do insight vão no evento"


def test_sem_dados_nao_ha_alertas():
    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)

    assert not alertas.avaliar([], hoje=HOJE).houve_novidade
    assert recebidos == []


def test_boas_noticias_nao_disparam_automacoes(monkeypatch):
    """Uma coisa boa fica no painel; não devia acordar ninguém."""
    monkeypatch.setattr(
        alertas, "gerar", lambda *a, **k: [Insight("bom", {}, Nivel.POSITIVO)]
    )
    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)

    assert not alertas.avaliar([1], hoje=HOJE).houve_novidade
    assert recebidos == []


# ============================================================== SILÊNCIO


def test_a_mesma_conclusao_nao_se_repete():
    """O teste que define esta peça."""
    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)

    primeira = alertas.avaliar(com_atrasos(), hoje=HOJE)
    assert primeira.novos and len(recebidos) == len(primeira.novos)

    antes = len(recebidos)
    segunda = alertas.avaliar(com_atrasos(), hoje=HOJE)
    assert not segunda.houve_novidade
    assert len(recebidos) == antes, "não podia ter dito nada de novo"


def test_os_numeros_mudarem_nao_e_novidade():
    """12 atrasadas ou 13: a situação é a mesma, e já foi dita."""
    alertas.avaliar(com_atrasos(12), hoje=HOJE)

    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
    assert not alertas.avaliar(com_atrasos(13), hoje=HOJE).houve_novidade
    assert recebidos == []


def test_a_memoria_sobrevive_ao_reinicio():
    """Senão cada arranque anunciava tudo outra vez."""
    alertas.avaliar(com_atrasos(), hoje=HOJE)
    assert alertas.vistos(), "tem de ficar no banco, não em memória"

    # Uma segunda avaliação, mesmo noutro processo, leria este estado.
    assert not alertas.avaliar(com_atrasos(), hoje=HOJE).houve_novidade


# ============================================================== AGRAVAR


def test_agravar_volta_a_ser_anunciado(monkeypatch):
    """Passar de atenção a crítico é notícia."""
    monkeypatch.setattr(
        alertas, "gerar", lambda *a, **k: [Insight("x", {}, Nivel.ATENCAO)]
    )
    alertas.avaliar([1], hoje=HOJE)

    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
    monkeypatch.setattr(
        alertas, "gerar", lambda *a, **k: [Insight("x", {}, Nivel.CRITICO)]
    )
    mudanca = alertas.avaliar([1], hoje=HOJE)

    assert [i.chave for i in mudanca.agravados] == ["x"]
    assert len(recebidos) == 1


def test_melhorar_sem_resolver_nao_volta_a_anunciar(monkeypatch):
    """Passar de crítico a atenção não é novidade que valha interromper."""
    monkeypatch.setattr(
        alertas, "gerar", lambda *a, **k: [Insight("x", {}, Nivel.CRITICO)]
    )
    alertas.avaliar([1], hoje=HOJE)

    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
    monkeypatch.setattr(
        alertas, "gerar", lambda *a, **k: [Insight("x", {}, Nivel.ATENCAO)]
    )
    assert not alertas.avaliar([1], hoje=HOJE).houve_novidade
    assert recebidos == []


# ============================================================= RESOLVER


def test_deixar_de_se_aplicar_e_anunciado():
    resolvidos = []
    eventos.subscrever(eventos.ANALISE_RESOLVIDO, resolvidos.append)

    alertas.avaliar(com_atrasos(), hoje=HOJE)
    mudanca = alertas.avaliar([], hoje=HOJE)

    assert mudanca.resolvidos
    assert resolvidos
    assert resolvidos[0].dados["id"] == mudanca.resolvidos[0]


def test_depois_de_resolvido_volta_a_poder_ser_anunciado():
    """A situação pode regressar, e aí é mesmo notícia outra vez."""
    alertas.avaliar(com_atrasos(), hoje=HOJE)
    alertas.avaliar([], hoje=HOJE)
    assert alertas.vistos() == {}

    assert alertas.avaliar(com_atrasos(), hoje=HOJE).novos


def test_esquecer_tudo_repoe_a_memoria():
    alertas.avaliar(com_atrasos(), hoje=HOJE)
    alertas.esquecer_tudo()
    assert alertas.vistos() == {}


# ========================================================== NA APLICAÇÃO


def test_a_vigilancia_reage_a_uma_tarefa_criada():
    """É quando as conclusões podem ter mudado."""
    alertas.ativar()
    try:
        assert alertas.ativa()
        recebidos = []
        eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)

        vencida = (date.today() - timedelta(days=5)).isoformat()
        for i in range(12):
            db.adicionar_tarefa(f"Atrasada {i}", vencida)

        assert recebidos, "criar tarefas atrasadas devia ter desencadeado a análise"
    finally:
        alertas.desativar()


def test_ativar_duas_vezes_nao_duplica():
    alertas.ativar()
    alertas.ativar()
    try:
        recebidos = []
        eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
        vencida = (date.today() - timedelta(days=5)).isoformat()
        for i in range(12):
            db.adicionar_tarefa(f"A {i}", vencida)

        chaves = [e.dados["id"] for e in recebidos]
        assert len(chaves) == len(set(chaves)), "cada alerta uma vez só"
    finally:
        alertas.desativar()


def test_uma_falha_a_analisar_nao_impede_criar_tarefas(monkeypatch):
    """A vigilância é um extra; não pode estragar o trabalho de ninguém."""

    def explode(*args, **kwargs):
        raise RuntimeError("rebentei")

    alertas.ativar()
    try:
        monkeypatch.setattr(alertas, "avaliar", explode)
        tarefa = db.adicionar_tarefa("Tem de existir na mesma", "2030-01-01")
        assert db.obter_tarefa(tarefa) is not None
    finally:
        alertas.desativar()


def test_desativar_para_mesmo():
    alertas.ativar()
    alertas.desativar()
    assert not alertas.ativa()

    recebidos = []
    eventos.subscrever(eventos.ANALISE_ALERTA, recebidos.append)
    vencida = (date.today() - timedelta(days=5)).isoformat()
    for i in range(12):
        db.adicionar_tarefa(f"A {i}", vencida)
    assert recebidos == []


def test_um_alerta_fica_na_auditoria():
    """É uma afirmação da aplicação sobre o trabalho de alguém."""
    auditoria.ativar()
    alertas.avaliar(com_atrasos(), hoje=HOJE)

    registos = [r for r in auditoria.consultar() if r.evento == eventos.ANALISE_ALERTA]
    assert registos
