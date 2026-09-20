"""Isolamento entre empresas: "ver todas" passa a querer dizer "as da minha".

Antes disto, quem tinha ``tarefas.ver_todas`` via **todas as tarefas da
instalação** — incluindo as de outra empresa. Numa instalação com uma empresa
só isso é a mesma coisa; com duas, é uma fuga de dados entre clientes.

Estes testes guardam as duas metades ao mesmo tempo, e a segunda é tão
importante como a primeira:

* que a fuga deixou de existir;
* que **nada muda** para quem tem uma empresa só, nenhuma estrutura, ou não
  está na estrutura. O isolamento começa a valer no dia em que a segunda
  empresa é criada, e não antes.
"""

import pytest

import banco_de_dados as db
import tarefas_servico as servico
from core import organizacao, permissoes, utilizadores
from core.organizacao import TipoUnidade


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

    # A estrutura monta-se **antes** de entrar em qualquer sessão de empresa.
    # Quem está dentro da Acme já não pode pôr ninguém na Rival, e é isso que
    # se quer: aqui é a instalação a ser configurada, e não a Ana a mexer no
    # organigrama do cliente do lado.
    lugares = (("ana", acme_eng.id), ("bruno", rival_eng.id))
    for nome, unidade in lugares:
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="administrador")
        utilizadores.definir_unidade(nome, unidade)

    tarefas = {}
    for nome, _ in lugares:
        como(nome)
        tarefas[nome] = servico.adicionar(f"Tarefa da {nome}", "2030-01-01")

    tarefas["antiga"] = db.adicionar_tarefa("Antiga, sem estrutura", "2030-01-02")
    return {"acme": acme, "rival": rival, "tarefas": tarefas}


# ============================================================ a fuga fechada


def test_quem_ve_tudo_ve_tudo_da_sua_empresa(duas_empresas):
    como("ana")
    vistas = descricoes()
    assert "Tarefa da ana" in vistas
    assert "Tarefa da bruno" not in vistas, "viu a tarefa da outra empresa"


def test_o_isolamento_vale_para_os_dois_lados(duas_empresas):
    como("bruno")
    vistas = descricoes()
    assert "Tarefa da bruno" in vistas
    assert "Tarefa da ana" not in vistas


def test_o_que_a_lista_esconde_tambem_nao_abre(duas_empresas):
    """`pode_ver` tem de concordar com `listar`.

    Se discordassem, havia tarefas que apareciam na lista e não abriam — ou,
    pior, que não apareciam e abriam na mesma por id.
    """
    como("ana")
    assert servico.pode_ver(duas_empresas["tarefas"]["ana"]) is True
    assert servico.pode_ver(duas_empresas["tarefas"]["bruno"]) is False
    assert servico.obter(duas_empresas["tarefas"]["bruno"]) is None


def test_a_contagem_por_pessoa_nao_soma_a_outra_empresa(duas_empresas):
    """Um número que não se explica a partir do ecrã é um número errado."""
    como("ana")
    contagem = dict(servico.contar_por_dono())
    assert "bruno" not in contagem


# ================================================= o que NÃO pode ter mudado


def test_as_tarefas_anteriores_a_estrutura_ficam_visiveis(duas_empresas):
    """Não pertencem a empresa nenhuma, e ninguém as pode perder de vista.

    Sem esta exceção, criar a segunda empresa fazia desaparecer o histórico
    inteiro do ecrã de toda a gente. O dado continuaria lá — e ninguém
    acreditaria nisso.
    """
    for pessoa in ("ana", "bruno"):
        como(pessoa)
        assert "Antiga, sem estrutura" in descricoes()


def test_com_uma_empresa_so_nada_muda():
    """O isolamento começa no dia em que a segunda empresa é criada."""
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    unidade = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, acme.id)
    utilizadores.criar("ana", "Uma-Senha-Longa-123", papel="administrador")
    utilizadores.definir_unidade("ana", unidade.id)
    como("ana")
    servico.adicionar("Minha", "2030-01-01")
    db.adicionar_tarefa("De outra pessoa", "2030-01-02", criada_por="zeca")

    assert servico.ambito().empresa == (), "não devia haver isolamento"
    assert descricoes() == {"Minha", "De outra pessoa"}


def test_sem_estrutura_nenhuma_nada_muda():
    """Uma instalação que nunca criou uma unidade continua exatamente igual."""
    utilizadores.criar("ana", "Uma-Senha-Longa-123", papel="administrador")
    como("ana")
    servico.adicionar("Minha", "2030-01-01")
    db.adicionar_tarefa("De outra pessoa", "2030-01-02", criada_por="zeca")

    assert servico.ambito().empresa == ()
    assert descricoes() == {"Minha", "De outra pessoa"}


def test_quem_administra_sem_estar_na_estrutura_continua_a_ver_tudo(duas_empresas):
    """Não pertence a empresa nenhuma; limitá-lo à "sua" deixava-o sem nada.

    É o caso de quem instala e administra sem se pôr no organigrama, e é
    exatamente quem precisa de ver tudo para resolver um problema.
    """
    utilizadores.criar("root", "Uma-Senha-Longa-123", papel="administrador")
    como("root")
    assert servico.ambito().empresa == ()
    vistas = descricoes()
    assert {"Tarefa da ana", "Tarefa da bruno"} <= vistas


def test_quem_ve_so_a_sua_unidade_nao_muda(duas_empresas):
    """O âmbito por unidade já era mais estreito do que a empresa."""
    como_a_instalacao()
    utilizadores.criar("chefe", "Uma-Senha-Longa-123", papel="gestor_de_unidade")
    unidade = organizacao.filhos(duas_empresas["acme"].id)[0]
    utilizadores.definir_unidade("chefe", unidade.id)
    como("chefe", "gestor_de_unidade")

    alcance = servico.ambito()
    assert alcance.empresa == (), "quem não vê tudo não precisa de isolamento"
    assert "Tarefa da bruno" not in descricoes()
