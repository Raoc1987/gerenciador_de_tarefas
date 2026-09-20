"""Contas e trilha de auditoria: o âmbito é a empresa, seja qual for o papel.

As tarefas ([ADR-0011]) e os dados dos módulos ([ADR-0012]) já seguiam esta
regra. As contas e a auditoria não — e isso não era uma omissão inofensiva.
Medido antes de mexer, numa instalação com duas empresas e a Ana como
administradora **dentro da Acme**:

* via o nome e o papel de `bruno_secreto`, empregado da Rival;
* via na trilha o que ele tinha feito;
* e, pior do que ver: podia **mudá-lo de empresa, desativá-lo e apagá-lo**.

O papel `administrador` é da instalação inteira — é o que ele quer dizer. O
que faltava não era um papel novo: era as contas seguirem a regra que as
tarefas já seguiam. Quem administra a instalação não está no organigrama, e
continua a ver tudo.
"""

import pytest

from core import auditoria, organizacao, permissoes, utilizadores
from core.organizacao import TipoUnidade
from core.utilizadores import ContaDeOutraEmpresaError


def como(utilizador: str, papel: str = "administrador") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


def como_a_instalacao() -> None:
    """Quem administra a instalação: não está no organigrama, e vê tudo."""
    permissoes.definir_sessao("instalacao", "administrador", persistir=False)


@pytest.fixture
def duas_empresas():
    """Acme (ana, colega) e Rival (bruno_secreto), e um root fora da estrutura."""
    como_a_instalacao()
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    acme_eng = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, acme.id)
    rival = organizacao.criar("Rival", TipoUnidade.EMPRESA)
    rival_eng = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, rival.id)

    for nome, unidade in (
        ("ana", acme_eng.id),
        ("colega", acme_eng.id),
        ("bruno_secreto", rival_eng.id),
    ):
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="colaborador")
        utilizadores.definir_unidade(nome, unidade)
    utilizadores.criar("root", "Uma-Senha-Longa-123", papel="administrador")

    return {"acme": acme, "rival": rival, "acme_eng": acme_eng, "rival_eng": rival_eng}


def nomes_visiveis() -> set:
    return {u.nome_utilizador for u in utilizadores.listar()}


# =========================================== o que não se vê: contas de outros


def test_nao_se_ve_o_pessoal_da_outra_empresa(duas_empresas):
    """São nomes de empregados de outro cliente. É o caso simples do RGPD."""
    como("ana")
    visiveis = nomes_visiveis()
    assert {"ana", "colega"} <= visiveis
    assert "bruno_secreto" not in visiveis, "viu o pessoal da outra empresa"


def test_quem_administra_a_instalacao_continua_a_ver_todos(duas_empresas):
    """Não está no organigrama; limitá-lo à "sua" empresa deixava-o sem nada."""
    como_a_instalacao()
    assert {"ana", "colega", "bruno_secreto", "root"} <= nomes_visiveis()


def test_quem_ainda_nao_tem_lugar_continua_visivel(duas_empresas):
    """``criar`` não recebe unidade: toda a conta nasce sem lugar.

    Escondê-las tornava impossível dar o primeiro lugar a alguém acabado de
    criar — o seletor de unidades ficava vazio de propósito.
    """
    como("ana")
    assert "root" in nomes_visiveis()


def test_com_uma_empresa_so_nada_muda():
    """O isolamento começa no dia em que a segunda empresa é criada."""
    como_a_instalacao()
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    unidade = organizacao.criar("Eng", TipoUnidade.DEPARTAMENTO, acme.id)
    for nome in ("ana", "zeca"):
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="administrador")
        utilizadores.definir_unidade(nome, unidade.id)

    como("ana")
    assert {"ana", "zeca"} <= nomes_visiveis()


def test_sem_estrutura_nenhuma_nada_muda():
    for nome in ("ana", "zeca"):
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="administrador")
    como("ana")
    assert {"ana", "zeca"} <= nomes_visiveis()


# ============================ o que não se toca: a metade mais grave dos dois


