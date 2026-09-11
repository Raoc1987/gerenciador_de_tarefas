"""Testes da tela *Configurações → Estrutura*.

A janela é onde a hierarquia deixa de ser uma tabela no banco e passa a ser
uma coisa que alguém pode desenhar. O que interessa verificar é que mostra a
árvore como árvore, que não oferece movimentos impossíveis, e que um erro do
núcleo chega ao utilizador como mensagem em vez de rebentar a janela.
"""

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")

from core import organizacao, permissoes  # noqa: E402
from core.organizacao import TipoUnidade  # noqa: E402


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
def acme():
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    engenharia = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, empresa.id)
    plataforma = organizacao.criar("Plataforma", TipoUnidade.EQUIPA, engenharia.id)
    financeiro = organizacao.criar("Financeiro", TipoUnidade.DEPARTAMENTO, empresa.id)
    return {
        "empresa": empresa,
        "engenharia": engenharia,
        "plataforma": plataforma,
        "financeiro": financeiro,
    }


def abrir(raiz):
    from organizacao_ui import JanelaOrganizacao

    permissoes.definir_sessao("admin", "administrador", persistir=False)
    return JanelaOrganizacao(raiz)


@pytest.fixture
def janela(raiz):
    """A janela sobre o que existir no momento em que é aberta."""
    tela = abrir(raiz)
    yield tela
    tela.destroy()


@pytest.fixture
def janela_acme(acme, raiz):
    """A janela já com a estrutura desenhada.

    Depende de ``acme`` de propósito: uma janela construída antes da estrutura
    existir mostra uma árvore vazia, e os testes ficavam a agir sobre linhas
    que não estão lá.
    """
    tela = abrir(raiz)
    yield tela
    tela.destroy()


# ================================================================== DESENHO


def test_a_arvore_e_desenhada_como_arvore(janela, acme):
    janela.recarregar()
    filhos_da_empresa = janela.arvore.get_children(str(acme["empresa"].id))
    assert set(filhos_da_empresa) == {
        str(acme["engenharia"].id),
        str(acme["financeiro"].id),
    }
    assert janela.arvore.get_children(str(acme["engenharia"].id)) == (
        str(acme["plataforma"].id),
    )


def test_so_as_raizes_estao_no_topo(janela, acme):
    janela.recarregar()
    assert janela.arvore.get_children("") == (str(acme["empresa"].id),)


def test_sem_estrutura_explica_o_que_fazer(janela):
    """Um ecrã vazio sem explicação é um beco."""
    janela.recarregar()
    assert janela.arvore.get_children("") == ()
    assert janela.vazio.winfo_manager(), "a explicação devia estar visível"


def test_a_explicacao_desaparece_quando_ha_estrutura(janela, acme):
    janela.recarregar()
    assert not janela.vazio.winfo_manager()


def test_as_inativas_continuam_a_aparecer_aqui(janela, acme):
    """Esconder uma unidade desativada a quem organiza é esconder a razão."""
    organizacao.definir_ativa(acme["plataforma"].id, False)
    janela.recarregar()

    assert janela.arvore.exists(str(acme["plataforma"].id))
    texto = janela.arvore.item(str(acme["plataforma"].id), "text")
    assert "inativa" in texto.lower()


# =================================================================== AÇÕES


def test_criar_uma_sub_unidade(janela_acme, acme, monkeypatch):
    import organizacao_ui

    monkeypatch.setattr(
        organizacao_ui.simpledialog, "askstring", lambda *a, **k: "Dados"
    )
    janela_acme.arvore.selection_set(str(acme["engenharia"].id))
    janela_acme.nova_subunidade()

    nomes = [u.nome for u in organizacao.filhos(acme["engenharia"].id)]
    assert "Dados" in nomes


def test_dentro_de_uma_empresa_nasce_um_departamento(janela_acme, acme, monkeypatch):
    import organizacao_ui

    monkeypatch.setattr(organizacao_ui.simpledialog, "askstring", lambda *a, **k: "Vendas")
    janela_acme.arvore.selection_set(str(acme["empresa"].id))
    janela_acme.nova_subunidade()

    nova = next(u for u in organizacao.filhos(acme["empresa"].id) if u.nome == "Vendas")
    assert nova.tipo == TipoUnidade.DEPARTAMENTO


def test_dentro_de_um_departamento_nasce_uma_equipa(janela_acme, acme, monkeypatch):
    import organizacao_ui

    monkeypatch.setattr(organizacao_ui.simpledialog, "askstring", lambda *a, **k: "Dados")
    janela_acme.arvore.selection_set(str(acme["engenharia"].id))
    janela_acme.nova_subunidade()

    nova = next(u for u in organizacao.filhos(acme["engenharia"].id) if u.nome == "Dados")
    assert nova.tipo == TipoUnidade.EQUIPA


