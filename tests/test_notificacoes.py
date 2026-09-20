"""A caixa de entrada: o que foi anunciado, a quem, e o que já foi lido.

Os alertas já existiam e já eram publicados no barramento. O que faltava era
o sítio onde uma pessoa os lê — e a pergunta difícil não é guardar texto, é
**a quem pertence cada aviso**.

Estes testes guardam três coisas, por ordem de importância:

* que a caixa de uma pessoa não é a de outra — nem a leitura, nem a contagem,
  nem a escrita;
* que o que ainda não foi lido não desaparece por nenhuma via;
* que a caixa nunca faz falhar a operação que deu origem ao aviso.
"""


import pytest

import alertas
import notificacoes
import tarefas_servico as servico
from core import eventos, organizacao, permissoes, utilizadores
from core.organizacao import TipoUnidade


def como(utilizador: str, papel: str = "administrador") -> None:
    permissoes.definir_sessao(utilizador, papel, persistir=False)


@pytest.fixture(autouse=True)
def caixa_desligada():
    """O barramento é global: nenhum teste pode herdar a ligação do anterior."""
    notificacoes.desativar()
    yield
    notificacoes.desativar()


# =========================================================== de quem é o aviso


def test_a_caixa_de_uma_pessoa_nao_e_a_de_outra():
    como("ana")
    notificacoes.criar("insight_atrasadas", nivel="critico", quantidade=15)

    como("bruno")
    assert notificacoes.listar() == []
    assert notificacoes.por_ler() == 0

    como("ana")
    assert notificacoes.por_ler() == 1


def test_ninguem_marca_como_lido_o_aviso_de_outra_pessoa():
    """Se marcasse, dava para apagar o sino de alguém sem ele ver nada."""
    como("ana")
    ident = notificacoes.criar("insight_atrasadas")

    como("bruno")
    assert notificacoes.marcar_lida(ident) is False
    assert notificacoes.marcar_todas_lidas() == 0
    assert notificacoes.limpar_lidas() == 0

    como("ana")
    assert notificacoes.por_ler() == 1


def test_o_assunto_tambem_e_por_pessoa():
    """Senão o aviso de uma pessoa calava o de outra sobre o mesmo assunto."""
    como("ana")
    notificacoes.criar("insight_atrasadas", assunto="atrasadas")
    assert notificacoes.ja_anunciado("atrasadas") is True

    como("bruno")
    assert notificacoes.ja_anunciado("atrasadas") is False


def test_sem_assunto_nunca_agrupa_com_nada():
    como("ana")
    notificacoes.criar("qualquer")
    assert notificacoes.ja_anunciado("") is False


# ============================================= o que está por ler não se perde


def test_limpar_as_lidas_nao_toca_nas_que_estao_por_ler():
    """É a única coisa que esta caixa nunca pode fazer."""
    como("ana")
    lida = notificacoes.criar("ja_vista")
    notificacoes.marcar_lida(lida)
    notificacoes.criar("por_ver")

    assert notificacoes.limpar_lidas() == 1
    restantes = notificacoes.listar()
    assert [n.chave for n in restantes] == ["por_ver"]
    assert notificacoes.por_ler() == 1


def test_a_caixa_apara_as_lidas_e_nunca_as_outras():
    """O limite existe para a tabela não crescer sem fim.

    O que se descarta são as **lidas** mais antigas. Uma caixa que deitasse
    fora avisos por ler seria pior do que uma caixa cheia: a pessoa não ficava
    a saber, e não ficava a saber que não ficou a saber.
    """
    como("ana")
    limite = notificacoes.LIMITE_POR_PESSOA
    for i in range(limite + 5):
        ident = notificacoes.criar(f"lida_{i}")
        notificacoes.marcar_lida(ident)
    por_ler = notificacoes.criar("por_ler")

    guardadas = notificacoes.listar(limite=limite + 50)
    assert len(guardadas) <= limite + 1
    assert any(n.id == por_ler for n in guardadas), "descartou a que estava por ler"
    # As descartadas são as mais antigas, não as mais recentes.
    assert not any(n.chave == "lida_0" for n in guardadas)


def test_marcar_como_lida_e_idempotente():
    como("ana")
    ident = notificacoes.criar("uma")
    assert notificacoes.marcar_lida(ident) is True
    assert notificacoes.marcar_lida(ident) is False, "marcou duas vezes"


# ================================================================== conteúdo


def test_guarda_a_chave_e_os_parametros_e_nunca_a_frase():
    """O idioma muda em execução; uma frase gravada ficava congelada nele."""
    como("ana")
    notificacoes.criar("insight_atrasadas", quantidade=15, percentagem=40)

    guardada = notificacoes.listar()[0]
    assert guardada.chave == "insight_atrasadas"
    assert guardada.parametros == {"quantidade": 15, "percentagem": 40}


