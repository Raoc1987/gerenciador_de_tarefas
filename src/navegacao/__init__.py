"""A concha de navegação: onde cada parte do produto vive, e como se chega lá.

É **Service (UI)**: a aplicação funciona sem isto — voltava às abas — e o
núcleo não lhe toca. Ver ADR-0009.
"""

from navegacao import comandos
from navegacao.comandos import PaletaDeComandos
from navegacao.concha import Concha
from navegacao.registo import GRUPOS, Destino, esquecer_por_dono, limpar, obter, por_grupo, registar

__all__ = [
    "Concha",
    "PaletaDeComandos",
    "comandos",
    "Destino",
    "GRUPOS",
    "esquecer_por_dono",
    "limpar",
    "obter",
    "por_grupo",
    "registar",
]