@pytest.mark.parametrize(
    "o_que_faz",
    [
        pytest.param(
            lambda d: utilizadores.definir_papel("bruno_secreto", "administrador"),
            id="promover",
        ),
        pytest.param(
            lambda d: utilizadores.definir_unidade("bruno_secreto", d["acme_eng"].id),
            id="roubar_para_a_minha_empresa",
        ),
        pytest.param(
            lambda d: utilizadores.definir_ativo("bruno_secreto", False),
            id="desativar",
        ),
        pytest.param(lambda d: utilizadores.remover("bruno_secreto"), id="apagar"),
        pytest.param(
            lambda d: utilizadores.alterar_senha("bruno_secreto", "Outra-Senha-Longa-9"),
            id="repor_a_senha",
        ),
    ],
)
def test_nao_se_mexe_em_quem_e_de_outra_empresa(duas_empresas, o_que_faz):
    """Cada uma destas era possível antes. A da senha é entrar na conta."""
    como("ana")
    with pytest.raises(ContaDeOutraEmpresaError):
        o_que_faz(duas_empresas)


def test_a_conta_da_outra_empresa_fica_mesmo_intacta(duas_empresas):
    """Recusar e não fazer nada não é o mesmo que recusar e deixar feito."""
    como("ana")
    with pytest.raises(ContaDeOutraEmpresaError):
        utilizadores.definir_unidade("bruno_secreto", duas_empresas["acme_eng"].id)

    como_a_instalacao()
    bruno = utilizadores.obter("bruno_secreto")
    assert bruno is not None and bruno.ativo
    assert utilizadores.empresa_de(bruno) == duas_empresas["rival"].id


def test_tambem_nao_se_exporta_alguem_para_a_empresa_do_lado(duas_empresas):
    """Faltava metade: não mexer nos deles, e não mandar os meus para lá.

    É a mesma fuga vista do outro lado — e a que não se vê ao pensar só em
    "proteger o que é dos outros".
    """
    como("ana")
    with pytest.raises(ContaDeOutraEmpresaError):
        utilizadores.definir_unidade("colega", duas_empresas["rival_eng"].id)


def test_dentro_da_sua_empresa_continua_a_administrar(duas_empresas):
    """O isolamento não pode transformar-se em paralisia."""
    como("ana")
    assert utilizadores.definir_papel("colega", "gestor") is True
    assert utilizadores.definir_unidade("colega", duas_empresas["acme_eng"].id) is True
    assert utilizadores.definir_ativo("colega", False) is True


def test_uma_recusa_e_um_erro_e_nao_um_false(duas_empresas):
    """Um ``False`` silencioso deixava quem administra a pensar que resultou."""
    como("ana")
    with pytest.raises(ContaDeOutraEmpresaError):
        utilizadores.definir_ativo("bruno_secreto", False)


# ================================================= a trilha segue a mesma regra


def test_a_trilha_de_uma_empresa_nao_mostra_a_outra(duas_empresas):
    auditoria.ativar()
    como("bruno_secreto")
    utilizadores.definir_papel("bruno_secreto", "gestor")

    como("ana")
    utilizadores.definir_papel("colega", "gestor")

    vistos = {r.alvo for r in auditoria.consultar(limite=200)}
    assert "colega" in vistos
    assert "bruno_secreto" not in vistos, "leu a trilha da outra empresa"


def test_quem_administra_a_instalacao_le_a_trilha_toda(duas_empresas):
    auditoria.ativar()
    como("bruno_secreto")
    utilizadores.definir_papel("bruno_secreto", "gestor")
    como("ana")
    utilizadores.definir_papel("colega", "gestor")

    como_a_instalacao()
    vistos = {r.alvo for r in auditoria.consultar(limite=200)}
    assert {"colega", "bruno_secreto"} <= vistos


def test_a_empresa_fica_gravada_no_momento_em_que_se_age(duas_empresas):
    """Como a unidade da tarefa: mudar de empresa não reescreve o passado."""
    auditoria.ativar()
    como("ana")
    utilizadores.definir_papel("colega", "gestor")

    # A Ana muda-se para a Rival. O que ela fez continua a ser da Acme.
    como_a_instalacao()
    utilizadores.definir_unidade("ana", duas_empresas["rival_eng"].id)

    como("ana")
    assert organizacao.empresa_da_sessao() == duas_empresas["rival"].id
    alvos = {r.alvo for r in auditoria.consultar(limite=200)}
    assert "colega" not in alvos, "o passado da Ana mudou de empresa com ela"


def test_sem_estrutura_a_trilha_continua_inteira():
    """Uma instalação com uma empresa ou nenhuma não nota diferença nenhuma."""
    auditoria.ativar()
    utilizadores.criar("ana", "Uma-Senha-Longa-123", papel="administrador")
    como("ana")
    utilizadores.criar("zeca", "Uma-Senha-Longa-123", papel="colaborador")

    assert {r.alvo for r in auditoria.consultar(limite=50)} >= {"zeca"}
