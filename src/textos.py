"""Tradução de resultados da análise para frases apresentáveis.

Vive fora de :mod:`analitica` de propósito (ADR-0003): a análise devolve
chaves e números, e a apresentação decide como se lê. É partilhada pelo
dashboard e pelos relatórios, para a mesma conclusão não ser escrita de duas
maneiras diferentes.
"""

from __future__ import annotations

from analitica.insights import Insight
from language_manager import carregar_texto

_SEM_ACENTOS = str.maketrans("áéíóúâêôãõç", "aeiouaeoaoc")


def texto_do_insight(insight: Insight) -> str:
    """Frase traduzida de um insight, com os seus números.

    Alguns parâmetros são eles próprios traduzíveis — a direção de uma
    tendência, por exemplo — e são resolvidos aqui.
    """
    parametros = dict(insight.parametros)
    direcao = parametros.get("direcao")
    if direcao:
        chave = f"direcao_{str(direcao).translate(_SEM_ACENTOS)}"
        parametros["direcao"] = carregar_texto(chave)
    return carregar_texto(insight.chave, **parametros)
