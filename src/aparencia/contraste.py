"""Contraste entre duas cores, pela fórmula da WCAG 2.1.

"Bonito" é discutível; legível não é. Esta é a parte da aparência que se
verifica com um número em vez de com uma opinião — e é por isso que existe
como código e não como nota num documento.

O rácio vai de 1 (invisível) a 21 (preto sobre branco). Os limiares da norma:

* **4.5** para texto normal;
* **3.0** para texto grande (a partir de ~18pt, ou 14pt a negrito) e para os
  contornos de controlos que a pessoa tem de conseguir distinguir.
"""

from __future__ import annotations

from typing import Tuple

#: Texto normal.
AA_TEXTO = 4.5

#: Texto grande e elementos de interface (contornos, ícones).
AA_GRANDE = 3.0


def _componentes(cor: str) -> Tuple[float, float, float]:
    """``"#rrggbb"`` para três valores de 0 a 1."""
    texto = cor.lstrip("#")
    if len(texto) != 6:
        raise ValueError(f"Cor em formato desconhecido: {cor!r}")
    return tuple(int(texto[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminancia(cor: str) -> float:
    """Luminância relativa, como a WCAG a define.

    Não é a média dos canais: o verde pesa muito mais do que o azul porque o
    olho é assim. Usar a média daria pares que a fórmula aprova e ninguém lê.
    """
    canais = []
    for valor in _componentes(cor):
        canais.append(valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4)
    vermelho, verde, azul = canais
    return 0.2126 * vermelho + 0.7152 * verde + 0.0722 * azul


def racio(frente: str, fundo: str) -> float:
    """Rácio de contraste entre duas cores, de 1 a 21."""
    a, b = luminancia(frente), luminancia(fundo)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def legivel(frente: str, fundo: str, minimo: float = AA_TEXTO) -> bool:
    """Se este par passa o limiar pedido."""
    return racio(frente, fundo) >= minimo


# --------------------------------------------------- distância entre cores
#
# O rácio de contraste responde a "vê-se isto por cima daquilo?" e é uma
# comparação de **luminância**. Não responde a "distinguem-se uma da outra":
# um azul e um verde igualmente luminosos dão rácio 1,16 e qualquer pessoa
# os separa a olho. Para séries de um gráfico, a pergunta é a segunda.
#
# A medida certa é a distância no espaço L*a*b*, que foi construído para que
# distâncias iguais correspondam a diferenças percebidas iguais — coisa que
# o RGB não faz.


def _para_xyz(cor: str):
    canais = []
    for valor in _componentes(cor):
        canais.append(valor / 12.92 if valor <= 0.04045 else ((valor + 0.055) / 1.055) ** 2.4)
    r, g, b = canais
    return (
        r * 0.4124 + g * 0.3576 + b * 0.1805,
        r * 0.2126 + g * 0.7152 + b * 0.0722,
        r * 0.0193 + g * 0.1192 + b * 0.9505,
    )


def _para_lab(cor: str):
    # Branco de referência D65, que é o do sRGB.
    x, y, z = _para_xyz(cor)
    x, y, z = x / 0.95047, y / 1.00000, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


#: Duas cores abaixo disto passam por variações da mesma.
#:
#: A norma diz que ~2.3 é o limiar em que uma pessoa nota que são diferentes.
#: Para séries de um gráfico, lado a lado e sem referência, é preciso muito
#: mais do que "notar": é preciso não ter de conferir na legenda.
DISTINTAS = 25.0


def distancia(a: str, b: str) -> float:
    """Diferença percebida entre duas cores (ΔE*ab, CIE76)."""
    la, aa, ba = _para_lab(a)
    lb, ab, bb = _para_lab(b)
    return ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5
