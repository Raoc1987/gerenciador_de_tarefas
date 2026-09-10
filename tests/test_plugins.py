"""Testes do sistema de plugins: manifesto, descoberta, ciclo de vida,
instalação segura, atualização com rollback, remoção e persistência.
"""

import json
import sys
import zipfile
from types import ModuleType

import pytest

from conftest import (  # fixtures/constantes do pacote de testes
    CORPO_FALHA_ATIVAR,
    CORPO_FALHA_IMPORT,
    CORPO_OK,
    CORPO_SEM_CLASSE,
    manifesto_valido,
)
from core import plugin_package
from core.plugin_api import (
    CarregamentoPluginError,
    EstadoPlugin,
    ManifestoInvalidoError,
    ManifestoPlugin,
    PacoteInvalidoError,
    Plugin,
    PluginIncompativelError,
    encontrar_classe_plugin,
)
from core.plugin_manager import PREFIXO_MODULO, PluginManager, RegistroEstado
from core.plugin_registry import RegistroEstadoBanco


# =========================================================== MANIFESTO


def test_manifesto_valido():
    manifesto = ManifestoPlugin.de_dicionario(manifesto_valido("calendar"))
    assert manifesto.id == "calendar"
    assert manifesto.versao == "1.0.0"
    assert manifesto.entry_point == "plugin.py"
    assert manifesto.autor == "Testes"


def test_manifesto_preserva_campos_extra():
    manifesto = ManifestoPlugin.de_dicionario(manifesto_valido("demo", homepage="http://x"))
    assert manifesto.extras["homepage"] == "http://x"
    assert manifesto.para_dicionario()["homepage"] == "http://x"


def test_manifesto_ida_e_volta():
    original = ManifestoPlugin.de_dicionario(manifesto_valido("demo"))
    assert ManifestoPlugin.de_dicionario(original.para_dicionario()) == original


@pytest.mark.parametrize("campo", ["id", "name", "version", "entry_point", "min_app_version"])
def test_manifesto_campo_obrigatorio_ausente(campo):
    dados = manifesto_valido()
    del dados[campo]
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(dados)


@pytest.mark.parametrize("valor", [None, 123, [], {}, "", "   "])
def test_manifesto_tipo_invalido(valor):
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(manifesto_valido(name=valor))


@pytest.mark.parametrize(
    "identificador",
    ["A", "x", "COM MAIUSCULAS", "com espaço", "com/barra", "com.ponto!", "-inicio", "", "a" * 65],
)
def test_manifesto_id_invalido(identificador):
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(manifesto_valido(identificador))


@pytest.mark.parametrize("identificador", ["ab", "calendar", "meu-plugin", "meu_plugin_2"])
def test_manifesto_id_valido(identificador):
    assert ManifestoPlugin.de_dicionario(manifesto_valido(identificador)).id == identificador


@pytest.mark.parametrize("versao", ["", "abc", "1.2.3.4", "v1.0", "1..0"])
def test_manifesto_versao_invalida(versao):
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(manifesto_valido(version=versao))


def test_manifesto_max_app_version_invalida():
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(manifesto_valido(max_app_version="abc"))


@pytest.mark.parametrize(
    "entry_point",
    ["../fora.py", "/absoluto.py", "C:/janelas.py", "plugin.txt", "sub/../../x.py", "pasta/"],
)
def test_manifesto_entry_point_inseguro(entry_point):
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(manifesto_valido(entry_point=entry_point))


def test_manifesto_entry_point_em_subpasta_e_aceite():
    manifesto = ManifestoPlugin.de_dicionario(manifesto_valido(entry_point="src/plugin.py"))
    assert manifesto.entry_point == "src/plugin.py"


def test_manifesto_nao_e_objeto():
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.de_dicionario(["não", "é", "objeto"])


def test_manifesto_json_invalido_em_disco(tmp_path):
    caminho = tmp_path / "plugin.json"
    caminho.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.ler(caminho)


def test_manifesto_inexistente_em_disco(tmp_path):
    with pytest.raises(ManifestoInvalidoError):
        ManifestoPlugin.ler(tmp_path / "nao_existe.json")


# ======================================================= COMPATIBILIDADE


def test_compatibilidade_versao_suficiente():
    manifesto = ManifestoPlugin.de_dicionario(manifesto_valido(min_app_version="1.2.0"))
    assert manifesto.compativel_com("1.5.0") is True
    manifesto.verificar_compatibilidade("1.5.0")  # não levanta


