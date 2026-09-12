"""Testes da regra de quem vê e edita que tarefas."""

import pytest

import database as db
import tarefas_servico as servico
from core import permissoes
from core.permissoes import Permissao, PermissaoNegadaError


def como(utilizador: str, papel: str = "colaborador") -> None:
    """Põe a sessão num utilizador e papel."""
    permissoes.definir_sessao(utilizador, papel, persistir=False)


@pytest.fixture
def cenario():
    """Uma tarefa de cada: da Ana, do Bruno e uma anterior às contas."""
    db.criar_tabela()
    return {
        "ana": db.adicionar_tarefa("Da Ana", "2030-01-01", criada_por="ana"),
        "bruno": db.adicionar_tarefa("Do Bruno", "2030-01-02", criada_por="bruno"),
        "antiga": db.adicionar_tarefa("Antiga, sem dono", "2030-01-03"),
    }


# ============================================================== VISIBILIDADE


def test_colaborador_ve_as_suas_e_as_sem_dono(cenario):
    como("ana", "colaborador")
    descricoes = [t[1] for t in servico.listar()]
    assert descricoes == ["Da Ana", "Antiga, sem dono"]


def test_colaborador_nao_ve_as_de_outro(cenario):
    como("ana", "colaborador")
    assert "Do Bruno" not in [t[1] for t in servico.listar()]
    assert servico.pode_ver(cenario["bruno"]) is False


def test_gestor_ve_tudo(cenario):
    como("chefe", "gestor")
    assert len(servico.listar()) == 3
    assert servico.ve_tudo() is True


def test_administrador_ve_tudo(cenario):
    como("rodrigo", "administrador")
    assert len(servico.listar()) == 3


def test_colaborador_ve_a_analise_das_suas(cenario):
    """Ver os próprios números não é privilégio; ver os dos outros é."""
    from analytics import fontes

    como("ana", "colaborador")
    assert fontes.panorama(dias=30).kpis.total == 2


def test_visualizador_ve_tudo_mas_nao_escreve(cenario):
    como("auditor", "visualizador")
    assert len(servico.listar()) == 3
    with pytest.raises(PermissaoNegadaError):
        servico.adicionar("Não devia conseguir")


def test_filtro_so_as_minhas_para_quem_ve_tudo(cenario):
    como("chefe", "gestor")
    db.adicionar_tarefa("Do chefe", criada_por="chefe")

    assert len(servico.listar()) == 4
    minhas = [t[1] for t in servico.listar(apenas_minhas=True)]
    assert minhas == ["Antiga, sem dono", "Do chefe"]


def test_tarefa_sem_dono_e_de_todos(cenario):
    """Foram criadas antes de existirem contas: não são de ninguém."""
    for utilizador in ("ana", "bruno", "carla"):
        como(utilizador, "colaborador")
        assert "Antiga, sem dono" in [t[1] for t in servico.listar()]
        assert servico.pode_editar(cenario["antiga"]) is True


def test_obter_respeita_a_visibilidade(cenario):
    como("ana", "colaborador")
    assert servico.obter(cenario["ana"])[1] == "Da Ana"
    assert servico.obter(cenario["bruno"]) is None


def test_por_data_respeita_a_visibilidade(cenario):
    como("ana", "colaborador")
    assert servico.listar_por_data("2030-01-01") != []
    assert servico.listar_por_data("2030-01-02") == []

    como("chefe", "gestor")
    assert servico.listar_por_data("2030-01-02") != []


def test_listar_completas_respeita_a_visibilidade(cenario):
    como("ana", "colaborador")
    assert [t[1] for t in servico.listar_completas()] == ["Da Ana", "Antiga, sem dono"]


# =================================================================== ESCRITA


def test_criar_carimba_o_dono(cenario):
    como("ana", "colaborador")
    tarefa_id = servico.adicionar("Nova da Ana")
    assert servico.dono(tarefa_id) == "ana"


