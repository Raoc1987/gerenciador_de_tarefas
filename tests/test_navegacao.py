"""Testes da concha de navegação: barra lateral, registo e paleta de comandos.

O que estes testes protegem, acima de tudo, é a **compatibilidade**: a concha
substituiu o ``ttk.Notebook`` da janela principal, e a promessa foi que
nenhum plugin instalado teria de mudar uma linha. Essa promessa é verificável
— os métodos que o contrato usa têm de aceitar o que o Notebook aceitava.
"""

import tkinter as tk
from tkinter import ttk

import pytest

from core import permissoes
from core.permissoes import Permissao
from navegacao import comandos, registo


@pytest.fixture
def raiz():
    """Uma janela Tk descartável, como nos outros testes de interface."""
    from conftest import criar_janela_com_retentativa

    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def registos_limpos():
    registo.limpar()
    comandos.limpar()
    yield
    registo.limpar()
    comandos.limpar()


@pytest.fixture
def concha(raiz):
    import aparencia
    from navegacao import Concha

    aparencia.aplicar(raiz, "claro")
    janela = Concha(raiz)
    janela.pack(fill=tk.BOTH, expand=True)
    return janela


# ================================================== compatível com Notebook


def test_a_concha_aceita_o_que_o_notebook_aceitava(concha, raiz):
    """Widget, índice e nome — as três formas de ``tab_id`` do Tk.

    Havia código a usar as três. Aceitar só uma tornaria "substitui o
    Notebook" uma intenção em vez de um facto.
    """
    a, b = ttk.Frame(concha), ttk.Frame(concha)
    concha.add(a, text="Painel")
    concha.add(b, text="Tarefas")

    assert concha.tab(a, "text") == "Painel"          # pelo widget
    assert concha.tab(1, "text") == "Tarefas"         # pelo índice
    assert concha.tab(str(a), "text") == "Painel"     # pelo nome
    assert concha.index("end") == 2
    assert concha.tabs() == (str(a), str(b))


def test_o_primeiro_painel_fica_visivel_sem_ninguem_pedir(concha):
    a = ttk.Frame(concha)
    concha.add(a, text="Painel")
    assert concha.select() is a


def test_mudar_de_seccao_nao_destroi_a_anterior(concha):
    """O estado de um ecrã sobrevive a sair dele e voltar.

    Reconstruir ao mudar de secção perderia o filtro escolhido e a linha
    selecionada — e é o que faz um produto parecer que se esquece.
    """
    a, b = ttk.Frame(concha), ttk.Frame(concha)
    concha.add(a, text="A")
    concha.add(b, text="B")
    concha.select(b)
    assert a.winfo_exists()
    concha.select(a)
    assert concha.select() is a


def test_renomear_muda_a_lateral_e_o_titulo_da_pagina(concha):
    a = ttk.Frame(concha)
    concha.add(a, text="Antigo")
    concha.tab(a, text="Novo")
    assert concha.tab(a, "text") == "Novo"


def test_tirar_o_painel_visivel_mostra_outro(concha):
    a, b = ttk.Frame(concha), ttk.Frame(concha)
    concha.add(a, text="A")
    concha.add(b, text="B")
    concha.select(a)
    concha.forget(a)
    assert concha.index("end") == 1
    assert concha.select() is b


def test_tirar_um_painel_que_nao_existe_nao_rebenta(concha):
    concha.forget(ttk.Frame(concha))


def test_a_lateral_abre_e_fecha(concha):
    assert concha.alternar_lateral() is False
    assert concha.alternar_lateral() is True


# ==================================================== registo de destinos


def test_um_destino_com_permissao_que_a_sessao_nao_tem_nao_aparece():
    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    registo.registar("livre", "Livre", grupo="principal")
    registo.registar("fechado", "Fechado", grupo="sistema",
                     permissao=Permissao.SISTEMA_ADMIN.value)

    visiveis = {d.id for _, ds in registo.por_grupo() for d in ds}
    assert visiveis == {"livre"}