def test_um_nivel_desconhecido_nao_deita_fora_o_aviso():
    """Trocar um problema pequeno — etiqueta errada — por um grande."""
    como("ana")
    notificacoes.criar("uma", nivel="urgentissimo")
    assert notificacoes.listar()[0].nivel == notificacoes.NIVEL_PADRAO


def test_uma_notificacao_sem_texto_e_um_erro_de_quem_chama():
    como("ana")
    with pytest.raises(ValueError):
        notificacoes.criar("   ")


def test_parametros_que_nao_sao_json_nao_impedem_o_aviso():
    """Um módulo pode passar um objeto seu; o aviso vale mais que o parâmetro."""
    como("ana")

    class Coisa:
        def __str__(self):
            return "uma coisa"

    assert notificacoes.criar("uma", objeto=Coisa()) is not None
    assert notificacoes.listar()[0].parametros["objeto"] == "uma coisa"


def test_a_lista_vem_da_mais_recente_para_a_mais_antiga():
    como("ana")
    for chave in ("primeira", "segunda", "terceira"):
        notificacoes.criar(chave)
    assert [n.chave for n in notificacoes.listar()] == [
        "terceira", "segunda", "primeira"
    ]


# ============================================================ ligação ao alerta


def test_um_alerta_publicado_fica_na_caixa_de_quem_o_desencadeou():
    como("ana")
    notificacoes.ativar()
    eventos.publicar(
        eventos.ANALISE_ALERTA, origem="alertas",
        id="insight_atrasadas", nivel="critico", tipo="descritivo", quantidade=15,
    )

    guardada = notificacoes.listar()[0]
    assert guardada.chave == "insight_atrasadas"
    assert guardada.nivel == "critico"
    assert guardada.origem == "alertas"
    assert guardada.assunto == "insight_atrasadas"
    # `id`, `nivel` e `tipo` identificam o alerta; não são parâmetros do texto.
    assert guardada.parametros == {"quantidade": 15}


def test_um_alerta_resolvido_nao_apaga_nem_esconde_nada():
    """É uma caixa de correio, não um painel de estado.

    Uma notificação diz o que era verdade às 14:05, e isso continua a ter
    sido verdade às 14:05. Quem quer saber como as coisas estão agora tem o
    painel, que é o sítio para essa pergunta.
    """
    como("ana")
    notificacoes.ativar()
    eventos.publicar(eventos.ANALISE_ALERTA, origem="alertas",
                     id="insight_atrasadas", nivel="critico")
    eventos.publicar(eventos.ANALISE_RESOLVIDO, origem="alertas",
                     id="insight_atrasadas")

    assert notificacoes.por_ler() == 1


def test_ativar_duas_vezes_nao_guarda_o_aviso_duas_vezes():
    como("ana")
    notificacoes.ativar()
    notificacoes.ativar()
    eventos.publicar(eventos.ANALISE_ALERTA, origem="alertas", id="uma")
    assert len(notificacoes.listar()) == 1


def test_a_caixa_a_falhar_nao_leva_com_ela_quem_publicou(monkeypatch):
    """A vigilância corre a partir de eventos de tarefas.

    Se um aviso por guardar impedisse a tarefa de ser criada, a caixa passava
    a ser o componente mais perigoso da aplicação.
    """
    como("ana")
    notificacoes.ativar()

    def rebenta(*args, **kwargs):
        raise RuntimeError("banco em baixo")

    monkeypatch.setattr(notificacoes, "criar", rebenta)
    eventos.publicar(eventos.ANALISE_ALERTA, origem="alertas", id="uma")  # não levanta


def test_uma_falha_a_escrever_devolve_none_em_vez_de_levantar(monkeypatch):
    como("ana")

    def sem_banco():
        raise RuntimeError("banco em baixo")

    monkeypatch.setattr(notificacoes, "_conectar", sem_banco)
    assert notificacoes.criar("uma") is None


# ===================================== a caixa vista de ponta a ponta, a sério


def test_uma_tarefa_atrasada_acaba_por_aparecer_na_caixa():
    """O caminho todo: tarefa -> evento -> análise -> alerta -> caixa.

    Testar cada elo em separado deixa passar exatamente o defeito que este
    trabalho existe para resolver — a cadeia estar toda feita e não chegar a
    lado nenhum.
    """
    como("ana")
    alertas.ativar()
    notificacoes.ativar()

    for i in range(20):
        servico.adicionar(f"Atrasada {i}", "2020-01-01")

    chaves = {n.chave for n in notificacoes.listar()}
    assert "insight_atrasadas" in chaves
    assert notificacoes.por_ler() >= 1


