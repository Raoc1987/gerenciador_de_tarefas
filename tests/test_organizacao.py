"""A estrutura da empresa, e as regras que a impedem de ficar impossível.

Uma árvore mal guardada não dá erro: dá respostas erradas em silêncio. Um
ciclo faz uma travessia nunca acabar; dois irmãos com o mesmo nome fazem
alguém escolher a unidade errada; uma empresa com pai deixa de ser uma
empresa. Estes testes existem para nenhuma dessas coisas ser possível.
"""

import pytest

from core import eventos, organizacao
from core.organizacao import (
    EstruturaInvalidaError,
    NomeDuplicadoError,
    TipoUnidade,
    UnidadeComConteudoError,
    UnidadeNaoEncontradaError,
)


@pytest.fixture
def acme():
    """Uma estrutura pequena mas com três níveis e um ramo paralelo.

        Acme
        +- Engenharia
        |  +- Plataforma
        |  +- Produto
        +- Financeiro
    """
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    engenharia = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, empresa.id)
    financeiro = organizacao.criar("Financeiro", TipoUnidade.DEPARTAMENTO, empresa.id)
    plataforma = organizacao.criar("Plataforma", TipoUnidade.EQUIPA, engenharia.id)
    produto = organizacao.criar("Produto", TipoUnidade.EQUIPA, engenharia.id)
    return {
        "empresa": empresa,
        "engenharia": engenharia,
        "financeiro": financeiro,
        "plataforma": plataforma,
        "produto": produto,
    }


# ============================================================== ESTADO VAZIO


def test_sem_estrutura_nada_rebenta():
    """Quem não usa organização nenhuma não tem de a criar."""
    assert organizacao.listar() == []
    assert organizacao.raizes() == []
    assert organizacao.obter(1) is None
    assert organizacao.caminho(1) == ""
    assert organizacao.empresa_de(1) is None


def test_pedir_uma_unidade_que_nao_existe():
    with pytest.raises(UnidadeNaoEncontradaError):
        organizacao.exigir(999)


# ================================================================== CRIAÇÃO


def test_criar_uma_empresa():
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    assert empresa.e_raiz
    assert empresa.ativa
    assert empresa.tipo == TipoUnidade.EMPRESA
    assert organizacao.raizes() == [empresa]


def test_uma_empresa_nao_tem_nada_acima(acme):
    with pytest.raises(EstruturaInvalidaError, match="acima"):
        organizacao.criar("Filial", TipoUnidade.EMPRESA, acme["empresa"].id)


def test_uma_sub_unidade_tem_de_pertencer_a_alguma_coisa():
    with pytest.raises(EstruturaInvalidaError, match="pertencer"):
        organizacao.criar("Órfã", TipoUnidade.DEPARTAMENTO)


def test_nao_se_pendura_numa_unidade_inexistente():
    with pytest.raises(UnidadeNaoEncontradaError):
        organizacao.criar("Equipa", TipoUnidade.EQUIPA, 999)


def test_dois_irmaos_nao_podem_ter_o_mesmo_nome(acme):
    with pytest.raises(NomeDuplicadoError):
        organizacao.criar("Plataforma", TipoUnidade.EQUIPA, acme["engenharia"].id)


def test_o_nome_repetido_e_recusado_sem_olhar_a_maiusculas(acme):
    with pytest.raises(NomeDuplicadoError):
        organizacao.criar("PLATAFORMA", TipoUnidade.EQUIPA, acme["engenharia"].id)


def test_o_mesmo_nome_noutro_sitio_e_permitido(acme):
    """"Plataforma" em Engenharia e em Financeiro são equipas diferentes."""
    outra = organizacao.criar("Plataforma", TipoUnidade.EQUIPA, acme["financeiro"].id)
    assert outra.id != acme["plataforma"].id


def test_duas_empresas_com_o_mesmo_nome_sao_recusadas(acme):
    with pytest.raises(NomeDuplicadoError):
        organizacao.criar("Acme", TipoUnidade.EMPRESA)


@pytest.mark.parametrize("vazio", ["", "   ", None])
def test_uma_unidade_precisa_de_nome(acme, vazio):
    with pytest.raises(ValueError):
        organizacao.criar(vazio, TipoUnidade.EQUIPA, acme["engenharia"].id)