def test_compatibilidade_versao_insuficiente():
    manifesto = ManifestoPlugin.de_dicionario(manifesto_valido(min_app_version="1.2.0"))
    assert manifesto.compativel_com("1.1.0") is False
    with pytest.raises(PluginIncompativelError) as erro:
        manifesto.verificar_compatibilidade("1.1.0")
    assert "1.2.0" in str(erro.value) and "1.1.0" in str(erro.value)


def test_compatibilidade_com_maximo():
    manifesto = ManifestoPlugin.de_dicionario(
        manifesto_valido(min_app_version="1.0.0", max_app_version="1.4.0")
    )
    assert manifesto.compativel_com("1.4.0") is True
    assert manifesto.compativel_com("1.5.0") is False


# ============================================================ DESCOBERTA


def test_descoberta_plugin_valido(gerenciador, criar_plugin):
    criar_plugin("demo")
    encontrados = gerenciador.descobrir()
    assert [r.id for r in encontrados] == ["demo"]
    assert encontrados[0].estado == EstadoPlugin.INSTALADO
    assert encontrados[0].nome == "Demo"


def test_descoberta_ignora_plugin_com_manifesto_invalido(gerenciador, pasta_plugins):
    (pasta_plugins / "quebrado").mkdir()
    (pasta_plugins / "quebrado" / "plugin.json").write_text("{ mau", encoding="utf-8")
    registro = gerenciador.descobrir()[0]
    assert registro.estado == EstadoPlugin.INVALIDO
    assert registro.erro


def test_descoberta_pasta_sem_manifesto(gerenciador, pasta_plugins):
    (pasta_plugins / "vazio").mkdir()
    assert gerenciador.descobrir()[0].estado == EstadoPlugin.INVALIDO


def test_descoberta_entry_point_ausente(gerenciador, criar_plugin):
    criar_plugin("semcodigo", corpo=None)
    registro = gerenciador.descobrir()[0]
    assert registro.estado == EstadoPlugin.INVALIDO
    assert "entry_point" in registro.erro


def test_descoberta_id_divergente_da_pasta(gerenciador, criar_plugin):
    criar_plugin("pasta_a", manifesto=manifesto_valido("outro_id"))
    registro = gerenciador.descobrir()[0]
    assert registro.estado == EstadoPlugin.INVALIDO
    assert "não corresponde" in registro.erro


def test_descoberta_marca_incompativel(gerenciador, criar_plugin):
    criar_plugin("futuro", min_app_version="9.0.0")
    registro = gerenciador.descobrir()[0]
    assert registro.estado == EstadoPlugin.INCOMPATIVEL


def test_descoberta_diretorio_inexistente(tmp_path):
    gerenciador = PluginManager(diretorio=tmp_path / "nao_existe", app_version="1.0.0")
    assert gerenciador.descobrir() == []


def test_descoberta_ignora_pastas_auxiliares(gerenciador, pasta_plugins, criar_plugin):
    criar_plugin("demo")
    (pasta_plugins / "__pycache__").mkdir()
    (pasta_plugins / ".oculta").mkdir()
    assert [r.id for r in gerenciador.descobrir()] == ["demo"]


def test_descoberta_convive_com_plugins_maus(gerenciador, criar_plugin, pasta_plugins):
    criar_plugin("bom")
    criar_plugin("futuro", min_app_version="9.0.0")
    (pasta_plugins / "quebrado").mkdir()
    (pasta_plugins / "quebrado" / "plugin.json").write_text("{", encoding="utf-8")
    estados = {r.id: r.estado for r in gerenciador.descobrir()}
    assert estados["bom"] == EstadoPlugin.INSTALADO
    assert estados["futuro"] == EstadoPlugin.INCOMPATIVEL
    assert estados["quebrado"] == EstadoPlugin.INVALIDO


def test_descoberta_esquece_plugin_removido_do_disco(gerenciador, criar_plugin):
    import shutil

    pasta = criar_plugin("demo")
    gerenciador.descobrir()
    shutil.rmtree(pasta)
    assert gerenciador.descobrir() == []


# ========================================================= CICLO DE VIDA


