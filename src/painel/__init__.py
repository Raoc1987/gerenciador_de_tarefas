"""O motor do painel: widgets declarados, uma grelha que se reparte, e os
filtros que os alimentam.

É **Service (UI)**: a aplicação funciona sem isto, e o núcleo não lhe toca.
Ver ADR-0010.
"""

from painel.contexto import Contexto
from painel.grelha import Grelha, colunas_para
from painel.rolo import Rolo
from painel.registo import COLUNAS, Widget, disponiveis, esquecer_por_dono, limpar, obter, registar

__all__ = [
    "COLUNAS",
    "Contexto",
    "Grelha",
    "Rolo",
    "Widget",
    "colunas_para",
    "disponiveis",
    "esquecer_por_dono",
    "limpar",
    "obter",
    "registar",
]


class FornecedorDaAplicacao:
    """O que o contrato dos plugins recebe — ver ``core.plugin_api``.

    Fina de propósito: dá ao Core acesso ao registo **sem** o Core saber que
    este módulo existe.
    """

    def registar_widget(self, **kwargs):
        return registar(**kwargs)


def instalar_no_contrato() -> None:
    """Liga o painel ao contrato dos plugins. Chamada no arranque."""
    from core.plugin_api import instalar_painel

    instalar_painel(FornecedorDaAplicacao())
