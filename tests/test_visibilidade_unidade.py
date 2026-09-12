"""O meio-termo: ver o seu departamento, nem só o seu nem o da empresa toda.

É onde a maioria dos chefes de departamento realmente está, e até agora não
havia forma de o dizer: ou se via tudo, ou só o próprio.

Estes testes guardam duas coisas ao mesmo tempo — que o âmbito novo funciona,
e que a chegada da estrutura **não muda nada** para quem já usava a aplicação.
"""

import pytest

import database as db
import tarefas_servico as servico
from core import organizacao, permissoes, utilizadores
from core.organizacao import TipoUnidade
from core.permissoes import Permissao, PermissaoNegadaError


def como(utilizador: str, papel: str = "colaborador") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


@pytest.fixture
def empresa():
    """Engenharia (Ana chefe, Bruno) e Financeiro (Carla), sob a Acme.

    Cada pessoa com uma tarefa sua, criada de dentro da sua unidade.
    """
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    engenharia = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, acme.id)
    plataforma = organizacao.criar("Plataforma", TipoUnidade.EQUIPA, engenharia.id)
    financeiro = organizacao.criar("Financeiro", TipoUnidade.DEPARTAMENTO, acme.id)

    pessoas = {
        "ana": (engenharia.id, "gestor_de_unidade"),
        "bruno": (plataforma.id, "colaborador"),
        "carla": (financeiro.id, "colaborador"),
    }
    tarefas = {}
    for nome, (unidade_id, papel) in pessoas.items():
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel=papel)
        utilizadores.definir_unidade(nome, unidade_id)
        como(nome, papel)
        tarefas[nome] = servico.adicionar(f"Tarefa da {nome}", "2030-01-01")

    tarefas["antiga"] = db.adicionar_tarefa("Antiga, sem dono", "2030-01-02")
    return {
        "acme": acme,
        "engenharia": engenharia,
        "plataforma": plataforma,
        "financeiro": financeiro,
        "tarefas": tarefas,
    }


def descricoes() -> set:
    return {t[1] for t in servico.listar()}


# ======================================================== O ÂMBITO NOVO


def test_o_chefe_ve_o_seu_departamento_e_o_que_esta_abaixo(empresa):
    como("ana", "gestor_de_unidade")
    assert "Tarefa da bruno" in descricoes(), "o Bruno está numa equipa dentro da dela"


def test_o_chefe_nao_ve_o_departamento_do_lado(empresa):
    como("ana", "gestor_de_unidade")
    assert "Tarefa da carla" not in descricoes()
    assert servico.pode_ver(empresa["tarefas"]["carla"]) is False


def test_o_chefe_continua_a_ver_as_suas(empresa):
    como("ana", "gestor_de_unidade")
    assert "Tarefa da ana" in descricoes()


def test_o_chefe_ve_as_tarefas_sem_dono(empresa):
    """São anteriores às contas e não pertencem a mais ninguém."""
    como("ana", "gestor_de_unidade")
    assert "Antiga, sem dono" in descricoes()


def test_um_colaborador_nao_ve_os_colegas_da_mesma_unidade(empresa):
    """Estar na mesma equipa não é autorização: o âmbito vem da permissão."""
    como("bruno", "colaborador")
    assert "Tarefa da ana" not in descricoes()
    assert "Tarefa da bruno" in descricoes()


def test_o_chefe_pode_editar_o_que_alcanca(empresa):
    como("ana", "gestor_de_unidade")
    assert servico.pode_editar(empresa["tarefas"]["bruno"]) is True
    assert servico.concluir(empresa["tarefas"]["bruno"]) is True


def test_o_chefe_nao_edita_o_que_nao_alcanca(empresa):
    como("ana", "gestor_de_unidade")
    assert servico.pode_editar(empresa["tarefas"]["carla"]) is False
    with pytest.raises(PermissaoNegadaError):
        servico.concluir(empresa["tarefas"]["carla"])


def test_o_que_a_lista_mostra_e_o_que_se_pode_abrir(empresa):
    """Uma tarefa que aparece tem de poder ser aberta, e vice-versa."""
    como("ana", "gestor_de_unidade")
    visiveis = {t[0] for t in servico.listar()}
    for tarefa_id in empresa["tarefas"].values():
        assert servico.pode_ver(tarefa_id) == (tarefa_id in visiveis)


def test_a_analise_respeita_o_mesmo_ambito(empresa):
    """Os números do painel não podem contar o que a lista não mostra."""
    como("ana", "gestor_de_unidade")
    completas = {t[1] for t in servico.listar_completas()}
    assert completas == descricoes()


