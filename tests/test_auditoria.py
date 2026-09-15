"""Testes da trilha de auditoria."""

from datetime import datetime, timedelta

import pytest

import banco_de_dados as db
from core import auditoria, eventos, permissoes
from core.eventos import Evento


@pytest.fixture(autouse=True)
def auditoria_ligada():
    """Cada teste começa com a auditoria ligada e acaba sem ela."""
    auditoria.ativar()
    yield
    auditoria.desativar()


def eventos_registados():
    return [r.evento for r in auditoria.consultar()]


# ============================================================== REGISTO


def test_criar_tarefa_deixa_rasto():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Tarefa auditada")

    registos = auditoria.consultar()
    assert len(registos) == 1
    registo = registos[0]
    assert registo.evento == eventos.TAREFA_CRIADA
    assert registo.alvo == str(tarefa_id)
    assert registo.origem == "database"
    assert registo.quando is not None


def test_ciclo_completo_de_uma_tarefa():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Tarefa")
    db.concluir_tarefa(tarefa_id)
    db.concluir_tarefa(tarefa_id, False)
    db.remover_tarefa(tarefa_id)

    # Do mais recente para o mais antigo.
    assert eventos_registados() == [
        eventos.TAREFA_REMOVIDA,
        eventos.TAREFA_REABERTA,
        eventos.TAREFA_CONCLUIDA,
        eventos.TAREFA_CRIADA,
    ]


def test_utilizador_da_sessao_fica_registado():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    db.adicionar_tarefa("Da Ana")
    assert auditoria.consultar()[0].utilizador == "ana"


def test_nao_se_guarda_o_conteudo_da_tarefa():
    """A trilha diz o que aconteceu, não o que a tarefa dizia."""
    db.criar_tabela()
    db.adicionar_tarefa("Segredo comercial muito sensível")

    registo = auditoria.consultar()[0]
    assert "Segredo" not in registo.detalhe
    assert "Segredo" not in registo.alvo


def test_evento_nao_auditavel_e_ignorado():
    auditoria.registar(Evento(nome="tarefa.rascunho", dados={"id": 1}))
    assert auditoria.contar() == 0


def test_detalhes_de_plugin_sao_guardados():
    auditoria.registar(
        Evento(
            nome=eventos.PLUGIN_ATUALIZADO,
            dados={"id": "calendar", "versao": "2.0.0", "versao_anterior": "1.0.0"},
            momento=datetime.now().isoformat(timespec="seconds"),
        )
    )
    registo = auditoria.consultar()[0]
    assert registo.alvo == "calendar"
    assert "versao=2.0.0" in registo.detalhe
    assert "versao_anterior=1.0.0" in registo.detalhe


def test_detalhe_longo_e_cortado():
    auditoria.registar(
        Evento(
            nome=eventos.PLUGIN_ERRO,
            dados={"id": "mau", "erro": "x" * 3000},
            momento=datetime.now().isoformat(timespec="seconds"),
        )
    )
    assert len(auditoria.consultar()[0].detalhe) <= auditoria.LIMITE_DETALHE


def test_ciclo_de_vida_de_plugin_e_auditado(tmp_path):
    from core.plugin_manager import PluginManager

    from conftest import CORPO_OK, manifesto_valido

    import json

    pasta = tmp_path / "installed" / "demo"
    pasta.mkdir(parents=True)
    (pasta / "plugin.json").write_text(json.dumps(manifesto_valido("demo")), encoding="utf-8")
    (pasta / "plugin.py").write_text(CORPO_OK, encoding="utf-8")

    gerenciador = PluginManager(diretorio=tmp_path / "installed", app_version="1.0.0")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    gerenciador.desativar("demo")

    assert eventos.PLUGIN_ATIVADO in eventos_registados()
    assert eventos.PLUGIN_DESATIVADO in eventos_registados()


# ============================================================== CONSULTA


def test_filtro_por_prefixo():
    db.criar_tabela()
    db.adicionar_tarefa("Uma")
    auditoria.registar(
        Evento(nome=eventos.PLUGIN_ATIVADO, dados={"id": "x"}, momento="2026-01-01T00:00:00")
    )

    assert len(auditoria.consultar(evento="tarefa.*")) == 1
    assert len(auditoria.consultar(evento="plugin.*")) == 1
    assert len(auditoria.consultar()) == 2


def test_filtro_por_evento_exato():
    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Uma")
    db.concluir_tarefa(tarefa_id)
    assert len(auditoria.consultar(evento=eventos.TAREFA_CONCLUIDA)) == 1


def test_filtro_por_utilizador():
    db.criar_tabela()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.adicionar_tarefa("Da Ana")
    permissoes.definir_sessao("bruno", "administrador", persistir=False)
    db.adicionar_tarefa("Do Bruno")

    assert len(auditoria.consultar(utilizador="ana")) == 1
    assert auditoria.consultar(utilizador="bruno")[0].utilizador == "bruno"


