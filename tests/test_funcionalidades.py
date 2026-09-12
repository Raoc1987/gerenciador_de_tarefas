"""O que esta instalação inclui — e porque não é a mesma coisa que permissões.

Duas maneiras de esta peça correr mal: virar um segundo sistema de permissões
(e ficarem duas respostas para a mesma pergunta, a discordar uma da outra), e
desligar coisas em silêncio por causa de um erro de escrita numa chave.
"""

import pytest

from core import config, eventos, funcionalidades, permissoes
from core.funcionalidades import (
    CATALOGO,
    FuncionalidadeDesconhecidaError,
    FuncionalidadeDesligadaError,
)
from core.permissoes import PermissaoNegadaError


def como(papel: str = "administrador", utilizador: str = "ana") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


@pytest.fixture(autouse=True)
def sessao_de_admin():
    como()


# ================================================================ CATÁLOGO


def test_tudo_nasce_ligado():
    """Instalar a versão nova não pode tirar nada a ninguém."""
    assert all(estado.ativa for estado in funcionalidades.listar())


def test_nada_esta_decidido_a_partida():
    assert not any(estado.decidida for estado in funcionalidades.listar())


def test_o_catalogo_e_a_lista_completa():
    chaves = {estado.chave for estado in funcionalidades.listar()}
    assert chaves == set(CATALOGO)


def test_o_que_ficou_de_fora_ficou_de_proposito():
    """As tarefas, as contas, os plugins e a auditoria não são opcionais.

    Se este teste falhar porque alguém acrescentou uma destas ao catálogo, a
    pergunta é se a instalação faz sentido sem isso. Para a auditoria a
    resposta está no módulo: parar de registar é uma decisão de conformidade,
    não uma preferência.
    """
    assert "tarefas" not in CATALOGO
    assert "utilizadores" not in CATALOGO
    assert "plugins" not in CATALOGO
    assert "auditoria" not in CATALOGO


def test_a_copia_de_seguranca_e_essencial():
    """Uma opção que deixa ficar sem rede de proteção não é uma opção."""
    assert CATALOGO["copia_seguranca"].essencial
    with pytest.raises(ValueError, match="essencial"):
        funcionalidades.definir("copia_seguranca", False)
    assert funcionalidades.ativa("copia_seguranca")


# ======================================================= CHAVES DESCONHECIDAS


def test_perguntar_por_uma_chave_inventada_levanta_erro():
    """Responder "desligada" a um erro de escrita desligaria coisas em silêncio."""
    with pytest.raises(FuncionalidadeDesconhecidaError):
        funcionalidades.ativa("painell")


def test_o_erro_diz_quais_existem():
    with pytest.raises(FuncionalidadeDesconhecidaError) as erro:
        funcionalidades.ativa("inventada")
    assert "painel" in str(erro.value)


def test_definir_uma_chave_inventada_levanta_erro():
    with pytest.raises(FuncionalidadeDesconhecidaError):
        funcionalidades.definir("inventada", False)


# ================================================================== DECIDIR


def test_desligar_e_ler_de_volta():
    assert funcionalidades.definir("painel", False) is True
    assert funcionalidades.ativa("painel") is False


def test_a_decisao_sobrevive_ao_reinicio():
    """É configuração persistida, não estado em memória.

    Verificado no ficheiro e não só pela API: se a decisão vivesse em memória,
    a leitura de volta passava na mesma e o teste não dizia nada.
    """
    import json

    funcionalidades.definir("relatorios", False)

    guardado = json.loads(config.caminho_config_app().read_text(encoding="utf-8"))
    assert guardado[funcionalidades.CHAVE_CONFIG]["relatorios"] is False
    assert funcionalidades.ativa("relatorios") is False


def test_voltar_a_ligar():
    funcionalidades.definir("painel", False)
    assert funcionalidades.definir("painel", True) is True
    assert funcionalidades.ativa("painel") is True


def test_decidir_o_mesmo_duas_vezes_nao_muda_nada():
    funcionalidades.definir("painel", False)
    assert funcionalidades.definir("painel", False) is False


def test_a_decisao_fica_marcada_como_decidida():
    funcionalidades.definir("painel", True)
    estado = next(e for e in funcionalidades.listar() if e.chave == "painel")
    assert estado.decidida is True
    assert estado.ativa is True


def test_repor_uma_funcionalidade():
    funcionalidades.definir("painel", False)
    funcionalidades.repor("painel")
    assert funcionalidades.ativa("painel") is True
    assert not next(e for e in funcionalidades.listar() if e.chave == "painel").decidida


def test_repor_tudo():
    funcionalidades.definir("painel", False)
    funcionalidades.definir("relatorios", False)
    funcionalidades.repor()
    assert all(e.ativa and not e.decidida for e in funcionalidades.listar())


