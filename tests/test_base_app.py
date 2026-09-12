"""Testes dos módulos de base: versão, caminhos, configuração, utils e idiomas."""

import json

import pytest

import language_manager as lm
import utils
from core import config, paths
from core.version import (
    APP_VERSION,
    VersaoInvalidaError,
    comparar_versoes,
    parse_version,
    versao_compativel,
)


# ------------------------------------------------------------------ versão

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("1.0.0", (1, 0, 0)),
        ("2.10.3", (2, 10, 3)),
        ("1.2", (1, 2, 0)),
        ("3", (3, 0, 0)),
        ("1.2.3-beta", (1, 2, 3)),
        ("1.2.3+build5", (1, 2, 3)),
        (" 1.4.0 ", (1, 4, 0)),
    ],
)
def test_parse_version_valida(entrada, esperado):
    assert parse_version(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "   ", "a.b.c", "1.x.0", "1.2.3.4", None, 1.0])
def test_parse_version_invalida(entrada):
    with pytest.raises(VersaoInvalidaError):
        parse_version(entrada)


def test_comparar_versoes():
    assert comparar_versoes("1.0.0", "1.0.1") == -1
    assert comparar_versoes("1.10.0", "1.9.0") == 1
    assert comparar_versoes("1.2.0", "1.2") == 0


def test_versao_compativel():
    assert versao_compativel("1.0.0", app_version="1.5.0") is True
    assert versao_compativel("2.0.0", app_version="1.5.0") is False
    assert versao_compativel("1.0.0", "1.4.0", app_version="1.5.0") is False
    assert versao_compativel("1.0.0", "2.0.0", app_version="1.5.0") is True


def test_app_version_e_semantica():
    assert parse_version(APP_VERSION)


# ----------------------------------------------------------------- caminhos

def test_dados_do_utilizador_respeitam_a_variavel(dados_isolados):
    assert paths.diretorio_dados_utilizador() == dados_isolados
    assert paths.caminho_banco().parent == dados_isolados
    assert paths.diretorio_plugins_instalados().is_dir()
    assert paths.diretorio_config().is_dir()


def test_recursos_contem_os_idiomas():
    assert paths.caminho_recurso("assets", "idiomas", "pt.json").exists()


# ------------------------------------------------------------ configuração

def test_config_app_persiste():
    config.definir("tema", "escuro")
    assert config.obter("tema") == "escuro"
    assert config.obter("inexistente", "padrão") == "padrão"


def test_config_corrompida_nao_derruba():
    config.caminho_config_app().write_text("{ isto nao e json", encoding="utf-8")
    assert config.carregar_config() == {}


def test_config_de_plugin_e_isolada():
    config.definir("tema", "claro")
    config.guardar_config_plugin("calendar", {"primeiro_dia": "segunda"})
    assert config.carregar_config_plugin("calendar") == {"primeiro_dia": "segunda"}
    assert config.carregar_config_plugin("outro") == {}
    assert config.obter("tema") == "claro"
    assert config.remover_config_plugin("calendar") is True
    assert config.remover_config_plugin("calendar") is False


# --------------------------------------------------------------------- utils

def test_formatar_data():
    assert utils.formatar_data("2026-09-10") == "10/09/2026"
    assert utils.formatar_data("") == ""
    assert utils.formatar_data(None) == ""


@pytest.mark.parametrize("valor", ["2026-01-01", "", None])
def test_validar_data_iso_ok(valor):
    assert utils.validar_data_iso(valor) is True


@pytest.mark.parametrize("valor", ["10/09/2026", "2026-13-01", "abc", "2026-02-30"])
def test_validar_data_iso_falha(valor):
    assert utils.validar_data_iso(valor) is False


# ------------------------------------------------------------------- idiomas

def test_traducao_nos_tres_idiomas():
    assert lm.definir_idioma("pt") == "pt"
    assert lm.carregar_texto("titulo") == "Gerenciador de Tarefas"
    lm.definir_idioma("en")
    assert lm.carregar_texto("titulo") == "Task Manager"
    lm.definir_idioma("es")
    assert lm.carregar_texto("titulo") == "Gestor de Tareas"


def test_idioma_invalido_mantem_o_atual():
    lm.definir_idioma("en")
    assert lm.definir_idioma("klingon") == "en"


def test_chave_inexistente_devolve_a_chave_ou_o_padrao():
    assert lm.carregar_texto("chave_que_nao_existe") == "chave_que_nao_existe"
    assert lm.carregar_texto("chave_que_nao_existe", "alternativa") == "alternativa"


def test_formatacao_de_texto():
    lm.definir_idioma("pt")
    assert "Tarefa X" in lm.carregar_texto("confirmar_remocao", item="Tarefa X")


def test_idioma_e_persistido_e_restaurado():
    lm.definir_idioma("es")
    lm.definir_idioma("pt", persistir=False)
    assert lm.restaurar_idioma_guardado() == "es"


def test_todos_os_idiomas_tem_as_mesmas_chaves():
    chaves = {}
    for codigo in lm.IDIOMAS_SUPORTADOS:
        caminho = paths.caminho_recurso("assets", "idiomas", f"{codigo}.json")
        chaves[codigo] = set(json.loads(caminho.read_text(encoding="utf-8")))
    referencia = chaves["pt"]
    for codigo, conjunto in chaves.items():
        assert conjunto == referencia, f"idioma {codigo} diverge: {conjunto ^ referencia}"
