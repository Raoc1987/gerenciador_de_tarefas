"""Testes dos papéis e permissões."""

import pytest

from core import config, permissoes
from core.permissoes import PermissaoNegadaError, Permissao


def test_sessao_padrao_e_administrador():
    atual = permissoes.sessao()
    assert atual.papel.nome == "administrador"
    assert atual.pode(Permissao.SISTEMA_ADMIN)


def test_administrador_pode_tudo():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    for permissao in Permissao:
        assert permissoes.pode(permissao), permissao


def test_colaborador_tem_acesso_limitado():
    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    assert permissoes.pode(Permissao.TAREFAS_LER)
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER)
    assert not permissoes.pode(Permissao.PLUGINS_GERIR)
    assert not permissoes.pode(Permissao.RELATORIOS_EXPORTAR)
    assert not permissoes.pode(Permissao.SISTEMA_ADMIN)


def test_visualizador_nao_escreve():
    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    assert permissoes.pode(Permissao.TAREFAS_LER)
    assert permissoes.pode(Permissao.ANALYTICS_LER)
    assert not permissoes.pode(Permissao.TAREFAS_ESCREVER)


def test_gestor_gere_plugins_mas_nao_e_admin():
    permissoes.definir_sessao("diogo", "gestor", persistir=False)
    assert permissoes.pode(Permissao.PLUGINS_GERIR)
    assert permissoes.pode(Permissao.RELATORIOS_EXPORTAR)
    assert not permissoes.pode(Permissao.UTILIZADORES_GERIR)


def test_exigir_deixa_passar_quando_ha_permissao():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    permissoes.exigir(Permissao.PLUGINS_GERIR)  # não levanta


def test_exigir_levanta_quando_falta_permissao():
    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    with pytest.raises(PermissaoNegadaError) as erro:
        permissoes.exigir(Permissao.PLUGINS_GERIR)
    assert erro.value.permissao == Permissao.PLUGINS_GERIR
    assert erro.value.chave_mensagem == "permissao_negada"
    assert "plugins.gerir" in str(erro.value)


def test_permissoes_em_falta():
    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    faltam = permissoes.permissoes_em_falta(
        [Permissao.TAREFAS_LER, Permissao.PLUGINS_GERIR, Permissao.SISTEMA_ADMIN]
    )
    assert faltam == frozenset({Permissao.PLUGINS_GERIR, Permissao.SISTEMA_ADMIN})


def test_papel_desconhecido_cai_no_padrao():
    sessao = permissoes.definir_sessao("eva", "papel_que_nao_existe", persistir=False)
    assert sessao.papel.nome == permissoes.PAPEL_PADRAO


def test_sessao_e_persistida_e_restaurada():
    permissoes.definir_sessao("filipa", "supervisor")
    assert config.obter("papel") == "supervisor"
    assert config.obter("utilizador") == "filipa"

    permissoes.terminar_sessao()
    restaurada = permissoes.sessao()
    assert restaurada.utilizador == "filipa"
    assert restaurada.papel.nome == "supervisor"


def test_sessao_sem_persistir_nao_altera_a_configuracao():
    permissoes.definir_sessao("gil", "colaborador", persistir=False)
    assert config.obter("papel") is None


def test_permissoes_efetivas_do_administrador():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    assert permissoes.sessao().permissoes() == frozenset(Permissao)


def test_permissoes_efetivas_de_papel_limitado():
    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    assert permissoes.sessao().permissoes() == frozenset(
        {Permissao.TAREFAS_LER, Permissao.TAREFAS_ESCREVER}
    )


def test_todos_os_papeis_tem_permissoes_validas():
    for nome, papel in permissoes.PAPEIS.items():
        assert papel.nome == nome
        assert papel.permissoes, f"o papel {nome} não concede nada"
        for permissao in papel.permissoes:
            assert isinstance(permissao, Permissao)


def test_nomes_das_permissoes_seguem_area_ponto_acao():
    for permissao in Permissao:
        assert permissao.value.count(".") == 1, permissao
        area, acao = permissao.value.split(".")
        assert area and acao
