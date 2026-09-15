"""Cópias de segurança: guardar tudo, repor tudo, nunca perder nada.

Há duas maneiras de esta funcionalidade ser pior do que não existir: apagar
dados bons ao restaurar uma cópia má, e executar código que veio dentro de um
ficheiro que alguém enviou. Os testes abaixo existem sobretudo por causa
dessas duas.
"""

import json
import zipfile
from datetime import datetime

import pytest

import banco_de_dados as db
from core import backup, organizacao, permissoes, utilizadores
from core.backup import (
    ArquivoInvalidoError,
    BackupIncompativelError,
    Manifesto,
)
from core.organizacao import TipoUnidade
from core.paths import diretorio_dados_utilizador


@pytest.fixture
def dados_reais():
    """Um estado com um pouco de cada coisa que se pode perder."""
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    tarefa = db.adicionar_tarefa("Não me percas", "2030-01-01", criada_por="ana")
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    utilizadores.criar("bruno", "Uma-Senha-Longa-123", papel="colaborador")
    utilizadores.definir_unidade("bruno", empresa.id)
    return {"tarefa": tarefa, "empresa": empresa}


@pytest.fixture
def copia(tmp_path, dados_reais):
    return backup.criar(tmp_path / "copia.zip")


# ================================================================== CRIAR


def test_criar_escreve_um_zip_com_manifesto(copia):
    assert copia.is_file()
    with zipfile.ZipFile(copia) as arquivo:
        assert backup.NOME_MANIFESTO in arquivo.namelist()
        assert backup.NOME_BANCO in arquivo.namelist()


def test_o_manifesto_diz_de_onde_veio(copia):
    from core.version import APP_VERSION

    manifesto = backup.inspecionar(copia)
    assert manifesto.formato == backup.FORMATO
    assert manifesto.app_version == APP_VERSION
    assert manifesto.esquema == db.VERSAO_ESQUEMA
    assert manifesto.criado_em


def test_a_copia_leva_as_configuracoes(tmp_path, dados_reais):
    from core import config

    config.definir("tema", "escuro")
    destino = backup.criar(tmp_path / "c.zip")

    with zipfile.ZipFile(destino) as arquivo:
        nomes = arquivo.namelist()
    assert any(n.startswith(backup.PASTA_CONFIG + "/") for n in nomes)


def test_a_copia_leva_os_dados_dos_plugins(tmp_path, dados_reais):
    from core.paths import diretorio_dados_plugin
    from core.plugin_dados import ArmazenamentoPlugin

    armazem = ArmazenamentoPlugin("estoque", diretorio_dados_plugin("estoque"))
    armazem.migrar(1, "CREATE TABLE itens (id INTEGER PRIMARY KEY, nome TEXT)")
    armazem.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))

    destino = backup.criar(tmp_path / "c.zip")
    with zipfile.ZipFile(destino) as arquivo:
        assert any("estoque" in n for n in arquivo.namelist())


def test_uma_copia_nunca_leva_codigo(tmp_path, dados_reais, criar_plugin):
    """Restaurar não pode ser uma forma de instalar plugins.

    Um ficheiro de cópia anda por e-mail e por pen. Se trouxesse código, abrir
    a cópia de alguém passava a executar o que essa pessoa lá pusesse.
    """
    from core.paths import diretorio_plugins_instalados

    pasta = diretorio_plugins_instalados() / "malicioso"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "plugin.py").write_text("raise SystemExit('boom')", encoding="utf-8")

    destino = backup.criar(tmp_path / "c.zip")
    with zipfile.ZipFile(destino) as arquivo:
        nomes = arquivo.namelist()
    assert not any("plugin.py" in n for n in nomes)
    assert not any("installed" in n for n in nomes)


def test_os_registos_ficam_de_fora(tmp_path, dados_reais):
    """Logs são diagnóstico, não dados — e podem levar caminhos da máquina."""
    from core.paths import diretorio_logs

    (diretorio_logs() / "app.log").write_text("linha", encoding="utf-8")
    destino = backup.criar(tmp_path / "c.zip")

    with zipfile.ZipFile(destino) as arquivo:
        assert not any("log" in n.lower() for n in arquivo.namelist())


