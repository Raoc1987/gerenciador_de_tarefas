"""O que acontece num ecrã pequeno e com a letra grande.

Estes testes existem por causa de medições, e não de ideias. Estão descritas
em ``docs/MEDICOES.md``; o que interessa aqui é que os dois defeitos que elas
encontraram não voltem:

* a 940×620 — **o mínimo que a própria aplicação declarava** — a caixa
  "Análise" ficava abaixo da dobra e não havia como lá chegar;
* a 150%, o mínimo continuava a ser 940×620 em píxeis, e nessa janela a barra
  de topo sobrepunha-se a si própria: o botão ``Ctrl+F`` ficava cortado a
  ``C`` e o seletor de idioma **desaparecia sem aviso**.

Nenhum dos dois dava erro. É o pior tipo de defeito de interface, e é o tipo
que só uma medição apanha.
"""

import tkinter as tk
from tkinter import ttk

import pytest

from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="sem interface gráfica disponível"
)


@pytest.fixture
def raiz():
    """Uma janela **no ecrã**, e não escondida.

    ``winfo_y`` e ``winfo_ismapped`` respondem 0 para tudo numa janela
    retirada: um teste de geometria contra uma janela escondida passa ou
    falha por acidente. Aqui a geometria é o assunto.
    """
    janela = criar_janela_com_retentativa(tk.Tk)
    janela.geometry("900x640+40+40")
    janela.update_idletasks()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


# ============================================== a escala e os tamanhos fixos


def test_sem_janela_a_escala_e_cem_por_cento():
    """Quem pergunta fora da interface recebe um número, não uma exceção."""
    from aparencia import em_pixeis, escala

    assert escala() == 1.0
    assert em_pixeis(940) == 940


def test_a_escala_segue_o_que_o_tk_diz(raiz):
    from aparencia import em_pixeis, escala
    from aparencia.tema import ESCALA_BASE

    raiz.tk.call("tk", "scaling", ESCALA_BASE * 1.5)
    assert escala(raiz) == pytest.approx(1.5, abs=0.01)
    assert em_pixeis(100, raiz) == pytest.approx(150, abs=1)


def test_um_minimo_nunca_e_maior_do_que_o_ecra(raiz):
    """Um mínimo que não cabe tira a quem lá está a única saída que tinha.

    Escalar 940×620 por 1.5 dá 1410×930, e um portátil de 1366×768 não tem
    lá isso. Sem esta trava, a janela deixava de se poder encolher até ao que
    existe.
    """
    from aparencia import cabe_no_ecra

    largura, altura = cabe_no_ecra(99_000, 99_000, raiz)
    assert largura <= raiz.winfo_screenwidth()
    assert altura <= raiz.winfo_screenheight()


def test_o_que_ja_cabe_nao_e_encolhido(raiz):
    from aparencia import cabe_no_ecra

    assert cabe_no_ecra(320, 240, raiz) == (320, 240)


def test_a_janela_pede_um_minimo_que_acompanha_a_letra(raiz):
    """A 150% o mínimo tem de crescer — ou o conteúdo deixa de lá caber."""
    import gui
    from aparencia.tema import ESCALA_BASE
    from core import permissoes

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    raiz.tk.call("tk", "scaling", ESCALA_BASE * 1.5)
    app = gui.criar_janela(raiz)
    try:
        largura, altura = app.wm_minsize()
        # Cresceu face aos 940×620 pensados a 100% — a menos que o ecrã do
        # sítio onde isto corre seja mais pequeno do que isso, e aí a trava
        # do ecrã manda, que é o comportamento certo.
        esperado = min(940 * 1.5, raiz.winfo_screenwidth())
        # `approx` e não igualdade: o valor que se põe no ``tk scaling`` não
        # volta exatamente igual, e 1409 em vez de 1410 não é um defeito —
        # é a precisão de um float a atravessar o Tcl.
        assert largura == pytest.approx(esperado, abs=2), (
            "o mínimo não acompanhou a escala"
        )
        assert altura <= raiz.winfo_screenheight()
    finally:
        app.gerenciador_de_plugins.desativar_todos()


# ========================================== o que não cabe tem de se alcançar


@pytest.fixture
def rolo(raiz):
    import aparencia
    from painel import Rolo

    aparencia.aplicar(raiz, "claro")
    janela = Rolo(raiz)
    janela.pack(fill=tk.BOTH, expand=True)
    raiz.geometry("400x300")
    raiz.update_idletasks()
    raiz.update()
    return janela


def encher(rolo, quantas: int) -> None:
    for i in range(quantas):
        ttk.Label(rolo.interior, text=f"linha {i}").pack(anchor=tk.W)
    rolo.winfo_toplevel().update_idletasks()
    rolo.winfo_toplevel().update()


def na_moldura(rolo) -> bool:
    """Se a barra está arrumada na moldura do rolo.

    E não ``winfo_ismapped``: isso responde também pelo estado da janela no
    sistema, e numa suíte que abre dezenas de interpretadores Tk no mesmo
    processo responde 0 por motivos que nada têm a ver com o rolo. Já apanhou
    este teste uma vez, e passava sozinho. O que aqui se decide é se a barra
    foi posta, que é a decisão do rolo.
    """
    return rolo._barra in rolo.pack_slaves()