def test_lixo_na_configuracao_e_ignorado():
    """Um ficheiro editado à mão não pode impedir a aplicação de arrancar."""
    config.definir(
        funcionalidades.CHAVE_CONFIG,
        {"painel": "talvez", "inventada": True, "relatorios": False},
    )
    assert funcionalidades.ativa("painel") is True, "valor inválido: vale o de origem"
    assert funcionalidades.ativa("relatorios") is False


def test_a_configuracao_com_o_tipo_errado_e_ignorada():
    config.definir(funcionalidades.CHAVE_CONFIG, "isto devia ser um objeto")
    assert funcionalidades.ativa("painel") is True


# ============================================================== QUEM DECIDE


@pytest.mark.parametrize("papel", ["colaborador", "gestor", "supervisor", "visualizador"])
def test_so_quem_administra_decide(papel):
    como(papel)
    with pytest.raises(PermissaoNegadaError):
        funcionalidades.definir("painel", False)
    assert funcionalidades.ativa("painel") is True


def test_ler_nao_exige_permissao():
    """O código pergunta isto em todo o lado, incluindo antes de haver sessão."""
    permissoes.terminar_sessao()
    assert funcionalidades.ativa("painel") is True


def test_repor_tambem_exige_administrador():
    como("gestor")
    with pytest.raises(PermissaoNegadaError):
        funcionalidades.repor()


# ============================================== NÃO É UM SISTEMA DE PERMISSÕES


def test_uma_funcionalidade_desligada_fecha_a_porta_a_toda_a_gente():
    """Nem o administrador escapa: a instalação não tem a funcionalidade."""
    funcionalidades.definir("relatorios", False)
    como("administrador")
    with pytest.raises(FuncionalidadeDesligadaError):
        funcionalidades.exigir("relatorios")


def test_exigir_deixa_passar_quando_esta_ligada():
    assert funcionalidades.exigir("painel") is None


def test_as_duas_perguntas_sao_independentes():
    """Ter permissão não liga a funcionalidade; tê-la ligada não dá permissão."""
    from core.permissoes import Permissao

    funcionalidades.definir("relatorios", False)
    como("administrador")
    assert permissoes.pode(Permissao.RELATORIOS_EXPORTAR) is True
    assert funcionalidades.ativa("relatorios") is False

    funcionalidades.definir("relatorios", True)
    como("visualizador")
    assert funcionalidades.ativa("relatorios") is True
    assert permissoes.pode(Permissao.RELATORIOS_EXPORTAR) is False


# ================================================== ONDE ISTO É MESMO APLICADO


def test_exportar_um_relatorio_e_recusado_com_a_funcionalidade_desligada(tmp_path):
    """Esconder o botão não chega: um plugin chega aqui por outro caminho."""
    from reporting.modelo import Relatorio
    from reporting.servico import exportar

    funcionalidades.definir("relatorios", False)
    with pytest.raises(FuncionalidadeDesligadaError):
        exportar(Relatorio(titulo="Teste"), tmp_path / "r.csv")
    assert not (tmp_path / "r.csv").exists()


def test_a_funcionalidade_e_verificada_antes_da_permissao(tmp_path):
    """Primeiro "a instalação tem isto?", depois "e esta pessoa pode?".

    Ao contrário, quem não tem permissão receberia "não pode" sobre uma coisa
    que a instalação nem sequer inclui.
    """
    from reporting.modelo import Relatorio
    from reporting.servico import exportar

    funcionalidades.definir("relatorios", False)
    como("visualizador")  # não tem relatorios.exportar
    with pytest.raises(FuncionalidadeDesligadaError):
        exportar(Relatorio(titulo="Teste"), tmp_path / "r.csv")


def test_exportar_funciona_quando_esta_ligada(tmp_path):
    from reporting.modelo import Lista, Relatorio
    from reporting.servico import exportar

    relatorio = Relatorio(titulo="Teste", secoes=[Lista(titulo="S", itens=["x"])])
    assert exportar(relatorio, tmp_path / "r.csv").is_file()


# ==================================================================== EVENTOS


def test_alterar_publica_um_evento():
    recebidos = []
    eventos.subscrever(eventos.FUNCIONALIDADE_ALTERADA, recebidos.append)

    funcionalidades.definir("painel", False)
    assert len(recebidos) == 1
    assert recebidos[0].dados["id"] == "painel"
    assert recebidos[0].dados["ligada"] is False


def test_uma_alteracao_recusada_nao_publica_nada():
    recebidos = []
    eventos.subscrever(eventos.FUNCIONALIDADE_ALTERADA, recebidos.append)

    como("colaborador")
    with pytest.raises(PermissaoNegadaError):
        funcionalidades.definir("painel", False)
    assert recebidos == []


def test_ligar_e_desligar_fica_na_auditoria():
    """Muda o que toda a gente vê: tem de ficar registado."""
    from core import auditoria

    auditoria.ativar()
    funcionalidades.definir("painel", False)

    registos = [
        r for r in auditoria.consultar() if r.evento == eventos.FUNCIONALIDADE_ALTERADA
    ]
    assert len(registos) == 1
    assert registos[0].alvo == "painel"
