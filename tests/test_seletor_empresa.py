"""Escolher que empresa se está a ver — e nunca poder escolher uma que não é sua.

O [ADR-0011] isolou as tarefas por empresa e o [ADR-0012] os dados dos
módulos. Faltava a outra ponta: **quem não pertence a empresa nenhuma vê
todas ao mesmo tempo**, misturadas. É o caso de quem instala e administra sem
se pôr no organigrama — e é exatamente quem precisa de conseguir olhar para
uma de cada vez.

A pergunta difícil não é mostrar uma lista. É que um seletor mal feito é uma
**escalada de privilégio com ar de menu**: se pudesse alargar o alcance,
alguém limitado à Acme via a Rival carregando num botão.

Por isso a regra é uma só, e é a primeira coisa que estes testes guardam:
**o seletor estreita, nunca alarga.**
"""

import pytest

import banco_de_dados as db
import tarefas_servico as servico
from core import eventos, organizacao, permissoes, utilizadores
from core.organizacao import EmpresaForaDoAlcanceError, TipoUnidade


def como(utilizador: str, papel: str = "administrador") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


def como_a_instalacao() -> None:
    """A sessão de quem administra a instalação: não está no organigrama.

    Montar a estrutura de dentro de uma empresa deixou de ser possível, e de
    propósito — quem está na Acme não põe ninguém na Rival. Quem monta é a
    instalação, e este é o seu lugar: nenhum.
    """
    permissoes.definir_sessao("instalacao", "administrador", persistir=False)


def descricoes() -> set:
    return {t[1] for t in servico.listar()}


@pytest.fixture
def duas_empresas():
    """Acme (Ana) e Rival (Bruno), e uma tarefa anterior à estrutura."""
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    acme_eng = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, acme.id)
    rival = organizacao.criar("Rival", TipoUnidade.EMPRESA)
    rival_eng = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, rival.id)

    # A estrutura monta-se antes de entrar numa sessão de empresa: quem está
    # dentro da Acme já não pode pôr ninguém na Rival.
    lugares = (("ana", acme_eng.id), ("bruno", rival_eng.id))
    for nome, unidade in lugares:
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="administrador")
        utilizadores.definir_unidade(nome, unidade)
    for nome, _ in lugares:
        como(nome)
        servico.adicionar(f"Tarefa da {nome}", "2030-01-01")

    db.adicionar_tarefa("Antiga, sem estrutura", "2030-01-02")
    utilizadores.criar("root", "Uma-Senha-Longa-123", papel="administrador")
    return {"acme": acme, "rival": rival}


# ============================================ o seletor estreita, nunca alarga


def test_quem_pertence_a_uma_empresa_nao_pode_escolher_outra(duas_empresas):
    """A regra que faz a diferença entre um filtro e um buraco."""
    como("ana")
    with pytest.raises(EmpresaForaDoAlcanceError):
        organizacao.escolher_empresa(duas_empresas["rival"].id)

    assert "Tarefa da bruno" not in descricoes()


def test_uma_empresa_que_nao_existe_tambem_e_recusada(duas_empresas):
    como("root")
    with pytest.raises(EmpresaForaDoAlcanceError):
        organizacao.escolher_empresa(999_999)


def test_quem_pertence_a_uma_empresa_nao_tem_nada_para_escolher(duas_empresas):
    """Já só vê a sua: um seletor com uma entrada é um seletor a mais."""
    como("ana")
    alcance = organizacao.empresas_ao_alcance()
    assert [u.id for u in alcance] == [duas_empresas["acme"].id]


def test_quem_nao_esta_na_estrutura_alcanca_todas(duas_empresas):
    como("root")
    nomes = {u.nome for u in organizacao.empresas_ao_alcance()}
    assert nomes == {"Acme", "Rival"}


def test_com_uma_empresa_so_nao_ha_nada_para_escolher():
    organizacao.criar("Acme", TipoUnidade.EMPRESA)
    utilizadores.criar("ana", "Uma-Senha-Longa-123", papel="administrador")
    como("ana")
    assert organizacao.empresas_ao_alcance() == []