def test_uma_copia_interrompida_nao_fica_no_sitio(tmp_path, dados_reais, monkeypatch):
    """Um ficheiro a meio não pode ficar com o nome de uma cópia boa."""
    destino = tmp_path / "c.zip"

    def rebentar(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(backup, "_guardar_pasta", rebentar)
    with pytest.raises(OSError):
        backup.criar(destino)

    assert not destino.exists()
    assert not list(tmp_path.glob("*.parcial"))


def test_o_nome_sugerido_tem_data():
    nome = backup.nome_sugerido(datetime(2026, 9, 11, 14, 30))
    assert nome == "copia-2026-09-11_1430.zip"


def test_duas_copias_seguidas_nao_se_sobrepoem(dados_reais):
    a = backup.nome_sugerido(datetime(2026, 9, 11, 14, 30))
    b = backup.nome_sugerido(datetime(2026, 9, 11, 15, 45))
    assert a != b


# =============================================================== RESTAURAR


def test_restaurar_repoe_as_tarefas(copia, dados_reais):
    db.remover_tarefa(dados_reais["tarefa"])
    assert db.buscar_tarefas() == []

    backup.restaurar(copia)
    assert [t[1] for t in db.buscar_tarefas()] == ["Não me percas"]


def test_restaurar_repoe_as_contas_e_a_estrutura(copia):
    utilizadores.remover("bruno")
    organizacao.remover(organizacao.raizes()[0].id)

    backup.restaurar(copia)
    assert utilizadores.obter("bruno") is not None
    assert [u.nome for u in organizacao.raizes()] == ["Acme"]


def test_restaurar_repoe_o_lugar_de_cada_pessoa(copia, dados_reais):
    utilizadores.definir_unidade("bruno", None)
    backup.restaurar(copia)
    assert utilizadores.obter("bruno").unidade_id == dados_reais["empresa"].id


def test_restaurar_repoe_os_dados_dos_plugins(tmp_path, dados_reais):
    from core.paths import diretorio_dados_plugin
    from core.plugin_dados import ArmazenamentoPlugin

    armazem = ArmazenamentoPlugin("estoque", diretorio_dados_plugin("estoque"))
    armazem.migrar(1, "CREATE TABLE itens (id INTEGER PRIMARY KEY, nome TEXT)")
    armazem.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))
    destino = backup.criar(tmp_path / "c.zip")

    armazem.executar("DELETE FROM itens")
    assert armazem.consultar("SELECT nome FROM itens") == []

    backup.restaurar(destino)
    assert armazem.consultar("SELECT nome FROM itens") == [("Parafuso",)]


def test_restaurar_guarda_o_estado_anterior(copia, dados_reais):
    """A rede de segurança: enganar-se na cópia não pode ser irreversível."""
    db.adicionar_tarefa("Feita depois da cópia", "2030-02-01", criada_por="ana")

    emergencia = backup.restaurar(copia)

    assert emergencia.is_file()
    assert "Feita depois da cópia" not in [t[1] for t in db.buscar_tarefas()]

    # E a emergência é uma cópia a sério: dá para voltar atrás.
    backup.restaurar(emergencia)
    assert "Feita depois da cópia" in [t[1] for t in db.buscar_tarefas()]


def test_restaurar_limpa_o_que_nao_estava_na_copia(tmp_path, dados_reais):
    """Sobras do estado anterior misturadas com o restaurado seriam pior."""
    from core.paths import diretorio_dados_plugin

    destino = backup.criar(tmp_path / "c.zip")
    intruso = diretorio_dados_plugin("depois") / "ficheiro.txt"
    intruso.write_text("criado depois da cópia", encoding="utf-8")

    backup.restaurar(destino)
    assert not intruso.exists()


# ==================================================== O QUE TEM DE SER RECUSADO


def test_um_ficheiro_que_nao_e_zip(tmp_path):
    falso = tmp_path / "nao.zip"
    falso.write_text("isto não é um zip", encoding="utf-8")
    with pytest.raises(ArquivoInvalidoError):
        backup.inspecionar(falso)


def test_um_zip_sem_manifesto(tmp_path):
    caminho = tmp_path / "sem.zip"
    with zipfile.ZipFile(caminho, "w") as arquivo:
        arquivo.writestr(backup.NOME_BANCO, b"conteudo")
    with pytest.raises(ArquivoInvalidoError, match="manifesto"):
        backup.inspecionar(caminho)


def test_um_ficheiro_que_nao_existe(tmp_path):
    with pytest.raises(ArquivoInvalidoError):
        backup.inspecionar(tmp_path / "nao-existe.zip")


@pytest.mark.parametrize(
    "nome",
    [
        "../fora.txt",
        "config/../../fora.txt",
        "/etc/passwd",
        "C:/Windows/system32/mau.dll",
        "~/.ssh/authorized_keys",
        "..\\fora.txt",
    ],
)
def test_um_caminho_que_escapa_e_recusado(tmp_path, copia, nome):
    """A mesma defesa dos pacotes de plugins: a cópia também vem de fora."""
    adulterada = tmp_path / "adulterada.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(adulterada, "w") as saida:
        for info in origem.infolist():
            saida.writestr(info.filename, origem.read(info.filename))
        saida.writestr(nome, b"conteudo hostil")

    with pytest.raises(ArquivoInvalidoError):
        backup.inspecionar(adulterada)


def test_um_ficheiro_fora_dos_sitios_conhecidos_e_recusado(tmp_path, copia):
    """Só três sítios fazem parte de uma cópia nossa."""
    adulterada = tmp_path / "adulterada.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(adulterada, "w") as saida:
        for info in origem.infolist():
            saida.writestr(info.filename, origem.read(info.filename))
        saida.writestr("plugins/installed/x/plugin.py", b"raise SystemExit()")

    with pytest.raises(ArquivoInvalidoError, match="inesperado"):
        backup.inspecionar(adulterada)


