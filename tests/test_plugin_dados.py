"""Cada plugin guarda os seus dados, e só os seus.

Um módulo de negócio precisa de tabelas. Dar-lhe o banco da aplicação seria
voltar ao monólito: uma migração mal escrita de um plugin de terceiros levaria
as tarefas de alguém. Cada plugin tem o seu ficheiro.
"""

import logging
import sqlite3

import pytest

from core.plugin_api import ContextoPlugin, ManifestoPlugin
from core.plugin_dados import NOME_FICHEIRO, ArmazenamentoPlugin

CRIAR_ITENS = "CREATE TABLE itens (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)"


@pytest.fixture
def dados(tmp_path) -> ArmazenamentoPlugin:
    return ArmazenamentoPlugin("estoque", tmp_path)


def contexto_de(plugin_id: str, pasta) -> ContextoPlugin:
    return ContextoPlugin(
        manifesto=ManifestoPlugin.de_dicionario(
            {
                "id": plugin_id,
                "name": plugin_id,
                "version": "1.0.0",
                "entry_point": "plugin.py",
                "min_app_version": "1.0.0",
            }
        ),
        app_version="1.0.0",
        diretorio_plugin=pasta,
        diretorio_dados=pasta,
        logger=logging.getLogger(f"teste.{plugin_id}"),
    )


# ============================================================== PREGUIÇA


def test_quem_nao_guarda_nada_nao_deixa_ficheiro(dados, tmp_path):
    """Ter a capacidade não é usá-la."""
    assert not dados.existe
    assert dados.versao() == 0
    assert dados.consultar("SELECT 1") == []
    assert not (tmp_path / NOME_FICHEIRO).exists()


def test_o_ficheiro_nasce_na_primeira_escrita(dados):
    dados.migrar(1, CRIAR_ITENS)
    assert dados.existe
    assert dados.caminho.name == NOME_FICHEIRO


# ============================================================== ESQUEMA


def test_uma_migracao_aplicada_nao_volta_a_correr(dados):
    assert dados.migrar(1, CRIAR_ITENS) is True
    # Se corresse outra vez, isto rebentava — é essa a prova.
    assert dados.migrar(1, "isto não é SQL") is False
    assert dados.versao() == 1


def test_o_esquema_evolui_por_passos(dados):
    dados.migrar(1, CRIAR_ITENS)
    dados.migrar(2, "ALTER TABLE itens ADD COLUMN quantidade INTEGER DEFAULT 0")
    dados.executar("INSERT INTO itens (nome, quantidade) VALUES (?, ?)", ("Parafuso", 7))
    assert dados.consultar_um("SELECT quantidade FROM itens") == (7,)
    assert dados.versao() == 2


def test_um_passo_falhado_nao_fica_a_meio(dados):
    """Ou o passo inteiro é aplicado, ou o esquema não avança."""
    dados.migrar(1, CRIAR_ITENS)
    with pytest.raises(sqlite3.Error):
        dados.migrar(2, "ALTER TABLE itens ADD COLUMN cor TEXT", "SQL INVÁLIDO AQUI")
    assert dados.versao() == 1, "a versão não pode avançar com o passo incompleto"
    colunas = [c[1] for c in dados.consultar("PRAGMA table_info(itens)")]
    assert "cor" not in colunas


@pytest.mark.parametrize("versao", [0, -1, 1.5, "1"])
def test_versao_invalida_e_recusada(dados, versao):
    with pytest.raises(ValueError):
        dados.migrar(versao, CRIAR_ITENS)


# ============================================================== ISOLAMENTO


def test_dois_plugins_nao_se_veem(tmp_path):
    """O mesmo nome de tabela nos dois, sem colisão."""
    estoque = ArmazenamentoPlugin("estoque", tmp_path / "estoque")
    (tmp_path / "estoque").mkdir()
    rh = ArmazenamentoPlugin("rh", tmp_path / "rh")
    (tmp_path / "rh").mkdir()

    for armazem, valor in ((estoque, "Parafuso"), (rh, "Contrato")):
        armazem.migrar(1, CRIAR_ITENS)
        armazem.executar("INSERT INTO itens (nome) VALUES (?)", (valor,))

    assert estoque.consultar("SELECT nome FROM itens") == [("Parafuso",)]
    assert rh.consultar("SELECT nome FROM itens") == [("Contrato",)]
    assert estoque.caminho != rh.caminho