def test_sem_estrutura_nenhuma_nao_ha_nada_para_escolher():
    utilizadores.criar("ana", "Uma-Senha-Longa-123", papel="administrador")
    como("ana")
    assert organizacao.empresas_ao_alcance() == []


# ================================================= o que a escolha muda mesmo


def test_escolher_uma_empresa_estreita_as_tarefas(duas_empresas):
    """O caso todo, de ponta a ponta."""
    como("root")
    assert {"Tarefa da ana", "Tarefa da bruno"} <= descricoes()

    organizacao.escolher_empresa(duas_empresas["acme"].id)
    vistas = descricoes()
    assert "Tarefa da ana" in vistas
    assert "Tarefa da bruno" not in vistas, "viu a tarefa da outra empresa"


def test_voltar_a_todas_alarga_outra_vez(duas_empresas):
    como("root")
    organizacao.escolher_empresa(duas_empresas["acme"].id)
    organizacao.escolher_empresa(None)
    assert {"Tarefa da ana", "Tarefa da bruno"} <= descricoes()


def test_as_tarefas_sem_estrutura_continuam_visiveis_com_uma_empresa_escolhida(
    duas_empresas,
):
    """Não pertencem a empresa nenhuma, e ninguém as pode perder de vista."""
    como("root")
    organizacao.escolher_empresa(duas_empresas["acme"].id)
    assert "Antiga, sem estrutura" in descricoes()


def test_a_escolha_chega_aos_dados_dos_modulos(duas_empresas):
    """Um módulo pergunta ``contexto.empresa()``; tem de ouvir a mesma resposta.

    Se a escolha só valesse para as tarefas, a interface dizia "Acme" e o
    inventário continuava a mostrar as duas — duas verdades no mesmo ecrã.
    """
    como("root")
    assert organizacao.empresa_da_sessao() is None

    organizacao.escolher_empresa(duas_empresas["acme"].id)
    assert organizacao.empresa_da_sessao() == duas_empresas["acme"].id


def test_a_escolha_e_anunciada(duas_empresas):
    """A interface tem de voltar a desenhar: o que está no ecrã é de antes."""
    recebidos = []
    eventos.subscrever(eventos.EMPRESA_ESCOLHIDA, recebidos.append)

    como("root")
    organizacao.escolher_empresa(duas_empresas["acme"].id)

    assert recebidos, "ninguém soube que a vista mudou"
    assert recebidos[-1].dados["empresa"] == duas_empresas["acme"].id


# ======================================== a escolha não sobrevive a quem a fez


def test_a_escolha_de_uma_pessoa_nao_vale_para_a_seguinte(duas_empresas):
    """Duas pessoas a partilhar um computador é o caso normal numa empresa.

    Sem isto, quem entrasse a seguir herdava uma vista estreitada que nunca
    escolheu — e o pior é que não daria erro nenhum: veria menos, e acharia
    que era o que havia.
    """
    como("root")
    organizacao.escolher_empresa(duas_empresas["acme"].id)
    assert organizacao.empresa_escolhida() == duas_empresas["acme"].id

    utilizadores.criar("outro", "Uma-Senha-Longa-123", papel="administrador")
    como("outro")
    assert organizacao.empresa_escolhida() is None, "herdou a escolha de outro"
    assert {"Tarefa da ana", "Tarefa da bruno"} <= descricoes()


def test_uma_escolha_que_deixou_de_ser_valida_vale_o_mesmo_que_nenhuma(
    duas_empresas,
):
    """O alcance de alguém pode encolher com a escolha ainda de pé.

    É o que acontece quando se põe no organigrama quem administrava de fora:
    passa a pertencer a uma empresa, e a escolha que tinha feito sobre outra
    deixa de lhe dizer respeito. Confiar no que ficou guardado seria mostrar-lhe
    a Acme depois de ela deixar de estar ao alcance.
    """
    como("root")
    organizacao.escolher_empresa(duas_empresas["acme"].id)
    assert organizacao.empresa_escolhida() == duas_empresas["acme"].id

    # O root passa a pertencer à Rival. Quem o põe lá é a instalação: o
    # próprio root, com a vista estreitada à Acme, já não podia fazê-lo --
    # enquanto se está dentro de uma empresa, age-se **como** ela.
    rival_eng = organizacao.filhos(duas_empresas["rival"].id)[0]
    como_a_instalacao()
    utilizadores.definir_unidade("root", rival_eng.id)
    como("root")

    assert [u.id for u in organizacao.empresas_ao_alcance()] == [
        duas_empresas["rival"].id
    ]
    assert organizacao.empresa_escolhida() is None, "manteve uma escolha inválida"
    # E o que vê é a Rival, pela estrutura — não a Acme, pela escolha velha.
    assert organizacao.empresa_da_sessao() == duas_empresas["rival"].id
    assert "Tarefa da ana" not in descricoes()