def test_os_grupos_vazios_nao_aparecem():
    """Um título de secção sem nada por baixo é ruído."""
    registo.registar("um", "Um", grupo="principal")
    grupos = [g for g, _ in registo.por_grupo()]
    assert grupos == ["principal"]


def test_a_ordem_e_a_declarada_e_nao_a_de_registo():
    registo.registar("z", "Z", grupo="principal", ordem=10)
    registo.registar("a", "A", grupo="principal", ordem=90)
    ids = [d.id for _, ds in registo.por_grupo() for d in ds]
    assert ids == ["z", "a"]


def test_um_grupo_inventado_e_um_erro():
    with pytest.raises(ValueError):
        registo.registar("x", "X", grupo="miscelanea")


def test_um_modulo_fica_no_seu_espaco_de_nomes():
    with pytest.raises(ValueError):
        registo.registar("tarefas.minhas", "X", dono="estoque")


def test_os_destinos_de_um_plugin_saem_com_ele():
    registo.registar("estoque.itens", "Itens", dono="estoque")
    assert registo.esquecer_por_dono("estoque") == 1
    assert registo.por_grupo() == []


# ======================================================== paleta de comandos


def test_um_comando_sem_permissao_nao_aparece():
    permissoes.definir_sessao("carla", "visualizador", persistir=False)
    comandos.registar("livre", "Livre", lambda: None)
    comandos.registar("fechado", "Fechado", lambda: None,
                      permissao=Permissao.SISTEMA_ADMIN.value)
    assert [c.id for c in comandos.disponiveis()] == ["livre"]


def test_procurar_poe_a_frente_o_que_comeca_pelo_termo():
    """Quem escreve "rel" quer "Relatórios" antes de "Abrir relatório"."""
    comandos.registar("b", "Abrir relatorio", lambda: None)
    comandos.registar("a", "Relatorios", lambda: None)
    assert [c.id for c in comandos.procurar("rel")] == ["a", "b"]


def test_procurar_ignora_acentos():
    comandos.registar("a", "Auditoria", lambda: None)
    assert [c.id for c in comandos.procurar("áud")] == ["a"]


def test_sem_termo_mostra_tudo():
    """Abrir a paleta e ver uma lista vazia não diz o que se pode escrever."""
    comandos.registar("a", "Um", lambda: None)
    comandos.registar("b", "Dois", lambda: None)
    assert len(comandos.procurar("")) == 2


def test_um_comando_precisa_de_algo_para_executar():
    with pytest.raises(ValueError):
        comandos.registar("x", "X", executar=None)


def test_os_comandos_de_um_plugin_saem_com_ele():
    comandos.registar("estoque.repor", "Repor", lambda: None, dono="estoque")
    assert comandos.esquecer_por_dono("estoque") == 1
    assert comandos.disponiveis() == []


def test_a_paleta_filtra_e_executa(raiz):
    import aparencia
    from navegacao.comandos import PaletaDeComandos

    aparencia.aplicar(raiz, "claro")
    feitos = []
    comandos.registar("a", "Abrir plugins", lambda: feitos.append("plugins"))
    comandos.registar("b", "Abrir auditoria", lambda: feitos.append("auditoria"))

    paleta = PaletaDeComandos(raiz)
    try:
        paleta._termo.set("audit")
        raiz.update_idletasks()
        assert paleta._lista.size() == 1
        paleta._executar()
        assert feitos == ["auditoria"]
    finally:
        if paleta.winfo_exists():  # pragma: no cover - já fechada ao executar
            paleta.destroy()


def test_um_comando_que_rebenta_nao_leva_a_aplicacao_com_ele(raiz):
    """A paleta vai acabar por correr comandos de plugins.

    A mesma regra do resto do motor: código de fora falha sozinho.
    """
    import aparencia
    from navegacao.comandos import PaletaDeComandos

    aparencia.aplicar(raiz, "claro")

    def explode():
        raise RuntimeError("o comando tinha um erro")

    comandos.registar("mau", "Explodir", explode)
    paleta = PaletaDeComandos(raiz)
    paleta._executar()  # não levanta
    assert not paleta.winfo_exists()