def test_por_data_respeita_o_mesmo_ambito(empresa):
    como("ana", "gestor_de_unidade")
    assert {t[1] for t in servico.listar_por_data("2030-01-01")} == {
        "Tarefa da ana",
        "Tarefa da bruno",
    }


def test_apenas_minhas_continua_a_estreitar(empresa):
    """O filtro que o utilizador escolhe na interface manda sobre o âmbito."""
    como("ana", "gestor_de_unidade")
    assert {t[1] for t in servico.listar(apenas_minhas=True)} == {
        "Tarefa da ana",
        "Antiga, sem dono",
    }


# =========================================== SEM ESTRUTURA, NADA MUDA


def test_sem_unidade_atribuida_ve_so_as_suas(empresa):
    """Não há como um âmbito vazio conceder mais do que o mínimo."""
    utilizadores.definir_unidade("ana", None)
    como("ana", "gestor_de_unidade")
    assert descricoes() == {"Tarefa da ana", "Antiga, sem dono"}


def test_quem_ve_tudo_continua_a_ver_tudo(empresa):
    como("chefe", "gestor")
    assert len(servico.listar()) == 4


def test_um_colaborador_de_sempre_nao_nota_diferenca(empresa):
    """A migração é aditiva: quem nunca montou estrutura fica na mesma."""
    como("carla", "colaborador")
    assert descricoes() == {"Tarefa da carla", "Antiga, sem dono"}


def test_o_ambito_diz_o_que_e_sem_ambiguidade(empresa):
    como("chefe", "gestor")
    assert servico.ambito().ve_tudo is True

    como("bruno", "colaborador")
    alcance = servico.ambito()
    assert alcance.ve_tudo is False
    assert alcance.unidades == ()


# ============================================== A UNIDADE DA TAREFA


def test_a_tarefa_guarda_a_unidade_de_quando_foi_criada(empresa):
    assert db.unidade_de(empresa["tarefas"]["bruno"]) == empresa["plataforma"].id


def test_mudar_de_departamento_nao_reescreve_o_passado(empresa):
    """O trabalho continua a contar para onde foi feito."""
    antes = db.unidade_de(empresa["tarefas"]["bruno"])
    utilizadores.definir_unidade("bruno", empresa["financeiro"].id)
    assert db.unidade_de(empresa["tarefas"]["bruno"]) == antes

    como("ana", "gestor_de_unidade")
    assert "Tarefa da bruno" in descricoes(), "ficou onde foi feita"


def test_o_trabalho_novo_conta_para_o_departamento_novo(empresa):
    utilizadores.definir_unidade("bruno", empresa["financeiro"].id)
    como("bruno", "colaborador")
    nova = servico.adicionar("Depois da mudança", "2030-02-01")

    assert db.unidade_de(nova) == empresa["financeiro"].id
    como("ana", "gestor_de_unidade")
    assert "Depois da mudança" not in descricoes()


def test_mover_a_unidade_alarga_o_que_o_chefe_alcanca(empresa):
    """Passar o Financeiro para dentro da Engenharia é uma decisão de estrutura."""
    como("ana", "gestor_de_unidade")
    assert "Tarefa da carla" not in descricoes()

    organizacao.mover(empresa["financeiro"].id, empresa["engenharia"].id)
    assert "Tarefa da carla" in descricoes()


def test_uma_unidade_desativada_sai_do_alcance(empresa):
    como("ana", "gestor_de_unidade")
    assert "Tarefa da bruno" in descricoes()

    organizacao.definir_ativa(empresa["plataforma"].id, False)
    assert "Tarefa da bruno" not in descricoes()


# ================================================ A PORTA DOS PLUGINS


def test_um_plugin_nao_ve_mais_do_que_a_sessao(empresa):
    """A fachada dos plugins passa pelo serviço: o âmbito aplica-se na mesma."""
    from core.permissoes import Permissao as P
    from core.plugin_api import TarefasComPermissoes
    from plugin_ui import ServicoTarefasApp

    como("ana", "gestor_de_unidade")
    tarefas = TarefasComPermissoes(ServicoTarefasApp(), [P.TAREFAS_LER])

    vistas = {t[1] for t in tarefas.listar()}
    assert "Tarefa da carla" not in vistas
    assert vistas == descricoes()


def test_declarar_ver_unidade_nao_alarga_uma_sessao_estreita(empresa):
    """Um plugin não empresta permissões a quem o instalou."""
    from core.plugin_api import TarefasComPermissoes
    from plugin_ui import ServicoTarefasApp

    como("bruno", "colaborador")
    tarefas = TarefasComPermissoes(
        ServicoTarefasApp(), [Permissao.TAREFAS_LER, Permissao.TAREFAS_VER_UNIDADE]
    )
    assert {t[1] for t in tarefas.listar()} == {"Tarefa da bruno", "Antiga, sem dono"}