def test_o_nome_e_guardado_sem_espaços_a_mais(acme):
    unidade = organizacao.criar("  Dados  ", TipoUnidade.EQUIPA, acme["engenharia"].id)
    assert unidade.nome == "Dados"


# ================================================================ TRAVESSIA


def test_filhos_sao_so_os_diretos(acme):
    nomes = [u.nome for u in organizacao.filhos(acme["empresa"].id)]
    assert nomes == ["Engenharia", "Financeiro"]
    assert "Plataforma" not in nomes


def test_descendentes_apanham_a_arvore_toda(acme):
    nomes = {u.nome for u in organizacao.descendentes(acme["empresa"].id)}
    assert nomes == {"Acme", "Engenharia", "Financeiro", "Plataforma", "Produto"}


def test_descendentes_sem_a_propria(acme):
    nomes = {
        u.nome
        for u in organizacao.descendentes(acme["engenharia"].id, incluir_propria=False)
    }
    assert nomes == {"Plataforma", "Produto"}


def test_descendentes_de_uma_folha(acme):
    assert [u.nome for u in organizacao.descendentes(acme["plataforma"].id)] == [
        "Plataforma"
    ]


def test_ancestrais_vao_da_raiz_ate_ao_pai(acme):
    nomes = [u.nome for u in organizacao.ancestrais(acme["plataforma"].id)]
    assert nomes == ["Acme", "Engenharia"]


def test_a_raiz_nao_tem_ancestrais(acme):
    assert organizacao.ancestrais(acme["empresa"].id) == []


def test_caminho_legivel(acme):
    assert organizacao.caminho(acme["plataforma"].id) == "Acme > Engenharia > Plataforma"
    assert organizacao.caminho(acme["empresa"].id) == "Acme"


def test_empresa_de_qualquer_nivel(acme):
    for chave in ("empresa", "engenharia", "plataforma"):
        assert organizacao.empresa_de(acme[chave].id).id == acme["empresa"].id


def test_esta_sob_atravessa_niveis(acme):
    assert organizacao.esta_sob(acme["plataforma"].id, acme["empresa"].id)
    assert organizacao.esta_sob(acme["plataforma"].id, acme["engenharia"].id)
    assert not organizacao.esta_sob(acme["plataforma"].id, acme["financeiro"].id)


def test_uma_unidade_esta_sob_si_propria(acme):
    """Quem manda numa unidade manda nela, não só no que está abaixo."""
    assert organizacao.esta_sob(acme["engenharia"].id, acme["engenharia"].id)


# ==================================================================== MOVER


def test_mover_leva_a_sub_arvore_atras(acme):
    """Mover Engenharia leva Plataforma e Produto com ela."""
    outra = organizacao.criar("Holding", TipoUnidade.EMPRESA)
    organizacao.mover(acme["engenharia"].id, outra.id)

    assert organizacao.empresa_de(acme["plataforma"].id).id == outra.id
    assert organizacao.caminho(acme["plataforma"].id) == "Holding > Engenharia > Plataforma"


def test_uma_unidade_nao_pode_ficar_debaixo_de_si_propria(acme):
    with pytest.raises(EstruturaInvalidaError, match="si própria"):
        organizacao.mover(acme["engenharia"].id, acme["engenharia"].id)


def test_nao_se_pode_mover_um_pai_para_dentro_de_um_filho(acme):
    """O ciclo indireto é o que passa despercebido, e é o que parte a árvore."""
    with pytest.raises(EstruturaInvalidaError):
        organizacao.mover(acme["engenharia"].id, acme["plataforma"].id)


def test_um_ciclo_recusado_nao_deixa_a_arvore_mexida(acme):
    with pytest.raises(EstruturaInvalidaError):
        organizacao.mover(acme["empresa"].id, acme["produto"].id)
    assert organizacao.obter(acme["empresa"].id).pai_id is None
    assert organizacao.caminho(acme["produto"].id) == "Acme > Engenharia > Produto"


def test_mover_para_onde_ja_ha_esse_nome_e_recusado(acme):
    organizacao.criar("Produto", TipoUnidade.EQUIPA, acme["financeiro"].id)
    with pytest.raises(NomeDuplicadoError):
        organizacao.mover(acme["produto"].id, acme["financeiro"].id)


