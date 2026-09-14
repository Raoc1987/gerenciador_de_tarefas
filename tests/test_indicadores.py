"""Indicadores declarados — e o que um número não pode revelar.

O painel mostrava tarefas porque foi escrito para tarefas. Agora cada módulo
declara o que sabe medir e o painel mostra sem saber o que é.

Um número parece inofensivo e não é: "há 3 itens abaixo do mínimo" diz que
existe um inventário e como está. Metade destes testes é sobre quem pode ver
o quê.
"""

import pytest

import database as db
import indicadores
import indicadores_incluidos
from core import permissoes
from indicadores import Valor


@pytest.fixture(autouse=True)
def registo_limpo():
    indicadores.limpar()
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    yield
    indicadores.limpar()


# ================================================================= VALOR


def test_sem_dados_nao_e_zero():
    """Mostrar zero quando não se sabe é mentir com um número."""
    vazio = Valor()
    assert not vazio.tem_dados
    assert vazio.formatado() == "—"


def test_zero_e_um_numero_a_serio():
    assert Valor(0).tem_dados
    assert Valor(0).formatado() == "0"


@pytest.mark.parametrize(
    "valor,esperado",
    [(Valor(12), "12"), (Valor(12.0), "12"), (Valor(12.34), "12.3"), (Valor(45, "%"), "45%")],
)
def test_como_se_le_num_cartao(valor, esperado):
    assert valor.formatado() == esperado


# =============================================================== REGISTO


def test_um_indicador_registado_e_lido():
    indicadores.registar("x", lambda: Valor(7))
    leituras = indicadores.ler()

    assert len(leituras) == 1
    assert leituras[0].valor.numero == 7


def test_registar_a_mesma_chave_substitui():
    indicadores.registar("x", lambda: Valor(1))
    indicadores.registar("x", lambda: Valor(2))
    assert indicadores.ler()[0].valor.numero == 2


@pytest.mark.parametrize("mau", ["", "   "])
def test_um_indicador_precisa_de_chave(mau):
    with pytest.raises(ValueError):
        indicadores.registar(mau, lambda: Valor(1))


def test_um_indicador_tem_de_ser_uma_funcao():
    with pytest.raises(ValueError):
        indicadores.registar("x", "isto não é uma função")


def test_um_modulo_tem_de_prefixar_os_seus():
    """Dois módulos com "total" deixavam de se poder distinguir."""
    with pytest.raises(ValueError, match="prefixar"):
        indicadores.registar("total", lambda: Valor(1), dono="estoque")

    indicadores.registar("estoque.total", lambda: Valor(1), dono="estoque")
    assert indicadores.ler()[0].chave == "estoque.total"


def test_os_indicadores_de_um_plugin_saem_com_ele():
    indicadores.registar("estoque.total", lambda: Valor(1), dono="estoque")
    assert indicadores.esquecer_por_dono("estoque") == 1
    assert indicadores.ler() == []


def test_ler_de_um_dono_so_traz_os_dele():
    indicadores.registar("a", lambda: Valor(1))
    indicadores.registar("estoque.total", lambda: Valor(2), dono="estoque")

    assert [l.chave for l in indicadores.ler_de("estoque")] == ["estoque.total"]


# ============================================================= ISOLAMENTO


def test_um_indicador_que_rebenta_nao_tapa_os_outros():
    """Uma divisão por zero num módulo não pode apagar o painel todo."""
    def explode():
        raise ZeroDivisionError("rebentei")

    indicadores.registar("partido", explode)
    indicadores.registar("bom", lambda: Valor(5))

    leituras = indicadores.ler()
    assert [l.chave for l in leituras] == ["bom"]


def test_um_indicador_que_devolve_lixo_e_ignorado():
    indicadores.registar("mau", lambda: "isto não é um Valor")
    indicadores.registar("bom", lambda: Valor(5))

    assert [l.chave for l in indicadores.ler()] == ["bom"]


# ============================================================= PERMISSÕES


def test_sem_permissao_o_cartao_nem_aparece():
    """Um "—" já diria que o número existe; quem não pode ver não vê nada."""
    indicadores.registar("secreto", lambda: Valor(42), permissao="estoque.ler")
    permissoes.definir_sessao("olga", "colaborador", persistir=False)

    assert indicadores.ler() == []


