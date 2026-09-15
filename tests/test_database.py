"""Testes da camada de persistência de tarefas."""

import sqlite3

import pytest

import database as db
import main


def test_criar_tabela_e_idempotencia(dados_isolados):
    db.criar_tabela()
    db.criar_tabela()  # não deve falhar nem duplicar
    assert db.caminho_bd().exists()
    with db.conectar() as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] >= 1


def test_banco_fica_no_diretorio_de_dados(dados_isolados):
    db.criar_tabela()
    assert db.caminho_bd().parent == dados_isolados


def test_adicionar_e_buscar():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Estudar Python", "2026-01-15")
    tarefas = db.buscar_tarefas()
    assert len(tarefas) == 1
    assert tarefas[0][0] == tarefa_id
    # gui.py depende de a descrição estar no índice 1
    assert tarefas[0][1] == "Estudar Python"
    assert tarefas[0][2] == "2026-01-15"
    assert tarefas[0][3] == 0


def test_descricao_vazia_e_rejeitada():
    db.criar_tabela()
    with pytest.raises(ValueError):
        db.adicionar_tarefa("   ")


def test_descricao_e_normalizada():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("  com espaços  ")
    assert db.obter_tarefa(tarefa_id)[1] == "com espaços"


def test_concluir_e_reabrir():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Lavar o carro")
    assert db.concluir_tarefa(tarefa_id) is True
    assert db.obter_tarefa(tarefa_id)[3] == 1
    assert db.buscar_tarefas(incluir_concluidas=False) == []
    db.concluir_tarefa(tarefa_id, False)
    assert db.obter_tarefa(tarefa_id)[3] == 0


def test_concluir_inexistente():
    db.criar_tabela()
    assert db.concluir_tarefa(9999) is False


def test_remover():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Temporária")
    assert db.remover_tarefa(tarefa_id) is True
    assert db.remover_tarefa(tarefa_id) is False
    assert db.buscar_tarefas() == []


def test_obter_tarefa_inexistente():
    db.criar_tabela()
    assert db.obter_tarefa(4242) is None


def test_tarefas_por_data():
    db.criar_tabela()
    db.adicionar_tarefa("Dia certo", "2026-03-01")
    db.adicionar_tarefa("Outro dia", "2026-03-02")
    db.adicionar_tarefa("Sem data")
    encontradas = db.tarefas_por_data("2026-03-01")
    assert [t[1] for t in encontradas] == ["Dia certo"]


def test_ordem_pendentes_antes_de_concluidas():
    db.criar_tabela()
    primeira = db.adicionar_tarefa("Primeira")
    db.adicionar_tarefa("Segunda")
    db.concluir_tarefa(primeira)
    assert [t[1] for t in db.buscar_tarefas()] == ["Segunda", "Primeira"]


def test_dados_sobrevivem_a_nova_conexao():
    db.criar_tabela()
    db.adicionar_tarefa("Persistente")
    # cada chamada abre e fecha a sua própria conexão
    assert [t[1] for t in db.buscar_tarefas()] == ["Persistente"]


def test_rollback_em_erro():
    db.criar_tabela()
    db.adicionar_tarefa("Antes do erro")
    with pytest.raises(sqlite3.OperationalError):
        with db.conectar() as conexao:
            conexao.execute(
                "INSERT INTO tarefas (descricao, criada_em) VALUES ('x', 'y')"
            )
            conexao.execute("SELECT * FROM tabela_inexistente")
    assert [t[1] for t in db.buscar_tarefas()] == ["Antes do erro"]


# ================================================ DIAGNÓSTICO DO BANCO


def test_verificar_banco_diz_que_esta_intacto(capsys):
    db.criar_tabela()
    db.adicionar_tarefa("Tarefa")

    assert main.verificar_banco() == 0
    saida = capsys.readouterr().out
    assert "integrity_check: ok" in saida
    assert "BANCO OK" in saida


def test_verificar_banco_mostra_a_versao_do_schema(capsys):
    db.criar_tabela()
    with db.conectar() as conexao:
        esperada = int(conexao.execute("PRAGMA user_version").fetchone()[0])

    main.verificar_banco()

    assert f"versão do schema (user_version): {esperada}" in capsys.readouterr().out


def test_verificar_banco_nao_migra_nada(capsys):
    """Um diagnóstico que altera o banco deixa de ser um diagnóstico."""
    caminho = db.caminho_bd()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(caminho) as conexao:
        conexao.execute("PRAGMA user_version = 0")

    assert main.verificar_banco() == 0

    with sqlite3.connect(caminho) as conexao:
        assert int(conexao.execute("PRAGMA user_version").fetchone()[0]) == 0
        tabelas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tabelas == [], "a verificação criou tabelas"


def test_verificar_banco_denuncia_ficheiro_estragado(capsys):
    caminho = db.caminho_bd()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"isto nao e um banco sqlite")

    assert main.verificar_banco() == 1
    assert "FALHA" in capsys.readouterr().out


def test_verificar_banco_sem_banco_nenhum(capsys):
    """Antes do primeiro arranque não há nada — e isso não é uma falha."""
    assert main.verificar_banco() == 0
    assert "ainda não existe" in capsys.readouterr().out