def test_uma_empresa_nao_se_move_para_dentro_de_nada(acme):
    with pytest.raises(EstruturaInvalidaError):
        organizacao.mover(acme["empresa"].id, acme["financeiro"].id)


# ================================================================ RENOMEAR


def test_renomear(acme):
    renomeada = organizacao.renomear(acme["plataforma"].id, "Infraestrutura")
    assert renomeada.nome == "Infraestrutura"
    assert renomeada.pai_id == acme["engenharia"].id


def test_renomear_para_o_nome_de_um_irmao_e_recusado(acme):
    with pytest.raises(NomeDuplicadoError):
        organizacao.renomear(acme["plataforma"].id, "Produto")


def test_renomear_para_o_proprio_nome_funciona(acme):
    """Não se pode tropeçar na verificação de duplicados por causa de si mesmo."""
    assert organizacao.renomear(acme["plataforma"].id, "Plataforma").nome == "Plataforma"


# ============================================================ ATIVA/INATIVA


def test_desativar_esconde_sem_apagar(acme):
    organizacao.definir_ativa(acme["produto"].id, False)

    visiveis = {u.nome for u in organizacao.listar()}
    assert "Produto" not in visiveis
    assert organizacao.obter(acme["produto"].id) is not None
    assert "Produto" in {u.nome for u in organizacao.listar(incluir_inativas=True)}


def test_uma_unidade_inativa_nao_aparece_nos_descendentes(acme):
    organizacao.definir_ativa(acme["produto"].id, False)
    nomes = {u.nome for u in organizacao.descendentes(acme["empresa"].id)}
    assert "Produto" not in nomes


def test_reativar(acme):
    organizacao.definir_ativa(acme["produto"].id, False)
    assert organizacao.definir_ativa(acme["produto"].id, True).ativa
    assert "Produto" in {u.nome for u in organizacao.listar()}


# =================================================================== REMOVER


def test_remover_uma_folha(acme):
    organizacao.remover(acme["produto"].id)
    assert organizacao.obter(acme["produto"].id) is None


def test_nao_se_remove_uma_unidade_com_sub_unidades(acme):
    """Apagar em cascata a empresa toda nunca é o que alguém queria num clique."""
    with pytest.raises(UnidadeComConteudoError):
        organizacao.remover(acme["engenharia"].id)
    assert organizacao.obter(acme["plataforma"].id) is not None


def test_nem_sequer_as_inativas_deixam_remover_o_pai(acme):
    """Uma sub-unidade escondida continua a ser uma sub-unidade."""
    organizacao.definir_ativa(acme["plataforma"].id, False)
    organizacao.remover(acme["produto"].id)
    with pytest.raises(UnidadeComConteudoError):
        organizacao.remover(acme["engenharia"].id)


# ==================================================================== EVENTOS


def test_mexer_na_estrutura_publica_eventos(acme):
    recebidos = []
    eventos.subscrever("unidade.*", recebidos.append)

    unidade = organizacao.criar("Dados", TipoUnidade.EQUIPA, acme["engenharia"].id)
    organizacao.renomear(unidade.id, "Dados e IA")
    organizacao.mover(unidade.id, acme["financeiro"].id)
    organizacao.remover(unidade.id)

    assert [e.nome for e in recebidos] == [
        eventos.UNIDADE_CRIADA,
        eventos.UNIDADE_ALTERADA,
        eventos.UNIDADE_ALTERADA,
        eventos.UNIDADE_REMOVIDA,
    ]


def test_a_estrutura_fica_na_auditoria(acme):
    """Mexer em quem está sob quem muda quem vê o quê: tem de ficar registado."""
    from core import auditoria

    auditoria.ativar()
    organizacao.criar("Dados", TipoUnidade.EQUIPA, acme["engenharia"].id)

    registos = [r for r in auditoria.consultar() if r.evento == eventos.UNIDADE_CRIADA]
    assert len(registos) == 1


def test_uma_operacao_recusada_nao_publica_nada(acme):
    recebidos = []
    eventos.subscrever("unidade.*", recebidos.append)

    with pytest.raises(NomeDuplicadoError):
        organizacao.criar("Produto", TipoUnidade.EQUIPA, acme["engenharia"].id)
    with pytest.raises(EstruturaInvalidaError):
        organizacao.mover(acme["engenharia"].id, acme["plataforma"].id)

    assert recebidos == []