def test_com_permissao_aparece():
    from core.permissoes import Permissao

    indicadores.registar("visivel", lambda: Valor(42), permissao=Permissao.TAREFAS_LER)
    permissoes.definir_sessao("olga", "colaborador", persistir=False)

    assert [l.chave for l in indicadores.ler()] == ["visivel"]


def test_sem_permissao_declarada_toda_a_gente_ve():
    indicadores.registar("publico", lambda: Valor(1))
    permissoes.definir_sessao("olga", "visualizador", persistir=False)

    assert len(indicadores.ler()) == 1


# ================================================= OS DA APLICAÇÃO


def test_os_incluidos_medem_as_tarefas_da_sessao():
    """Um número sobre tudo o que existe diria a um colaborador quantas
    tarefas a empresa tem, o que a lista dele não diz."""
    indicadores_incluidos.registar_incluidos()
    db.adicionar_tarefa("Da Ana", "2030-01-01", criada_por="ana")
    db.adicionar_tarefa("Do Bruno", "2030-01-02", criada_por="bruno")

    permissoes.definir_sessao("chefe", "gestor", persistir=False)
    por_chave = {l.chave: l.valor.numero for l in indicadores.ler()}
    assert por_chave["tarefas.total"] == 2

    permissoes.definir_sessao("ana", "colaborador", persistir=False)
    por_chave = {l.chave: l.valor.numero for l in indicadores.ler()}
    assert por_chave["tarefas.total"] == 1, "só vê a sua"


def test_sem_tarefas_o_indicador_diz_sem_dados():
    indicadores_incluidos.registar_incluidos()
    assert all(not l.valor.tem_dados for l in indicadores.ler())


def test_a_taxa_de_conclusao_vem_em_percentagem():
    indicadores_incluidos.registar_incluidos()
    primeira = db.adicionar_tarefa("Uma", "2030-01-01", criada_por="ana")
    db.adicionar_tarefa("Outra", "2030-01-02", criada_por="ana")
    db.concluir_tarefa(primeira)

    taxa = next(l for l in indicadores.ler() if l.chave == "tarefas.taxa_conclusao")
    assert taxa.valor.formatado() == "50%"


def test_atrasadas_sabe_que_subir_e_mau():
    """A seta do cartão depende disto: mais atrasadas não é uma boa notícia."""
    indicadores_incluidos.registar_incluidos()
    atrasadas = next(
        i for i in indicadores.registados() if i.chave == "tarefas.atrasadas"
    )
    assert atrasadas.subir_e_bom is False


# ============================================ UM MÓDULO NO PAINEL


@pytest.fixture
def estoque(gerenciador, pasta_plugins):
    """O módulo real instalado e carregado."""
    import shutil
    from pathlib import Path

    origem = Path(__file__).resolve().parent.parent / "plugins" / "available" / "estoque"
    shutil.copytree(origem, pasta_plugins / "estoque")
    gerenciador.descobrir()
    assert gerenciador.carregar("estoque").sucesso
    return gerenciador


def test_um_modulo_aparece_no_painel_sem_o_painel_o_conhecer(estoque):
    """A promessa que isto existe para cumprir."""
    chaves = [i.chave for i in indicadores.registados()]
    assert "estoque.itens" in chaves
    assert "estoque.em_falta" in chaves


def test_os_numeros_do_modulo_sao_os_seus(estoque):
    instancia = estoque.obter("estoque").instancia
    item = instancia.servico.criar_item("PAR-01", "Parafuso", minimo=10)
    instancia.servico.entrada(item.id, 3)

    por_chave = {l.chave: l.valor.numero for l in indicadores.ler()}
    assert por_chave["estoque.itens"] == 1
    assert por_chave["estoque.em_falta"] == 1, "3 é menos que o mínimo de 10"


def test_desinstalar_o_modulo_tira_os_cartoes(estoque):
    assert any(i.dono == "estoque" for i in indicadores.registados())

    estoque.remover("estoque", remover_dados=True)
    assert not any(i.dono == "estoque" for i in indicadores.registados())


def test_quem_nao_ve_o_estoque_nao_ve_os_numeros_dele(estoque):
    """O módulo declarou que estes números exigem estoque.ler."""
    instancia = estoque.obter("estoque").instancia
    instancia.servico.criar_item("PAR-01", "Parafuso")

    estoque.descarregar("estoque")  # as permissões do módulo saem com ele
    assert [l for l in indicadores.ler() if l.chave.startswith("estoque.")] == []