def test_sem_permissao_de_escrita_nao_cria(cenario):
    como("auditor", "visualizador")
    with pytest.raises(PermissaoNegadaError) as erro:
        servico.adicionar("Não passa")
    assert erro.value.permissao == Permissao.TAREFAS_ESCREVER


def test_editar_a_propria_tarefa(cenario):
    como("ana", "colaborador")
    assert servico.concluir(cenario["ana"]) is True
    assert db.obter_tarefa(cenario["ana"])[3] == 1


def test_nao_edita_a_tarefa_de_outro(cenario):
    como("ana", "colaborador")
    with pytest.raises(PermissaoNegadaError):
        servico.concluir(cenario["bruno"])
    with pytest.raises(PermissaoNegadaError):
        servico.remover(cenario["bruno"])
    assert db.obter_tarefa(cenario["bruno"]) is not None


def test_gestor_edita_a_tarefa_de_outro(cenario):
    como("chefe", "gestor")
    assert servico.concluir(cenario["ana"]) is True
    assert servico.remover(cenario["bruno"]) is True


def test_visualizador_nao_edita_nada(cenario):
    como("auditor", "visualizador")
    with pytest.raises(PermissaoNegadaError):
        servico.concluir(cenario["ana"])


def test_pode_editar(cenario):
    como("ana", "colaborador")
    assert servico.pode_editar(cenario["ana"]) is True
    assert servico.pode_editar(cenario["bruno"]) is False

    como("auditor", "visualizador")
    assert servico.pode_editar(cenario["ana"]) is False


def test_tarefa_inexistente(cenario):
    como("chefe", "gestor")
    assert servico.pode_ver(9999) is False
    assert servico.obter(9999) is None


def test_contar_por_dono(cenario):
    como("chefe", "gestor")
    assert servico.contar_por_dono() == [("", 1), ("ana", 1), ("bruno", 1)]

    como("ana", "colaborador")
    assert servico.contar_por_dono() == [("ana", 2)], "as suas e a sem dono"


# ================================================== PLUGINS E ANALYTICS


def test_plugins_respeitam_a_visibilidade(cenario):
    """Um plugin não pode ser a porta das traseiras para ver tudo."""
    from plugin_ui import ServicoTarefasApp

    fachada = ServicoTarefasApp()
    como("ana", "colaborador")
    assert [t[1] for t in fachada.listar()] == ["Da Ana", "Antiga, sem dono"]
    assert fachada.listar_por_data("2030-01-02") == []

    como("chefe", "gestor")
    assert len(fachada.listar()) == 3


def test_plugin_cria_tarefa_em_nome_de_quem_esta_em_sessao(cenario):
    from plugin_ui import ServicoTarefasApp

    como("ana", "colaborador")
    tarefa_id = ServicoTarefasApp().adicionar("Criada por um plugin")
    assert servico.dono(tarefa_id) == "ana"


def test_analytics_conta_so_o_que_a_sessao_ve(cenario):
    from analytics import fontes

    como("ana", "colaborador")
    assert fontes.panorama(dias=30).kpis.total == 2

    como("chefe", "gestor")
    assert fontes.panorama(dias=30).kpis.total == 3


def test_relatorio_so_leva_o_que_a_sessao_ve(cenario):
    from reporting.construtor import relatorio_de_tarefas

    como("ana", "colaborador")
    relatorio = relatorio_de_tarefas(dias=30)
    descricoes = [linha[0] for linha in relatorio.secoes[2].linhas]
    assert "Do Bruno" not in descricoes
    assert "Da Ana" in descricoes


# ======================================================== BANCO E MIGRAÇÃO


def test_linhas_antigas_ficam_sem_dono_e_nao_inventado(cenario):
    assert db.dono_de(cenario["antiga"]) == db.SEM_DONO


def test_o_banco_nao_decide_quem_ve_o_que(cenario):
    """database.py continua armazenamento: sem filtro, devolve tudo."""
    como("ana", "colaborador")
    assert len(db.buscar_tarefas()) == 3
    assert len(servico.listar()) == 2