def test_uma_copia_de_uma_versao_mais_recente_e_recusada(tmp_path, copia):
    """Ler um esquema do futuro é ler colunas que não se conhecem."""
    adulterada = _com_manifesto(tmp_path, copia, esquema=db.VERSAO_ESQUEMA + 1)
    with pytest.raises(BackupIncompativelError, match="Atualize"):
        backup.restaurar(adulterada)


def test_um_formato_mais_recente_e_recusado(tmp_path, copia):
    adulterada = _com_manifesto(tmp_path, copia, formato=backup.FORMATO + 1)
    with pytest.raises(BackupIncompativelError):
        backup.restaurar(adulterada)


def test_uma_copia_mais_antiga_e_aceite_e_migrada(tmp_path, copia, dados_reais):
    """O caso normal de quem restaura numa versão nova da aplicação."""
    antiga = _com_manifesto(tmp_path, copia, esquema=db.VERSAO_ESQUEMA - 1)
    backup.restaurar(antiga)
    assert db.versao_do_esquema() == db.VERSAO_ESQUEMA


def test_uma_copia_sem_banco_e_recusada(tmp_path, copia):
    sem_banco = tmp_path / "sem-banco.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(sem_banco, "w") as saida:
        for info in origem.infolist():
            if info.filename != backup.NOME_BANCO:
                saida.writestr(info.filename, origem.read(info.filename))

    with pytest.raises(ArquivoInvalidoError, match="banco"):
        backup.restaurar(sem_banco)


def test_um_banco_ilegivel_e_recusado(tmp_path, copia):
    corrompida = tmp_path / "corrompida.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(corrompida, "w") as saida:
        for info in origem.infolist():
            conteudo = (
                b"isto nao e um banco"
                if info.filename == backup.NOME_BANCO
                else origem.read(info.filename)
            )
            saida.writestr(info.filename, conteudo)

    with pytest.raises(ArquivoInvalidoError):
        backup.restaurar(corrompida)


def test_uma_copia_recusada_nao_toca_nos_dados(tmp_path, copia, dados_reais):
    """O teste que mais importa: falhar ao restaurar não pode custar nada."""
    db.adicionar_tarefa("O que eu tinha", "2030-03-01", criada_por="ana")
    antes = sorted(t[1] for t in db.buscar_tarefas())

    corrompida = tmp_path / "corrompida.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(corrompida, "w") as saida:
        for info in origem.infolist():
            conteudo = (
                b"lixo"
                if info.filename == backup.NOME_BANCO
                else origem.read(info.filename)
            )
            saida.writestr(info.filename, conteudo)

    with pytest.raises(ArquivoInvalidoError):
        backup.restaurar(corrompida)

    assert sorted(t[1] for t in db.buscar_tarefas()) == antes
    assert not (diretorio_dados_utilizador() / "antes-do-restauro.zip").exists(), (
        "não devia ter chegado a fazer a cópia de emergência"
    )


@pytest.mark.parametrize(
    "manifesto",
    [
        "não é json",
        '{"formato": 1}',
        '["uma", "lista"]',
        '{"formato": "x", "app_version": "1", "esquema": 1, "criado_em": "a"}',
    ],
)
def test_um_manifesto_malformado_e_recusado(tmp_path, copia, manifesto):
    adulterada = tmp_path / "adulterada.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(adulterada, "w") as saida:
        for info in origem.infolist():
            conteudo = (
                manifesto.encode("utf-8")
                if info.filename == backup.NOME_MANIFESTO
                else origem.read(info.filename)
            )
            saida.writestr(info.filename, conteudo)

    with pytest.raises(ArquivoInvalidoError):
        backup.inspecionar(adulterada)


# ==================================================================== MANIFESTO


def test_o_manifesto_sobrevive_a_ida_e_volta():
    original = Manifesto(
        formato=1,
        app_version="1.0.0",
        esquema=8,
        criado_em="2026-09-11T14:30:00",
        plugins=(("calendar", "1.0.0"),),
    )
    copia = Manifesto.de_dicionario(json.loads(json.dumps(original.para_dicionario())))
    assert copia == original


def test_o_manifesto_regista_os_plugins_para_memoria(copia):
    """Não os instala — diz quais eram, para se saber o que reinstalar."""
    manifesto = backup.inspecionar(copia)
    assert isinstance(manifesto.plugins, tuple)


def _com_manifesto(tmp_path, copia, **alteracoes):
    """Reescreve uma cópia com o manifesto alterado."""
    destino = tmp_path / f"alterada-{len(alteracoes)}-{abs(hash(str(alteracoes)))}.zip"
    with zipfile.ZipFile(copia) as origem:
        dados = json.loads(origem.read(backup.NOME_MANIFESTO).decode("utf-8"))
        dados.update(alteracoes)
        with zipfile.ZipFile(destino, "w") as saida:
            for info in origem.infolist():
                conteudo = (
                    json.dumps(dados).encode("utf-8")
                    if info.filename == backup.NOME_MANIFESTO
                    else origem.read(info.filename)
                )
                saida.writestr(info.filename, conteudo)
    return destino