def test_carregar_e_ativar(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    assert gerenciador.carregar("demo").sucesso
    assert gerenciador.obter("demo").estado == EstadoPlugin.CARREGADO
    assert gerenciador.ativar("demo").sucesso
    assert gerenciador.obter("demo").ativo
    assert sys.modules[PREFIXO_MODULO + "demo"].eventos == ["inicializar", "ativar"]


def test_ciclo_completo_em_ordem(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    modulo = sys.modules[PREFIXO_MODULO + "demo"]
    gerenciador.desativar("demo")
    gerenciador.ativar("demo")
    gerenciador.descarregar("demo")
    assert modulo.eventos == [
        "inicializar", "ativar", "desativar", "ativar", "desativar", "finalizar",
    ]


def test_desativar_mantem_instalado(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    assert gerenciador.desativar("demo").sucesso
    registro = gerenciador.obter("demo")
    assert registro.estado == EstadoPlugin.CARREGADO
    assert registro.ativo is False
    assert registro.pasta.exists()


def test_descarregar_liberta_o_modulo(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    gerenciador.descarregar("demo")
    assert PREFIXO_MODULO + "demo" not in sys.modules
    assert gerenciador.obter("demo").instancia is None


def test_ativar_plugin_inexistente(gerenciador):
    resultado = gerenciador.ativar("fantasma")
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_nao_encontrado"


def test_ativar_duas_vezes_e_inofensivo(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    assert gerenciador.ativar("demo").sucesso
    assert sys.modules[PREFIXO_MODULO + "demo"].eventos.count("ativar") == 1


def test_desativar_plugin_ja_inativo(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    assert gerenciador.desativar("demo").sucesso


# ================================================== ISOLAMENTO DE FALHAS


def test_falha_na_ativacao_nao_propaga(gerenciador, criar_plugin):
    criar_plugin("quebrado", corpo=CORPO_FALHA_ATIVAR)
    gerenciador.descobrir()
    resultado = gerenciador.ativar("quebrado")
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_erro_ativar"
    assert "falha proposital" in resultado.detalhes
    assert gerenciador.obter("quebrado").estado == EstadoPlugin.ERRO


def test_falha_na_importacao_nao_propaga(gerenciador, criar_plugin):
    criar_plugin("importruim", corpo=CORPO_FALHA_IMPORT)
    gerenciador.descobrir()
    resultado = gerenciador.carregar("importruim")
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_erro_carregar"
    assert PREFIXO_MODULO + "importruim" not in sys.modules


def test_modulo_sem_classe_de_plugin(gerenciador, criar_plugin):
    criar_plugin("semclasse", corpo=CORPO_SEM_CLASSE)
    gerenciador.descobrir()
    assert gerenciador.carregar("semclasse").chave_mensagem == "plugin_erro_carregar"


def test_plugin_defeituoso_nao_impede_os_outros(gerenciador, criar_plugin):
    criar_plugin("a_bom")
    criar_plugin("b_quebrado", corpo=CORPO_FALHA_ATIVAR)
    criar_plugin("c_bom")
    gerenciador.descobrir()
    for plugin_id in ("a_bom", "b_quebrado", "c_bom"):
        gerenciador.ativar(plugin_id)
    estados = {r.id: r.estado for r in gerenciador.listar()}
    assert estados["a_bom"] == EstadoPlugin.ATIVO
    assert estados["c_bom"] == EstadoPlugin.ATIVO
    assert estados["b_quebrado"] == EstadoPlugin.ERRO


def test_arranque_isola_falhas(gerenciador, criar_plugin):
    criar_plugin("bom")
    criar_plugin("quebrado", corpo=CORPO_FALHA_ATIVAR)
    criar_plugin("futuro", min_app_version="9.0.0")
    gerenciador.descobrir()
    for plugin_id in ("bom", "quebrado", "futuro"):
        gerenciador.registro.definir_habilitado(plugin_id, True)
    gerenciador.descobrir()

    resultados = gerenciador.ativar_habilitados()
    sucesso = {r.plugin_id: r.sucesso for r in resultados}
    assert sucesso == {"bom": True, "quebrado": False, "futuro": False}
    assert gerenciador.obter("bom").ativo


def test_plugin_com_erro_ao_ativar_fica_desabilitado(gerenciador, criar_plugin):
    criar_plugin("quebrado", corpo=CORPO_FALHA_ATIVAR)
    gerenciador.descobrir()
    gerenciador.ativar("quebrado")
    assert gerenciador.registro.habilitados().get("quebrado") is False


def _modulo_falso(nome: str, **atributos) -> ModuleType:
    modulo = ModuleType(nome)
    for chave, valor in atributos.items():
        if isinstance(valor, type):
            valor.__module__ = nome
        setattr(modulo, chave, valor)
    return modulo


def test_encontrar_classe_plugin_unica():
    class Unica(Plugin):
        pass

    modulo = _modulo_falso("mod_um", Unica=Unica)
    assert encontrar_classe_plugin(modulo) is Unica


def test_encontrar_classe_plugin_ambigua():
    class A(Plugin):
        pass

    class B(Plugin):
        pass

    modulo = _modulo_falso("mod_dois", A=A, B=B)
    with pytest.raises(CarregamentoPluginError):
        encontrar_classe_plugin(modulo)


def test_plugin_class_explicita_resolve_a_ambiguidade():
    class A(Plugin):
        pass

    class B(Plugin):
        pass

    modulo = _modulo_falso("mod_tres", A=A, B=B)
    modulo.PLUGIN_CLASS = B
    assert encontrar_classe_plugin(modulo) is B


def test_plugin_class_invalida():
    modulo = _modulo_falso("mod_quatro")
    modulo.PLUGIN_CLASS = str
    with pytest.raises(CarregamentoPluginError):
        encontrar_classe_plugin(modulo)


def test_modulo_sem_nenhuma_classe():
    with pytest.raises(CarregamentoPluginError):
        encontrar_classe_plugin(_modulo_falso("mod_cinco", VALOR=1))


# ============================================================ INSTALAÇÃO


def test_instalar_zip_valido(gerenciador, zip_valido):
    resultado = gerenciador.instalar_zip(zip_valido("demo"))
    assert resultado.sucesso
    assert resultado.chave_mensagem == "plugin_instalado"
    assert (gerenciador.diretorio / "demo" / "plugin.json").is_file()
    assert gerenciador.obter("demo").estado == EstadoPlugin.INSTALADO


def test_instalar_zip_sem_pasta_de_topo(gerenciador, criar_zip):
    caminho = criar_zip(
        "raiz.zip",
        {"plugin.json": json.dumps(manifesto_valido("naraiz")), "plugin.py": CORPO_OK},
    )
    assert gerenciador.instalar_zip(caminho).sucesso
    assert (gerenciador.diretorio / "naraiz" / "plugin.py").is_file()


def test_instalar_e_ativar_de_seguida(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo"))
    assert gerenciador.ativar("demo").sucesso


def test_instalar_zip_sem_manifesto(gerenciador, criar_zip):
    caminho = criar_zip("sem.zip", {"plugin.py": CORPO_OK})
    resultado = gerenciador.instalar_zip(caminho)
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_pacote_invalido"


def test_instalar_arquivo_que_nao_e_zip(gerenciador, tmp_path):
    falso = tmp_path / "falso.zip"
    falso.write_text("isto não é um zip", encoding="utf-8")
    assert gerenciador.instalar_zip(falso).chave_mensagem == "plugin_pacote_invalido"


def test_instalar_arquivo_inexistente(gerenciador, tmp_path):
    assert not gerenciador.instalar_zip(tmp_path / "nada.zip").sucesso


def test_instalar_zip_incompativel(gerenciador, zip_valido):
    resultado = gerenciador.instalar_zip(zip_valido("futuro", min_app_version="9.0.0"))
    assert resultado.chave_mensagem == "plugin_incompativel"
    assert not (gerenciador.diretorio / "futuro").exists()


def test_instalar_zip_com_manifesto_invalido(gerenciador, criar_zip):
    caminho = criar_zip("mau.zip", {"x/plugin.json": "{ mau", "x/plugin.py": CORPO_OK})
    assert gerenciador.instalar_zip(caminho).chave_mensagem == "plugin_invalido"


def test_instalar_zip_com_varios_manifestos(gerenciador, criar_zip):
    caminho = criar_zip(
        "dois.zip",
        {
            "a/plugin.json": json.dumps(manifesto_valido("aa")),
            "a/plugin.py": CORPO_OK,
            "b/plugin.json": json.dumps(manifesto_valido("bb")),
            "b/plugin.py": CORPO_OK,
        },
    )
    assert gerenciador.instalar_zip(caminho).chave_mensagem == "plugin_pacote_invalido"


def test_instalar_zip_com_entry_point_ausente(gerenciador, criar_zip):
    caminho = criar_zip(
        "faltoso.zip",
        {"x/plugin.json": json.dumps(manifesto_valido("faltoso")), "x/outro.py": CORPO_OK},
    )
    assert gerenciador.instalar_zip(caminho).chave_mensagem == "plugin_invalido"


# ============================================== SEGURANÇA DO PACOTE (ZIP)


@pytest.mark.parametrize(
    "caminho_malicioso",
    ["../evil.py", "../../evil.py", "demo/../../evil.py", "/etc/passwd", "C:/Windows/evil.py"],
)
def test_zip_com_path_traversal_e_recusado(gerenciador, criar_zip, caminho_malicioso, tmp_path):
    caminho = criar_zip(
        "mal.zip",
        {
            "demo/plugin.json": json.dumps(manifesto_valido("demo")),
            "demo/plugin.py": CORPO_OK,
            caminho_malicioso: "print('invadido')",
        },
    )
    resultado = gerenciador.instalar_zip(caminho)
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_pacote_invalido"
    assert not (gerenciador.diretorio / "demo").exists()
    assert not (tmp_path / "evil.py").exists()
    assert not (tmp_path.parent / "evil.py").exists()


def test_zip_com_separadores_do_windows_e_recusado(gerenciador, criar_zip):
    caminho = criar_zip(
        "win.zip",
        {
            "demo/plugin.json": json.dumps(manifesto_valido("demo")),
            "demo/plugin.py": CORPO_OK,
            "..\\..\\evil.py": "print('invadido')",
        },
    )
    assert gerenciador.instalar_zip(caminho).chave_mensagem == "plugin_pacote_invalido"


def test_zip_com_ligacao_simbolica_e_recusado(gerenciador, tmp_path):
    caminho = tmp_path / "link.zip"
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("demo/plugin.json", json.dumps(manifesto_valido("demo")))
        pacote.writestr("demo/plugin.py", CORPO_OK)
        info = zipfile.ZipInfo("demo/atalho")
        info.external_attr = (0xA1FF) << 16  # S_IFLNK | 0777
        pacote.writestr(info, "/etc/passwd")
    assert gerenciador.instalar_zip(caminho).chave_mensagem == "plugin_pacote_invalido"


def test_zip_com_arquivos_a_mais_e_recusado(gerenciador, criar_zip, monkeypatch):
    monkeypatch.setattr(plugin_package, "MAX_ARQUIVOS", 3)
    arquivos = {
        "demo/plugin.json": json.dumps(manifesto_valido("demo")),
        "demo/plugin.py": CORPO_OK,
    }
    arquivos.update({f"demo/extra{i}.txt": "x" for i in range(5)})
    assert gerenciador.instalar_zip(criar_zip("muitos.zip", arquivos)).chave_mensagem == (
        "plugin_pacote_invalido"
    )


def test_zip_demasiado_grande_e_recusado(gerenciador, criar_zip, monkeypatch):
    monkeypatch.setattr(plugin_package, "MAX_TAMANHO_TOTAL", 100)
    monkeypatch.setattr(plugin_package, "MAX_RACIO_COMPRESSAO", 10_000_000)
    arquivos = {
        "demo/plugin.json": json.dumps(manifesto_valido("demo")),
        "demo/plugin.py": CORPO_OK,
        "demo/grande.bin": "A" * 5000,
    }
    assert gerenciador.instalar_zip(criar_zip("grande.zip", arquivos)).chave_mensagem == (
        "plugin_pacote_invalido"
    )


def test_zip_bomb_por_racio_e_recusado(gerenciador, criar_zip, monkeypatch):
    monkeypatch.setattr(plugin_package, "MAX_RACIO_COMPRESSAO", 5)
    arquivos = {
        "demo/plugin.json": json.dumps(manifesto_valido("demo")),
        "demo/plugin.py": CORPO_OK,
        "demo/bomba.bin": "A" * 100_000,  # comprime imenso
    }
    assert gerenciador.instalar_zip(criar_zip("bomba.zip", arquivos)).chave_mensagem == (
        "plugin_pacote_invalido"
    )


def test_inspecionar_nao_escreve_nada(gerenciador, zip_valido):
    manifesto = gerenciador.inspecionar_zip(zip_valido("demo"))
    assert manifesto.id == "demo"
    assert list(gerenciador.diretorio.iterdir()) == []


def test_extrair_ignora_arquivos_fora_da_raiz_do_plugin(criar_zip, tmp_path):
    caminho = criar_zip(
        "extra.zip",
        {
            "demo/plugin.json": json.dumps(manifesto_valido("demo")),
            "demo/plugin.py": CORPO_OK,
            "LEIAME.txt": "fora da pasta do plugin",
        },
    )
    pacote = plugin_package.inspecionar(caminho)
    destino = plugin_package.extrair(pacote, tmp_path / "saida")
    assert (destino / "plugin.json").is_file()
    assert not (destino / "LEIAME.txt").exists()


def test_pacote_vazio(gerenciador, tmp_path):
    caminho = tmp_path / "vazio.zip"
    with zipfile.ZipFile(caminho, "w"):
        pass
    with pytest.raises(PacoteInvalidoError):
        plugin_package.inspecionar(caminho)


# ============================================================ ATUALIZAÇÃO


def test_atualizacao_para_versao_mais_nova(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    resultado = gerenciador.instalar_zip(
        zip_valido("demo", version="2.0.0", corpo=CORPO_OK + "\nMARCA = 2\n", nome="v2.zip")
    )
    assert resultado.sucesso
    assert resultado.chave_mensagem == "plugin_atualizado"
    assert gerenciador.versao_instalada("demo") == "2.0.0"
    assert "MARCA = 2" in (gerenciador.diretorio / "demo" / "plugin.py").read_text(
        encoding="utf-8"
    )


def test_reinstalar_a_mesma_versao_e_recusado(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo"))
    resultado = gerenciador.instalar_zip(zip_valido("demo", nome="outra_vez.zip"))
    assert not resultado.sucesso
    assert resultado.chave_mensagem == "plugin_ja_instalado"
    assert "1.0.0" in resultado.detalhes


def test_downgrade_e_recusado(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo", version="2.0.0"))
    resultado = gerenciador.instalar_zip(zip_valido("demo", version="1.0.0", nome="velho.zip"))
    assert resultado.chave_mensagem == "plugin_ja_instalado"
    assert gerenciador.versao_instalada("demo") == "2.0.0"


def test_atualizacao_troca_o_modulo_em_execucao(gerenciador, zip_valido):
    """O plugin é descarregado antes de os arquivos serem substituídos."""
    gerenciador.instalar_zip(zip_valido("demo"))
    gerenciador.ativar("demo")
    antigo = sys.modules[PREFIXO_MODULO + "demo"]

    gerenciador.instalar_zip(
        zip_valido(
            "demo", version="2.0.0", corpo=CORPO_OK + "\nMARCA = 2\n", nome="v2.zip"
        )
    )
    novo = sys.modules[PREFIXO_MODULO + "demo"]
    assert novo is not antigo
    assert antigo.eventos == ["inicializar", "ativar", "desativar", "finalizar"]
    assert hasattr(novo, "MARCA")


def test_rollback_repoe_a_versao_anterior(gerenciador, zip_valido, monkeypatch):
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0", corpo=CORPO_OK + "\nMARCA = 1\n"))

    original = plugin_package.validar_instalacao
    chamadas = {"n": 0}

    def falhar_na_segunda(pasta, esperado=None):
        chamadas["n"] += 1
        if chamadas["n"] == 2:  # já depois de a nova versão ter sido movida
            raise ManifestoInvalidoError("falha simulada após mover")
        return original(pasta, esperado)

    monkeypatch.setattr(plugin_package, "validar_instalacao", falhar_na_segunda)

    resultado = gerenciador.instalar_zip(
        zip_valido("demo", version="2.0.0", corpo=CORPO_OK + "\nMARCA = 2\n", nome="v2.zip")
    )
    assert not resultado.sucesso
    assert gerenciador.versao_instalada("demo") == "1.0.0"
    assert "MARCA = 1" in (gerenciador.diretorio / "demo" / "plugin.py").read_text(
        encoding="utf-8"
    )


def test_area_temporaria_fica_limpa(gerenciador, zip_valido):
    from core.paths import diretorio_plugins_temp

    gerenciador.instalar_zip(zip_valido("demo"))
    assert list(diretorio_plugins_temp().iterdir()) == []


def test_atualizacao_preserva_config_do_plugin(gerenciador, zip_valido):
    from core import config

    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    config.guardar_config_plugin("demo", {"chave": "valor"})
    gerenciador.instalar_zip(zip_valido("demo", version="2.0.0", nome="v2.zip"))
    assert config.carregar_config_plugin("demo") == {"chave": "valor"}


# ================================================================ REMOÇÃO


def test_remover_plugin_inativo(gerenciador, criar_plugin):
    pasta = criar_plugin("demo")
    gerenciador.descobrir()
    assert gerenciador.remover("demo").sucesso
    assert not pasta.exists()
    assert gerenciador.obter("demo") is None


def test_remover_desativa_antes(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    modulo = sys.modules[PREFIXO_MODULO + "demo"]
    gerenciador.remover("demo")
    assert modulo.eventos[-2:] == ["desativar", "finalizar"]
    assert PREFIXO_MODULO + "demo" not in sys.modules


def test_remover_preserva_dados_por_omissao(gerenciador, criar_plugin):
    from core import config
    from core.paths import diretorio_dados_plugin

    criar_plugin("demo")
    gerenciador.descobrir()
    config.guardar_config_plugin("demo", {"a": 1})
    (diretorio_dados_plugin("demo") / "notas.txt").write_text("dados", encoding="utf-8")

    gerenciador.remover("demo")
    assert config.carregar_config_plugin("demo") == {"a": 1}
    assert (diretorio_dados_plugin("demo") / "notas.txt").exists()


def test_remover_com_dados_quando_pedido(gerenciador, criar_plugin):
    from core import config
    from core.paths import diretorio_dados_plugin

    criar_plugin("demo")
    gerenciador.descobrir()
    config.guardar_config_plugin("demo", {"a": 1})
    pasta_dados = diretorio_dados_plugin("demo")
    (pasta_dados / "notas.txt").write_text("dados", encoding="utf-8")

    gerenciador.remover("demo", remover_dados=True)
    assert config.carregar_config_plugin("demo") == {}
    assert not pasta_dados.exists()


def test_remover_plugin_inexistente(gerenciador):
    assert not gerenciador.remover("fantasma").sucesso


def test_remover_esquece_o_registo(gerenciador, criar_plugin):
    criar_plugin("demo")
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    gerenciador.remover("demo")
    assert "demo" not in gerenciador.registro.habilitados()


# =========================================================== PERSISTÊNCIA


def test_estado_sobrevive_a_reinicializacao(pasta_plugins, criar_plugin):
    criar_plugin("demo")
    registro = RegistroEstadoBanco()

    primeira = PluginManager(diretorio=pasta_plugins, app_version="1.0.0", registro=registro)
    primeira.descobrir()
    primeira.ativar("demo")
    primeira.desativar_todos()

    # "Reinício": novo gerenciador, novo registo, mesmo banco.
    segunda = PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )
    segunda.descobrir()
    assert segunda.obter("demo").habilitado is True
    segunda.ativar_habilitados()
    assert segunda.obter("demo").ativo


def test_plugin_desativado_continua_desativado_apos_reinicio(pasta_plugins, criar_plugin):
    criar_plugin("demo")
    primeira = PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )
    primeira.descobrir()
    primeira.ativar("demo")
    primeira.desativar("demo")

    segunda = PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )
    segunda.descobrir()
    assert segunda.obter("demo").habilitado is False
    assert [r for r in segunda.ativar_habilitados()] == []


def test_registo_no_banco_guarda_versao_e_datas(pasta_plugins, zip_valido):
    gerenciador = PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    linha = gerenciador.registro.obter("demo")
    assert linha[1] == "1.0.0"
    assert linha[2] is False
    assert linha[3] and linha[4]

    gerenciador.ativar("demo")
    gerenciador.instalar_zip(zip_valido("demo", version="2.0.0", nome="v2.zip"))
    linha = gerenciador.registro.obter("demo")
    assert linha[1] == "2.0.0"
    # A atualização preserva a escolha do utilizador de ter o plugin ligado.
    assert linha[2] is True


def test_registo_em_memoria_e_o_padrao(pasta_plugins):
    assert isinstance(PluginManager(diretorio=pasta_plugins).registro, RegistroEstado)


def test_tabela_de_plugins_nao_afeta_as_tarefas(pasta_plugins, criar_plugin):
    import database

    database.criar_tabela()
    tarefa_id = database.adicionar_tarefa("Tarefa importante")

    criar_plugin("demo")
    gerenciador = PluginManager(
        diretorio=pasta_plugins, app_version="1.0.0", registro=RegistroEstadoBanco()
    )
    gerenciador.descobrir()
    gerenciador.ativar("demo")
    gerenciador.remover("demo", remover_dados=True)

    assert database.obter_tarefa(tarefa_id)[1] == "Tarefa importante"


# ====================================================== IDIOMAS DOS PLUGINS


CORPO_TRADUZIDO = '''
from core.plugin_api import Plugin

visto = {}


class PluginTraduzido(Plugin):
    def ativar(self):
        visto["aba"] = self.contexto.traduzir("aba")
        visto["app"] = self.contexto.traduzir("tarefas")
        visto["desconhecida"] = self.contexto.traduzir("nao_existe", "reserva")
'''

CORPO_REGISTA_TEXTOS = '''
from core.plugin_api import Plugin

visto = {}


class PluginQueRegista(Plugin):
    def inicializar(self):
        self.contexto.registrar_textos(
            {"pt": {"ola": "Olá"}, "en": {"ola": "Hello"}}
        )

    def ativar(self):
        visto["ola"] = self.contexto.traduzir("ola")
'''


def test_plugin_usa_a_sua_pasta_de_idiomas(gerenciador, criar_plugin):
    import language_manager as lm

    pasta = criar_plugin("traduzido", corpo=CORPO_TRADUZIDO)
    idiomas = pasta / "idiomas"
    idiomas.mkdir()
    (idiomas / "pt.json").write_text(json.dumps({"aba": "Calendário"}), encoding="utf-8")
    (idiomas / "en.json").write_text(json.dumps({"aba": "Calendar"}), encoding="utf-8")

    gerenciador.descobrir()
    lm.definir_idioma("en", persistir=False)
    assert gerenciador.ativar("traduzido").sucesso

    visto = sys.modules[PREFIXO_MODULO + "traduzido"].visto
    assert visto["aba"] == "Calendar"
    # chaves que o plugin não define caem nos textos da aplicação
    assert visto["app"] == "Tasks"
    assert visto["desconhecida"] == "reserva"


def test_idioma_do_plugin_cai_para_portugues(gerenciador, criar_plugin):
    import language_manager as lm

    pasta = criar_plugin("traduzido", corpo=CORPO_TRADUZIDO)
    idiomas = pasta / "idiomas"
    idiomas.mkdir()
    (idiomas / "pt.json").write_text(json.dumps({"aba": "Calendário"}), encoding="utf-8")

    gerenciador.descobrir()
    lm.definir_idioma("es", persistir=False)
    gerenciador.ativar("traduzido")
    assert sys.modules[PREFIXO_MODULO + "traduzido"].visto["aba"] == "Calendário"


def test_idioma_do_plugin_invalido_e_ignorado(gerenciador, criar_plugin):
    pasta = criar_plugin("traduzido", corpo=CORPO_TRADUZIDO)
    idiomas = pasta / "idiomas"
    idiomas.mkdir()
    (idiomas / "pt.json").write_text("{ isto não é json", encoding="utf-8")

    gerenciador.descobrir()
    assert gerenciador.ativar("traduzido").sucesso
    assert sys.modules[PREFIXO_MODULO + "traduzido"].visto["aba"] == "aba"


def test_plugin_pode_registar_textos_em_codigo(gerenciador, criar_plugin):
    import language_manager as lm

    criar_plugin("registador", corpo=CORPO_REGISTA_TEXTOS)
    gerenciador.descobrir()
    lm.definir_idioma("pt", persistir=False)
    gerenciador.ativar("registador")
    assert sys.modules[PREFIXO_MODULO + "registador"].visto["ola"] == "Olá"


def test_textos_do_plugin_sao_esquecidos_ao_descarregar(gerenciador, criar_plugin):
    import language_manager as lm

    criar_plugin("registador", corpo=CORPO_REGISTA_TEXTOS)
    gerenciador.descobrir()
    gerenciador.ativar("registador")
    assert lm.carregar_texto_plugin("registador", "ola") == "Olá"

    gerenciador.descarregar("registador")
    assert lm.carregar_texto_plugin("registador", "ola") == "ola"


def test_atualizacao_reativa_plugin_que_estava_ativo(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    gerenciador.ativar("demo")

    resultado = gerenciador.instalar_zip(
        zip_valido("demo", version="2.0.0", corpo=CORPO_OK + "\nMARCA = 2\n", nome="v2.zip")
    )
    assert resultado.sucesso
    registro = gerenciador.obter("demo")
    assert registro.ativo
    assert registro.versao == "2.0.0"
    # correndo a partir do código novo
    assert hasattr(sys.modules[PREFIXO_MODULO + "demo"], "MARCA")


def test_atualizacao_nao_ativa_plugin_que_estava_parado(gerenciador, zip_valido):
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    gerenciador.instalar_zip(zip_valido("demo", version="2.0.0", nome="v2.zip"))
    assert not gerenciador.obter("demo").ativo


def test_atualizacao_com_versao_nova_que_falha_ao_ativar(gerenciador, zip_valido):
    """A atualização conclui; a falha do plugin novo é reportada, não fatal."""
    gerenciador.instalar_zip(zip_valido("demo", version="1.0.0"))
    gerenciador.ativar("demo")

    resultado = gerenciador.instalar_zip(
        zip_valido("demo", version="2.0.0", corpo=CORPO_FALHA_ATIVAR, nome="v2.zip")
    )
    assert resultado.sucesso
    assert "falha proposital" in resultado.detalhes
    assert gerenciador.obter("demo").estado == EstadoPlugin.ERRO
    assert gerenciador.versao_instalada("demo") == "2.0.0"
