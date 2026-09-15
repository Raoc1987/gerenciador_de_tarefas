"""O que um plugin declara é o limite do que consegue fazer.

Um plugin instalado é código de outra pessoa a correr na máquina de quem nos
confia os dados. O manifesto passa a dizer de que acesso precisa, o utilizador
vê isso antes de o ativar, e o contrato recusa o resto — mesmo que a sessão
tivesse o direito.
"""

import json

import pytest

from core.permissoes import Permissao, definir_sessao
from core.plugin_api import (
    PERMISSOES_CONCEDIVEIS,
    PERMISSOES_NEGADAS_A_PLUGINS,
    ContextoPlugin,
    ManifestoInvalidoError,
    ManifestoPlugin,
    PermissaoNaoDeclaradaError,
    TarefasComPermissoes,
)

BASE = {
    "id": "exemplo",
    "name": "Exemplo",
    "version": "1.0.0",
    "entry_point": "plugin.py",
    "min_app_version": "1.0.0",
}


def manifesto(**extra) -> ManifestoPlugin:
    return ManifestoPlugin.de_dicionario({**BASE, **extra})


class TarefasFalsas:
    """Um serviço que aceita tudo, para isolar o que o guardião recusa."""

    def __init__(self):
        self.chamadas = []

    def listar(self, incluir_concluidas=True):
        self.chamadas.append("listar")
        return []

    def listar_por_data(self, data_iso):
        self.chamadas.append("listar_por_data")
        return []

    def adicionar(self, descricao, data_vencimento=None):
        self.chamadas.append("adicionar")
        return 1


# ============================================================== MANIFESTO


def test_sem_campo_nao_pede_nada():
    """Omitir o campo não é o mesmo que pedir tudo."""
    assert manifesto().permissoes == frozenset()


def test_declara_o_que_pede():
    m = manifesto(permissions=["tarefas.ler", "tarefas.escrever"])
    assert m.permissoes == {Permissao.TAREFAS_LER, Permissao.TAREFAS_ESCREVER}


@pytest.mark.parametrize("negada", sorted(p.value for p in PERMISSOES_NEGADAS_A_PLUGINS))
def test_nenhum_plugin_pode_pedir_as_chaves_da_casa(negada):
    """Gerir plugins, contas ou o sistema não são capacidades de negócio."""
    with pytest.raises(ManifestoInvalidoError, match="Nenhum plugin pode pedir"):
        manifesto(permissions=[negada])


def test_permissao_inventada_e_recusada():
    with pytest.raises(ManifestoInvalidoError, match="desconhecida"):
        manifesto(permissions=["estoque.roubar"])


@pytest.mark.parametrize("mau", ["tarefas.ler", {"a": 1}, [1, 2], [None]])
def test_campo_malformado_e_recusado(mau):
    with pytest.raises(ManifestoInvalidoError):
        manifesto(permissions=mau)


def test_sobrevive_a_ida_e_volta_ao_json():
    """O manifesto reescrito no disco tem de voltar a ser o mesmo."""
    original = manifesto(permissions=["relatorios.exportar", "tarefas.ler"])
    copia = ManifestoPlugin.de_dicionario(
        json.loads(json.dumps(original.para_dicionario()))
    )
    assert copia.permissoes == original.permissoes


def test_a_lista_do_que_e_concedivel_esta_fixada():
    """Uma permissão nova obriga a decidir se um plugin pode pedi-la.

    Se este teste falhar porque acrescentou uma Permissao, a pergunta é: um
    plugin de terceiros devia poder pedir isto? Se sim, junte-a aqui. Se não,
    junte-a a PERMISSOES_NEGADAS_A_PLUGINS.
    """
    assert {p.value for p in PERMISSOES_CONCEDIVEIS} == {
        "tarefas.ler",
        "tarefas.escrever",
        "tarefas.ver_todas",
        "tarefas.ver_unidade",
        "analytics.ler",
        "relatorios.ler",
        "relatorios.exportar",
    }


# ============================================================== APLICAÇÃO


def test_o_que_nao_foi_declarado_e_recusado():
    servico = TarefasFalsas()
    tarefas = TarefasComPermissoes(servico, [Permissao.TAREFAS_LER])

    tarefas.listar()
    tarefas.listar_por_data("2026-01-01")
    assert servico.chamadas == ["listar", "listar_por_data"]

    with pytest.raises(PermissaoNaoDeclaradaError) as erro:
        tarefas.adicionar("não devia passar")
    assert erro.value.permissao == Permissao.TAREFAS_ESCREVER
    assert "adicionar" not in servico.chamadas


def test_declarar_nao_concede():
    """Declarar tarefas.escrever não dá o direito de escrever.

    A sessão é um visualizador: lê tudo, não escreve nada. O plugin declara
    ambas. O guardião do plugin deixa passar as duas; o serviço por baixo —
    que é quem conhece a sessão — recusa a escrita.
    """
    import banco_de_dados
    from core.permissoes import PermissaoNegadaError
    from plugin_ui import ServicoTarefasApp

    banco_de_dados.criar_tabela()
    definir_sessao("ana", "visualizador", persistir=False)
    tarefas = TarefasComPermissoes(
        ServicoTarefasApp(), [Permissao.TAREFAS_LER, Permissao.TAREFAS_ESCREVER]
    )

    tarefas.listar()  # leitura passa nas duas camadas

    with pytest.raises(PermissaoNegadaError):
        tarefas.adicionar("a sessão não pode escrever")


def test_contexto_diz_o_que_o_plugin_pode(monkeypatch):
    from core import permissoes as mod_permissoes

    contexto = ContextoPlugin(
        manifesto=manifesto(permissions=["tarefas.ler"]),
        app_version="1.0.0",
        diretorio_plugin=".",
        diretorio_dados=".",
        logger=__import__("logging").getLogger("teste"),
    )
    monkeypatch.setattr(mod_permissoes, "pode", lambda p: True)

    assert contexto.pode(Permissao.TAREFAS_LER)
    assert not contexto.pode(Permissao.TAREFAS_ESCREVER), "não foi declarada"

    monkeypatch.setattr(mod_permissoes, "pode", lambda p: False)
    assert not contexto.pode(Permissao.TAREFAS_LER), "a sessão também conta"


# =============================================== PLUGINS QUE ACOMPANHAM A APP


def test_os_plugins_incluidos_declaram_o_que_usam():
    """Se um plugin nosso usa tarefas sem declarar, falha aqui e não no cliente."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "plugins" / "available"
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        m = ManifestoPlugin.ler_de_pasta(pasta)
        codigo = "\n".join(
            arquivo.read_text(encoding="utf-8") for arquivo in pasta.rglob("*.py")
        )
        usa_leitura = "tarefas.listar" in codigo
        usa_escrita = "tarefas.adicionar" in codigo
        assert usa_leitura <= (Permissao.TAREFAS_LER in m.permissoes), (
            f"{pasta.name} lê tarefas sem declarar tarefas.ler"
        )
        assert usa_escrita <= (Permissao.TAREFAS_ESCREVER in m.permissoes), (
            f"{pasta.name} cria tarefas sem declarar tarefas.escrever"
        )