# ================================================== o seletor na barra de topo


@pytest.fixture
def concha():
    """A concha real, numa janela descartável."""
    import tkinter as tk

    from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

    if not TKINTER_DISPONIVEL:
        pytest.skip("sem interface gráfica disponível")

    import aparencia
    from navegacao import Concha, registo

    registo.limpar()
    janela = criar_janela_com_retentativa(tk.Tk)
    janela.withdraw()
    aparencia.aplicar(janela, "claro")
    casca = Concha(janela)
    casca.pack(fill=tk.BOTH, expand=True)
    janela.update_idletasks()
    yield casca
    registo.limpar()
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


def test_com_uma_empresa_so_o_seletor_nao_aparece(concha):
    """Um controlo que promete uma escolha que não existe."""
    concha.definir_empresas([(1, "Acme")])
    assert concha._seletor_empresa.winfo_ismapped() == 0


def test_com_duas_o_seletor_aparece_e_oferece_todas(concha):
    concha.definir_empresas([(1, "Acme"), (2, "Rival")])
    concha.update_idletasks()

    valores = list(concha._seletor_empresa.cget("values"))
    assert valores[1:] == ["Acme", "Rival"]
    assert valores[0] == concha._rotulo_todas(), "faltou a opção de ver todas"
    assert concha.empresa_escolhida() is None, "começou estreitado sem ninguém pedir"


def test_o_seletor_mostra_a_que_esta_escolhida(concha):
    concha.definir_empresas([(1, "Acme"), (2, "Rival")], escolhida=2)
    assert concha.empresa_escolhida() == 2


def test_escolher_no_seletor_avisa_quem_o_ligou(concha):
    escolhas = []
    concha.ligar_empresas(escolhas.append)
    concha.definir_empresas([(1, "Acme"), (2, "Rival")])

    concha._empresa_var.set("Rival")
    concha._ao_mudar_empresa()
    assert escolhas == [2]

    concha._empresa_var.set(concha._rotulo_todas())
    concha._ao_mudar_empresa()
    assert escolhas == [2, None]


def test_mudar_de_idioma_nao_perde_a_empresa_escolhida(concha):
    """A barra é redesenhada ao traduzir; o contexto não se pode perder nisso."""
    concha.definir_empresas([(1, "Acme"), (2, "Rival")], escolhida=1)
    concha.atualizar_traducoes()
    assert concha.empresa_escolhida() == 1


def test_o_seletor_so_oferece_o_que_a_organizacao_alcanca(duas_empresas, concha):
    """A ponte entre as duas metades, e o sítio onde uma fuga entraria.

    A interface não decide o alcance — pergunta-o. Este teste liga as duas
    peças de propósito: um seletor que oferecesse a lista toda a quem pertence
    a uma empresa seria um buraco, mesmo com a organização a recusar depois.
    Oferecer para recusar a seguir é pior do que não oferecer.
    """
    como("ana")
    concha.definir_empresas(
        [(u.id, u.nome) for u in organizacao.empresas_ao_alcance()],
        organizacao.empresa_escolhida(),
    )
    assert concha._seletor_empresa.winfo_ismapped() == 0

    como("root")
    concha.definir_empresas(
        [(u.id, u.nome) for u in organizacao.empresas_ao_alcance()],
        organizacao.empresa_escolhida(),
    )
    concha.update_idletasks()
    assert list(concha._seletor_empresa.cget("values"))[1:] == ["Acme", "Rival"]
