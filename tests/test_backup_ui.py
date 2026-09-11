"""Testes da tela *Configurações → Cópia de segurança*.

O que interessa aqui não é o aspeto: é que ninguém consiga substituir os seus
dados sem ter visto de que cópia se trata, e que um ficheiro inválido seja
recusado **antes** de a pergunta ser feita.
"""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

import database as db  # noqa: E402
from core import backup, permissoes  # noqa: E402


@pytest.fixture
def raiz():
    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture
def com_dados():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    db.adicionar_tarefa("Não me percas", "2030-01-01", criada_por="ana")


@pytest.fixture
def janela(com_dados, raiz):
    from backup_ui import JanelaBackup

    tela = JanelaBackup(raiz)
    yield tela
    tela.destroy()


# ==================================================================== CRIAR


def test_guardar_escreve_o_ficheiro(janela, tmp_path, monkeypatch):
    import backup_ui

    destino = tmp_path / "minha-copia.zip"
    monkeypatch.setattr(
        backup_ui.filedialog, "asksaveasfilename", lambda *a, **k: str(destino)
    )
    assert janela.criar() == str(destino)
    assert destino.is_file()
    assert backup.inspecionar(destino).app_version


def test_cancelar_nao_escreve_nada(janela, tmp_path, monkeypatch):
    import backup_ui

    monkeypatch.setattr(backup_ui.filedialog, "asksaveasfilename", lambda *a, **k: "")
    assert janela.criar() is None
    assert list(tmp_path.glob("*.zip")) == []


def test_um_erro_ao_guardar_vira_mensagem(janela, monkeypatch):
    import backup_ui

    monkeypatch.setattr(
        backup_ui.filedialog, "asksaveasfilename", lambda *a, **k: "x.zip"
    )
    monkeypatch.setattr(
        backup_ui.backup, "criar", lambda *a: (_ for _ in ()).throw(OSError("disco cheio"))
    )
    assert janela.criar() is None
    assert "disco cheio" in janela.mensagem.cget("text")


# ================================================================= RESTAURAR


@pytest.fixture
def copia(com_dados, tmp_path):
    return backup.criar(tmp_path / "copia.zip")


def test_restaurar_mostra_de_que_copia_se_trata(janela, copia, monkeypatch):
    """A pergunta tem de dizer de quando é a cópia, não só "tem a certeza?"."""
    import backup_ui

    perguntas = []
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(copia)
    )
    monkeypatch.setattr(
        backup_ui.messagebox,
        "askyesno",
        lambda titulo, texto, **k: perguntas.append(texto) or False,
    )
    janela.restaurar()

    assert perguntas, "devia ter perguntado"
    manifesto = backup.inspecionar(copia)
    assert manifesto.data_legivel in perguntas[0]
    assert manifesto.app_version in perguntas[0]


def test_dizer_que_nao_nao_muda_nada(janela, copia, monkeypatch):
    import backup_ui

    db.remover_tarefa(db.buscar_tarefas()[0][0])
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(copia)
    )
    monkeypatch.setattr(backup_ui.messagebox, "askyesno", lambda *a, **k: False)

    assert janela.restaurar() is False
    assert db.buscar_tarefas() == []


def test_dizer_que_sim_repoe_os_dados(janela, copia, monkeypatch):
    import backup_ui

    db.remover_tarefa(db.buscar_tarefas()[0][0])
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(copia)
    )
    monkeypatch.setattr(backup_ui.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(backup_ui.messagebox, "showinfo", lambda *a, **k: None)

    assert janela.restaurar() is True
    assert [t[1] for t in db.buscar_tarefas()] == ["Não me percas"]


def test_avisa_que_e_preciso_reiniciar(janela, copia, monkeypatch):
    """A aplicação a correr tem ligações e caches do banco antigo."""
    import backup_ui

    avisos = []
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(copia)
    )
    monkeypatch.setattr(backup_ui.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(
        backup_ui.messagebox, "showinfo", lambda t, texto, **k: avisos.append(texto)
    )
    janela.restaurar()

    assert len(avisos) == 1
    assert "abrir a aplicação" in avisos[0]


def test_um_ficheiro_invalido_e_recusado_antes_de_perguntar(
    janela, tmp_path, monkeypatch
):
    """Perguntar "quer substituir os seus dados?" sobre lixo é assustar à toa."""
    import backup_ui

    falso = tmp_path / "nao.zip"
    falso.write_text("isto não é um zip", encoding="utf-8")

    perguntou = []
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(falso)
    )
    monkeypatch.setattr(
        backup_ui.messagebox, "askyesno", lambda *a, **k: perguntou.append(1) or True
    )

    assert janela.restaurar() is False
    assert not perguntou, "não devia ter chegado a perguntar"
    assert janela.mensagem.cget("text")


def test_uma_copia_de_versao_mais_recente_e_recusada_antes_de_perguntar(
    janela, copia, tmp_path, monkeypatch
):
    import json
    import zipfile

    import backup_ui

    adulterada = tmp_path / "futuro.zip"
    with zipfile.ZipFile(copia) as origem, zipfile.ZipFile(adulterada, "w") as saida:
        for info in origem.infolist():
            conteudo = origem.read(info.filename)
            if info.filename == backup.NOME_MANIFESTO:
                dados = json.loads(conteudo.decode("utf-8"))
                dados["esquema"] = db.VERSAO_ESQUEMA + 1
                conteudo = json.dumps(dados).encode("utf-8")
            saida.writestr(info.filename, conteudo)

    perguntou = []
    monkeypatch.setattr(
        backup_ui.filedialog, "askopenfilename", lambda *a, **k: str(adulterada)
    )
    monkeypatch.setattr(
        backup_ui.messagebox, "askyesno", lambda *a, **k: perguntou.append(1) or True
    )

    assert janela.restaurar() is False
    assert not perguntou
    assert [t[1] for t in db.buscar_tarefas()] == ["Não me percas"]


def test_cancelar_a_escolha_do_ficheiro(janela, monkeypatch):
    import backup_ui

    monkeypatch.setattr(backup_ui.filedialog, "askopenfilename", lambda *a, **k: "")
    assert janela.restaurar() is False


# ================================================================ PERMISSÕES


def test_quem_nao_administra_nao_mexe(com_dados, raiz):
    from backup_ui import JanelaBackup

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    tela = JanelaBackup(raiz)
    try:
        assert "disabled" in tela.botao_criar.state()
        assert "disabled" in tela.botao_restaurar.state()
    finally:
        tela.destroy()