def test_o_que_sobra_por_baixo_tem_a_cor_do_painel(rolo):
    """Um Canvas não é um widget ttk e não recebe o tema.

    Sem isto ficava uma faixa cinzenta de origem do Tk no fundo do painel,
    tanto mais visível quanto mais espaço sobrasse.
    """
    from aparencia import cores

    encher(rolo, 2)
    assert rolo._tela.cget("background") == cores()["superficie"]


def test_sem_nada_a_mais_nao_ha_barra(rolo):
    """Uma barra desativada é ruído a dizer "isto podia deslocar-se"."""
    encher(rolo, 2)
    assert rolo.precisa_de_barra() is False
    assert na_moldura(rolo) is False


def test_conteudo_a_mais_faz_aparecer_a_barra(rolo):
    encher(rolo, 200)
    assert rolo.precisa_de_barra() is True
    assert na_moldura(rolo) is True


def test_a_largura_de_dentro_segue_a_de_fora(rolo):
    """Sem isto a grelha nunca recebia a largura real e ficava com 4 colunas.

    Que é o contrário do que a grelha existe para fazer.
    """
    encher(rolo, 5)
    rolo.winfo_toplevel().update()
    assert rolo.interior.winfo_width() == rolo._tela.winfo_width()


def test_o_teclado_desloca_e_nao_so_a_roda(rolo):
    """Um ecrã que só se percorre com rato é metade da acessibilidade."""
    encher(rolo, 200)
    rolo.winfo_toplevel().update()

    topo_antes = rolo._tela.yview()[0]
    rolo._paginas(1)
    rolo.winfo_toplevel().update_idletasks()
    assert rolo._tela.yview()[0] > topo_antes, "Page Down não deslocou nada"

    rolo._paginas(-1)
    rolo.winfo_toplevel().update_idletasks()
    assert rolo._tela.yview()[0] == pytest.approx(topo_antes, abs=0.01)


def test_quando_o_conteudo_encolhe_a_vista_volta_ao_topo(rolo):
    """Senão ficava uma faixa em branco por baixo do que já cabia todo."""
    encher(rolo, 200)
    rolo.winfo_toplevel().update()

    for filho in list(rolo.interior.winfo_children())[3:]:
        filho.destroy()
    rolo.winfo_toplevel().update()

    assert rolo.precisa_de_barra() is False
    assert rolo._tela.yview()[0] == pytest.approx(0.0, abs=0.01)


def test_apagar_conteudo_fora_da_vista_precisa_de_aviso(rolo):
    """O limite do que o Tk consegue dizer sozinho, guardado por um teste.

    Com o painel deslocado, o que se apaga está **fora da vista** — e o Tk
    não reporta geometria de widgets que ninguém está a ver. O ``<Configure>``
    não chega, e a barra fica a prometer conteúdo que já não existe.

    Por isso :meth:`Rolo.sincronizar` é público e o painel chama-o depois de
    mexer no que mostra. Este teste prova as duas metades: que sem aviso fica
    mesmo desacertado, e que com aviso acerta.
    """
    encher(rolo, 200)
    rolo.winfo_toplevel().update()
    rolo._paginas(1)
    rolo.winfo_toplevel().update()

    for filho in list(rolo.interior.winfo_children())[3:]:
        filho.destroy()
    rolo.winfo_toplevel().update()
    assert rolo._barra_visivel is True, (
        "o Tk passou a reportar isto sozinho; o aviso deixou de ser preciso"
    )

    rolo.sincronizar()
    rolo.winfo_toplevel().update()
    assert rolo._barra_visivel is False
    assert rolo._tela.yview()[0] == pytest.approx(0.0, abs=0.01)


# ============================================ o painel, que foi o caso real


def test_o_painel_alcanca_a_analise_numa_janela_baixa(raiz):
    """O caso medido: a 940×620 a caixa "Análise" era inalcançável.

    Não se testa que ela esteja visível — numa janela baixa não está, e não
    tem de estar. Testa-se que **há como lá chegar**, que é o que faltava.
    """
    import aparencia
    from core import permissoes
    from dashboard_ui import PainelDashboard

    permissoes.definir_sessao("ana", "administrador", persistir=False)
    aparencia.aplicar(raiz, "claro")
    raiz.geometry("940x620")
    painel = PainelDashboard(raiz)
    painel.pack(fill=tk.BOTH, expand=True)
    raiz.update_idletasks()
    raiz.update()

    assert painel._grelha.winfo_reqheight() > painel._rolo._tela.winfo_height(), (
        "o painel coube todo; este teste deixou de medir o que dizia medir"
    )
    assert painel._rolo.precisa_de_barra() is True


def test_a_razao_de_o_painel_estar_vazio_continua_a_aparecer(raiz):
    """A grelha mudou de pai ao entrar no rolo, e o aviso ficou órfão.

    ``pack(before=...)`` com um widget de **outro** pai não faz nada e não
    levanta: a mensagem desaparecia do ecrã em silêncio, e a suíte inteira
    continuava verde. É por isso que este teste olha para o ``pack``, e não
    só para o texto.
    """
    import aparencia
    from core import permissoes
    from dashboard_ui import PainelDashboard

    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    aparencia.aplicar(raiz, "claro")
    painel = PainelDashboard(raiz)
    painel.pack(fill=tk.BOTH, expand=True)
    painel._dizer("sem permissão para ver isto")
    raiz.update_idletasks()

    assert painel._aviso in painel.pack_slaves(), "o aviso não chegou ao ecrã"
    assert painel._aviso.winfo_y() < painel._rolo.winfo_y(), (
        "o aviso ficou por baixo do painel a que se refere"
    )
