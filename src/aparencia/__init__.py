"""A aparência da aplicação: tokens num sítio, aplicados uma vez.

Um módulo de interface — da aplicação ou de um plugin — pede o **papel** e
nunca o valor::

    from aparencia import ESPACO, aplicar, cores, fonte

    ttk.Label(pai, text="Total", style="Suave.TLabel")
    ttk.Label(pai, text="128", font=fonte("display", negrito=True))
    caixa.pack(padx=ESPACO["largo"])

É **Service**, não Core: o núcleo não importa interface nenhuma, e a
aplicação funciona sem isto — fica com o aspeto de origem do Tk, que era o
que tinha antes. Ver ADR-0008.
"""

from aparencia.paleta import ALTURA_LINHA, ESPACO, TAMANHO
from aparencia.tema import (
    aplicar,
    cabe_no_ecra,
    cores,
    em_pixeis,
    escala,
    familia,
    fonte,
    guardar_modo,
    modo,
    modo_guardado,
    series,
)

__all__ = [
    "ALTURA_LINHA",
    "ESPACO",
    "TAMANHO",
    "aplicar",
    "cabe_no_ecra",
    "cores",
    "em_pixeis",
    "escala",
    "familia",
    "fonte",
    "guardar_modo",
    "modo",
    "modo_guardado",
    "series",
]


class FornecedorDaAplicacao:
    """O que o contrato dos plugins recebe — ver ``core.plugin_api``.

    Uma classe fina de propósito: o que ela faz é dar ao Core acesso à paleta
    **sem** o Core saber que este módulo existe.
    """

    def cor(self, papel: str) -> str:
        return cores()[papel]

    def fonte(self, tamanho: str = "corpo", negrito: bool = False) -> tuple:
        return fonte(tamanho, negrito)

    def espaco(self, nome: str = "normal") -> int:
        return ESPACO[nome]


def instalar_no_contrato() -> None:
    """Liga a aparência ao contrato dos plugins.

    Chamada no arranque, pela interface. Enquanto não for chamada, um plugin
    que pergunte a cor recebe valores neutros em vez de um erro.
    """
    from core.plugin_api import instalar_aparencia

    instalar_aparencia(FornecedorDaAplicacao())