def test_um_plugin_nao_alcanca_o_banco_da_aplicacao(tmp_path):
    """As tarefas não estão ao alcance de um SELECT do plugin."""
    import database

    database.criar_tabela()
    database.adicionar_tarefa("Tarefa da aplicação", "2030-01-01")

    dados = ArmazenamentoPlugin("intrometido", tmp_path)
    dados.migrar(1, CRIAR_ITENS)
    with pytest.raises(sqlite3.OperationalError, match="tarefas"):
        dados.consultar("SELECT * FROM tarefas")


def test_o_caminho_vem_do_id_e_nao_do_plugin(tmp_path):
    """O plugin não escolhe onde grava — recebe o sítio já decidido."""
    dados = ArmazenamentoPlugin("estoque", tmp_path)
    assert dados.caminho.parent == tmp_path
    assert dados.caminho.name == NOME_FICHEIRO


# ============================================================== TRANSAÇÕES


def test_uma_escrita_que_falha_nao_deixa_metade(dados):
    dados.migrar(1, CRIAR_ITENS)
    dados.executar("INSERT INTO itens (nome) VALUES (?)", ("Bom",))

    with pytest.raises(sqlite3.Error):
        with dados.conectar() as conexao:
            conexao.execute("INSERT INTO itens (nome) VALUES (?)", ("Perdido",))
            conexao.execute("INSERT INTO inexistente VALUES (1)")

    assert dados.consultar("SELECT nome FROM itens") == [("Bom",)]


def test_escrever_muitos_de_uma_vez(dados):
    dados.migrar(1, CRIAR_ITENS)
    inseridas = dados.executar_muitos(
        "INSERT INTO itens (nome) VALUES (?)", [("A",), ("B",), ("C",)]
    )
    assert inseridas == 3
    assert len(dados.consultar("SELECT nome FROM itens")) == 3


def test_executar_devolve_o_id_do_que_inseriu(dados):
    dados.migrar(1, CRIAR_ITENS)
    primeiro = dados.executar("INSERT INTO itens (nome) VALUES (?)", ("A",))
    segundo = dados.executar("INSERT INTO itens (nome) VALUES (?)", ("B",))
    assert segundo == primeiro + 1


# ============================================================== CONTEXTO


def test_o_contexto_entrega_sempre_o_mesmo_armazem(tmp_path):
    contexto = contexto_de("estoque", tmp_path)
    assert contexto.dados is contexto.dados


def test_o_armazem_sabe_de_quem_e(tmp_path):
    contexto = contexto_de("estoque", tmp_path)
    contexto.dados.migrar(1, CRIAR_ITENS)
    assert (tmp_path / NOME_FICHEIRO).exists()
    assert "estoque" in repr(contexto.dados)


def test_guardar_dados_nao_exige_permissao(tmp_path):
    """São os dados do próprio plugin: não há nada a pedir ao utilizador."""
    contexto = contexto_de("estoque", tmp_path)
    assert contexto.permissoes == frozenset()
    contexto.dados.migrar(1, CRIAR_ITENS)
    contexto.dados.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))
    assert contexto.dados.consultar("SELECT nome FROM itens") == [("Parafuso",)]


# ====================================================== CICLO DE VIDA


def test_remover_o_plugin_leva_os_dados_dele(gerenciador, criar_plugin):
    """Desinstalar com os dados não pode deixar o ficheiro para trás."""
    from core.paths import diretorio_dados_plugin

    criar_plugin("estoque")
    gerenciador.descobrir()

    armazem = ArmazenamentoPlugin("estoque", diretorio_dados_plugin("estoque"))
    armazem.migrar(1, CRIAR_ITENS)
    armazem.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))
    assert armazem.existe

    assert gerenciador.remover("estoque", remover_dados=True).sucesso
    assert not armazem.existe


def test_remover_sem_apagar_dados_preserva_o_ficheiro(gerenciador, criar_plugin):
    """Reinstalar tem de encontrar o que lá estava — é a promessa ao utilizador."""
    from core.paths import diretorio_dados_plugin

    criar_plugin("estoque")
    gerenciador.descobrir()

    armazem = ArmazenamentoPlugin("estoque", diretorio_dados_plugin("estoque"))
    armazem.migrar(1, CRIAR_ITENS)
    armazem.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))

    assert gerenciador.remover("estoque").sucesso
    assert armazem.existe
    assert armazem.consultar("SELECT nome FROM itens") == [("Parafuso",)]


def test_remover_um_plugin_nao_toca_nas_tarefas(gerenciador, criar_plugin):
    import database

    database.criar_tabela()
    database.adicionar_tarefa("Continua aqui", "2030-01-01")

    criar_plugin("estoque")
    gerenciador.descobrir()
    gerenciador.remover("estoque", remover_dados=True)

    assert [t[1] for t in database.buscar_tarefas()] == ["Continua aqui"]