def test_o_aviso_de_uma_empresa_nao_cai_na_caixa_da_outra():
    """A vigilância vê o âmbito de quem a desencadeia; a caixa segue-o."""
    acme = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    acme_eng = organizacao.criar("Eng", TipoUnidade.DEPARTAMENTO, acme.id)
    rival = organizacao.criar("Rival", TipoUnidade.EMPRESA)
    rival_eng = organizacao.criar("Eng", TipoUnidade.DEPARTAMENTO, rival.id)
    for nome, unidade in (("ana", acme_eng.id), ("bruno", rival_eng.id)):
        utilizadores.criar(nome, "Uma-Senha-Longa-123", papel="administrador")
        utilizadores.definir_unidade(nome, unidade)

    alertas.ativar()
    notificacoes.ativar()

    como("ana")
    for i in range(20):
        servico.adicionar(f"Atrasada {i}", "2020-01-01")
    assert notificacoes.por_ler() >= 1

    como("bruno")
    assert notificacoes.listar() == [], "recebeu o aviso da outra empresa"


# ================================================= a ação de automação


def test_uma_regra_pode_notificar():
    """A §41 dizia que as automações notificavam. Não havia forma de o fazer."""
    import automacoes
    from regras import acoes

    automacoes.registar_incluidas()
    como("ana")

    acoes.obter("notificar").funcao(
        {"descricao": "Comprar pão"},
        {"texto": "Tarefa nova: {descricao}", "nivel": "atencao"},
    )

    guardada = notificacoes.listar()[0]
    assert guardada.chave == "Tarefa nova: Comprar pão"
    assert guardada.nivel == "atencao"
    assert guardada.origem == "regras"


def test_uma_regra_sem_texto_e_recusada():
    import automacoes
    from regras import acoes

    automacoes.registar_incluidas()
    como("ana")
    with pytest.raises(ValueError):
        acoes.obter("notificar").funcao({}, {"texto": "  "})


# ============================================ o contrato: um módulo que avisa


def contexto_de(plugin_id: str, pasta):
    """Um contexto de plugin mínimo, como em ``test_plugin_dados.py``."""
    import logging

    from core.plugin_api import ContextoPlugin, ManifestoPlugin

    return ContextoPlugin(
        manifesto=ManifestoPlugin.de_dicionario(
            {
                "id": plugin_id,
                "name": plugin_id,
                "version": "1.0.0",
                "entry_point": "plugin.py",
                "min_app_version": "1.0.0",
            }
        ),
        app_version="1.0.0",
        diretorio_plugin=pasta,
        diretorio_dados=pasta,
        logger=logging.getLogger(f"teste.{plugin_id}"),
    )


def test_um_modulo_pode_avisar_quem_o_esta_a_usar(tmp_path):
    como("ana")
    contexto_de("estoque", tmp_path).notificar(
        "estoque_stock_baixo", nivel="atencao", assunto="stock_baixo", quantidade=3
    )

    guardada = notificacoes.listar()[0]
    assert guardada.chave == "estoque_stock_baixo"
    assert guardada.origem == "estoque"
    assert guardada.parametros == {"quantidade": 3}


def test_o_assunto_de_um_modulo_fica_no_espaco_de_nomes_dele(tmp_path):
    """Dois módulos com um "stock_baixo" deixavam de se poder distinguir."""
    estoque = contexto_de("estoque", tmp_path)
    compras = contexto_de("compras", tmp_path)

    como("ana")
    estoque.notificar("aviso", assunto="stock_baixo")

    assert estoque.ja_anunciado("stock_baixo") is True
    assert compras.ja_anunciado("stock_baixo") is False, "leu o assunto do outro"
    assert notificacoes.listar()[0].assunto == "estoque.stock_baixo"


def test_um_assunto_ja_prefixado_nao_e_prefixado_duas_vezes(tmp_path):
    estoque = contexto_de("estoque", tmp_path)
    como("ana")
    estoque.notificar("aviso", assunto="estoque.stock_baixo")
    assert notificacoes.listar()[0].assunto == "estoque.stock_baixo"


def test_um_modulo_nao_tem_forma_de_avisar_outra_pessoa(tmp_path):
    """Corre com o âmbito de quem o está a usar, e o aviso segue-o."""
    import inspect

    from core.plugin_api import ContextoPlugin

    assinatura = inspect.signature(ContextoPlugin.notificar)
    assert "destinatario" not in assinatura.parameters

    como("ana")
    contexto_de("estoque", tmp_path).notificar("aviso")
    como("bruno")
    assert notificacoes.listar() == []