def test_cancelar_nao_cria_nada(janela_acme, acme, monkeypatch):
    import organizacao_ui

    monkeypatch.setattr(organizacao_ui.simpledialog, "askstring", lambda *a, **k: None)
    janela_acme.arvore.selection_set(str(acme["engenharia"].id))
    janela_acme.nova_subunidade()

    assert [u.nome for u in organizacao.filhos(acme["engenharia"].id)] == ["Plataforma"]


def test_um_nome_repetido_vira_mensagem_e_nao_excecao(janela_acme, acme, monkeypatch):
    """O erro do núcleo tem de chegar ao utilizador, não ao ecrã de crash."""
    import organizacao_ui

    avisos = []
    monkeypatch.setattr(
        organizacao_ui.simpledialog, "askstring", lambda *a, **k: "Plataforma"
    )
    monkeypatch.setattr(
        organizacao_ui.messagebox, "showerror", lambda *a, **k: avisos.append(a)
    )
    janela_acme.arvore.selection_set(str(acme["engenharia"].id))
    janela_acme.nova_subunidade()

    assert avisos, "o utilizador tinha de ser avisado"
    assert len(organizacao.filhos(acme["engenharia"].id)) == 1


def test_remover_uma_unidade_com_conteudo_avisa(janela_acme, acme, monkeypatch):
    import organizacao_ui

    avisos = []
    monkeypatch.setattr(organizacao_ui.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(
        organizacao_ui.messagebox, "showerror", lambda *a, **k: avisos.append(a)
    )
    janela_acme.arvore.selection_set(str(acme["engenharia"].id))
    janela_acme.remover()

    assert avisos
    assert organizacao.obter(acme["engenharia"].id) is not None


def test_remover_pede_confirmacao(janela_acme, acme, monkeypatch):
    import organizacao_ui

    monkeypatch.setattr(organizacao_ui.messagebox, "askyesno", lambda *a, **k: False)
    janela_acme.arvore.selection_set(str(acme["plataforma"].id))
    janela_acme.remover()

    assert organizacao.obter(acme["plataforma"].id) is not None


def test_alternar_estado(janela_acme, acme):
    janela_acme.arvore.selection_set(str(acme["plataforma"].id))
    janela_acme.alternar_estado()
    assert organizacao.obter(acme["plataforma"].id).ativa is False

    janela_acme.arvore.selection_set(str(acme["plataforma"].id))
    janela_acme.alternar_estado()
    assert organizacao.obter(acme["plataforma"].id).ativa is True


# ================================================================== MOVER


def test_os_destinos_nao_incluem_a_propria_sub_arvore(janela, acme):
    """Oferecer um destino impossível é oferecer um erro."""
    janela.recarregar()
    destinos = {u.id for u in janela._destinos_para(acme["engenharia"])}

    assert acme["engenharia"].id not in destinos
    assert acme["plataforma"].id not in destinos
    assert acme["financeiro"].id in destinos


def test_o_pai_atual_nao_e_oferecido(janela, acme):
    janela.recarregar()
    destinos = {u.id for u in janela._destinos_para(acme["plataforma"])}
    assert acme["engenharia"].id not in destinos


def test_uma_empresa_nao_tem_para_onde_ir(janela, acme):
    janela.recarregar()
    assert janela._destinos_para(acme["empresa"]) == []


def test_mover_pelo_dialogo(janela_acme, acme, monkeypatch):
    import organizacao_ui

    def escolher(self, dialogo):
        dialogo.var.set(organizacao.caminho(acme["financeiro"].id))
        dialogo.confirmar()

    monkeypatch.setattr(organizacao_ui.JanelaOrganizacao, "wait_window", escolher)
    janela_acme.arvore.selection_set(str(acme["plataforma"].id))
    janela_acme.mover()

    assert organizacao.obter(acme["plataforma"].id).pai_id == acme["financeiro"].id


# ============================================================== PERMISSÕES


def test_quem_nao_administra_nao_ve_nem_mexe(raiz, acme):
    from organizacao_ui import JanelaOrganizacao

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    tela = JanelaOrganizacao(raiz)
    try:
        assert tela.arvore.get_children("") == ()
        assert tela.unidades() == []
        for botao in tela._botoes.values():
            assert "disabled" in botao.state()
    finally:
        tela.destroy()