def test_filtro_por_data():
    auditoria.registar(
        Evento(nome=eventos.TAREFA_CRIADA, dados={"id": 1}, momento="2020-01-01T00:00:00")
    )
    db.criar_tabela()
    db.adicionar_tarefa("Recente")

    recentes = auditoria.consultar(desde=datetime.now() - timedelta(hours=1))
    assert len(recentes) == 1


def test_limite():
    db.criar_tabela()
    for indice in range(10):
        db.adicionar_tarefa(f"Tarefa {indice}")
    assert len(auditoria.consultar(limite=3)) == 3
    assert auditoria.contar() == 10


# ============================================================== ROBUSTEZ


def test_auditoria_nao_impede_o_trabalho(monkeypatch):
    """Se a gravação falhar, a tarefa é criada na mesma."""
    import core.auditoria as modulo

    def explode(evento):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(modulo, "_detalhe_de", explode)

    db.criar_tabela()
    tarefa_id = db.adicionar_tarefa("Tem de ser criada")
    assert db.obter_tarefa(tarefa_id) is not None


def test_consulta_com_banco_partido_devolve_vazio(monkeypatch):
    import banco_de_dados

    def explode():
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(banco_de_dados, "criar_tabela", explode)
    assert auditoria.consultar() == []
    assert auditoria.contar() == 0


def test_ativar_e_idempotente():
    assert auditoria.ativar() is False, "já ligada pela fixture"
    assert auditoria.ativa() is True
    assert auditoria.desativar() is True
    assert auditoria.desativar() is False


def test_desligada_nao_regista():
    auditoria.desativar()
    db.criar_tabela()
    db.adicionar_tarefa("Sem rasto")
    assert auditoria.contar() == 0


# ============================================================== RETENÇÃO


def test_retencao_remove_so_o_que_e_antigo():
    antigo = (datetime.now() - timedelta(days=120)).isoformat(timespec="seconds")
    auditoria.registar(Evento(nome=eventos.TAREFA_CRIADA, dados={"id": 1}, momento=antigo))
    db.criar_tabela()
    db.adicionar_tarefa("Recente")

    assert auditoria.contar() == 2
    assert auditoria.aplicar_retencao(dias=90) == 1
    assert auditoria.contar() == 1
    # O que sobra é o recente. (O alvo não distingue: numa base nova, ambas as
    # tarefas teriam id 1.)
    restante = auditoria.consultar()[0]
    assert restante.quando > datetime.now() - timedelta(minutes=5)


def test_retencao_invalida():
    with pytest.raises(ValueError):
        auditoria.aplicar_retencao(dias=0)


def test_retencao_sem_nada_para_remover():
    db.criar_tabela()
    db.adicionar_tarefa("Recente")
    assert auditoria.aplicar_retencao(dias=30) == 0


def test_retencao_configurada_aplica_a_politica():
    """Com política definida, o arranque encolhe a trilha."""
    from core import config

    antigo = (datetime.now() - timedelta(days=400)).isoformat(timespec="seconds")
    auditoria.registar(Evento(nome=eventos.TAREFA_CRIADA, dados={"id": 1}, momento=antigo))
    db.criar_tabela()
    db.adicionar_tarefa("Recente")

    config.definir(auditoria.CHAVE_RETENCAO, 365)
    assert auditoria.aplicar_retencao_configurada() == 1
    assert auditoria.contar() == 1


def test_sem_politica_nao_se_apaga_nada():
    """O padrão é guardar: apagar por omissão não se desfaz."""
    antigo = (datetime.now() - timedelta(days=4000)).isoformat(timespec="seconds")
    auditoria.registar(Evento(nome=eventos.TAREFA_CRIADA, dados={"id": 1}, momento=antigo))

    assert auditoria.aplicar_retencao_configurada() == 0
    assert auditoria.contar() == 1


@pytest.mark.parametrize("valor", [0, -5, "sempre", None, ""])
def test_politica_invalida_nao_apaga_nem_rebenta(valor):
    """Uma configuração estragada não pode apagar a auditoria por acidente."""
    from core import config

    antigo = (datetime.now() - timedelta(days=4000)).isoformat(timespec="seconds")
    auditoria.registar(Evento(nome=eventos.TAREFA_CRIADA, dados={"id": 1}, momento=antigo))

    config.definir(auditoria.CHAVE_RETENCAO, valor)
    assert auditoria.aplicar_retencao_configurada() == 0
    assert auditoria.contar() == 1


# ============================================================== CATÁLOGO


def test_todos_os_eventos_auditaveis_existem_no_nucleo():
    conhecidos = set(eventos.eventos_conhecidos())
    for nome in auditoria.EVENTOS_AUDITAVEIS:
        assert nome in conhecidos, f"{nome} não está no catálogo do barramento"


def test_auditoria_nao_depende_da_interface():
    import ast
    from pathlib import Path

    arquivo = Path(__file__).resolve().parent.parent / "src" / "core" / "auditoria.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        nomes = []
        if isinstance(no, ast.Import):
            nomes = [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom):
            nomes = [no.module or ""]
        for nome in nomes:
            assert nome.split(".")[0] != "tkinter"
