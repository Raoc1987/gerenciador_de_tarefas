"""Conversão de unidades.

Tudo passa por uma unidade de referência por família: converter A→B é A→base
e base→B. Uma tabela de pares seria N² entradas para manter em acordo umas
com as outras; assim é N, e acrescentar uma unidade é uma linha.

**Não há moedas aqui.** Converter euros em dólares exige taxas de hoje, e taxas
de hoje exigem rede, uma chave de API e um fornecedor — coisas que esta
aplicação não tem e que fariam sair da máquina o que alguém está a calcular.
Uma taxa desatualizada gravada no código seria pior: daria um número errado
com ar de certo. As unidades que estão aqui são todas definições exatas ou
constantes físicas, e não mudam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class ConversaoError(Exception):
    """Não é possível converter entre as unidades pedidas."""

    chave_mensagem = "calc_conversao_erro"


class UnidadeDesconhecidaError(ConversaoError):
    """A unidade não existe nessa família."""

    chave_mensagem = "calc_unidade_desconhecida"


@dataclass(frozen=True)
class Familia:
    """Um grupo de unidades comparáveis entre si.

    Attributes:
        base: a unidade de referência da família.
        fatores: quanto vale cada unidade **na base**.
    """

    chave: str
    base: str
    fatores: Dict[str, float]

    def unidades(self) -> List[str]:
        return sorted(self.fatores)


#: Comprimento, com a base em metros. A polegada é exatamente 0,0254 m desde
#: 1959, e daí saem o pé, a jarda e a milha — por isso não são aproximações.
COMPRIMENTO = Familia(
    "comprimento",
    "m",
    {
        "mm": 0.001,
        "cm": 0.01,
        "m": 1.0,
        "km": 1000.0,
        "pol": 0.0254,
        "pe": 0.3048,
        "jarda": 0.9144,
        "milha": 1609.344,
        "milha_nautica": 1852.0,
    },
)

MASSA = Familia(
    "massa",
    "kg",
    {
        "mg": 1e-6,
        "g": 0.001,
        "kg": 1.0,
        "tonelada": 1000.0,
        "onca": 0.028349523125,
        "libra": 0.45359237,
    },
)

AREA = Familia(
    "area",
    "m2",
    {
        "cm2": 0.0001,
        "m2": 1.0,
        "km2": 1e6,
        "hectare": 10000.0,
        "acre": 4046.8564224,
    },
)

VOLUME = Familia(
    "volume",
    "l",
    {
        "ml": 0.001,
        "l": 1.0,
        "m3": 1000.0,
        "galao_us": 3.785411784,
        "galao_uk": 4.54609,
    },
)

TEMPO = Familia(
    "tempo",
    "s",
    {
        "ms": 0.001,
        "s": 1.0,
        "min": 60.0,
        "h": 3600.0,
        "dia": 86400.0,
        "semana": 604800.0,
    },
)

#: Armazenamento em potências de 1024 (KiB, MiB…) e de 1000 (KB, MB…). As duas
#: existem e querem dizer coisas diferentes; misturá-las é a origem de metade
#: das discussões sobre o tamanho de um disco.
DADOS = Familia(
    "dados",
    "byte",
    {
        "bit": 0.125,
        "byte": 1.0,
        "kb": 1000.0,
        "mb": 1000.0**2,
        "gb": 1000.0**3,
        "tb": 1000.0**4,
        "kib": 1024.0,
        "mib": 1024.0**2,
        "gib": 1024.0**3,
        "tib": 1024.0**4,
    },
)

VELOCIDADE = Familia(
    "velocidade",
    "m/s",
    {
        "m/s": 1.0,
        "km/h": 1000.0 / 3600.0,
        "milha/h": 1609.344 / 3600.0,
        "no": 1852.0 / 3600.0,
    },
)

#: A temperatura não cabe numa tabela de fatores: as escalas têm origens
#: diferentes, por isso a conversão é afim (multiplicar **e** somar) e não
#: uma multiplicação. Tratá-la como as outras daria 0 °C = 0 °F.
TEMPERATURA = "temperatura"

FAMILIAS: Dict[str, Familia] = {
    familia.chave: familia
    for familia in (COMPRIMENTO, MASSA, AREA, VOLUME, TEMPO, DADOS, VELOCIDADE)
}

UNIDADES_TEMPERATURA = ("c", "f", "k")


def familias() -> List[str]:
    """Todas as famílias, incluindo a temperatura."""
    return sorted(list(FAMILIAS) + [TEMPERATURA])


def unidades_de(familia: str) -> List[str]:
    """As unidades de uma família.

    Raises:
        ConversaoError: se a família não existir.
    """
    if familia == TEMPERATURA:
        return list(UNIDADES_TEMPERATURA)
    if familia not in FAMILIAS:
        raise ConversaoError(f"Não conheço a família {familia!r}.")
    return FAMILIAS[familia].unidades()


def _para_celsius(valor: float, de: str) -> float:
    if de == "c":
        return valor
    if de == "f":
        return (valor - 32.0) * 5.0 / 9.0
    if de == "k":
        return valor - 273.15
    raise UnidadeDesconhecidaError(f"Não conheço a escala {de!r}.")


def _de_celsius(celsius: float, para: str) -> float:
    if para == "c":
        return celsius
    if para == "f":
        return celsius * 9.0 / 5.0 + 32.0
    if para == "k":
        return celsius + 273.15
    raise UnidadeDesconhecidaError(f"Não conheço a escala {para!r}.")


def converter_temperatura(valor: float, de: str, para: str) -> float:
    """Converte entre °C, °F e K.

    Raises:
        UnidadeDesconhecidaError: escala desconhecida.
        ConversaoError: abaixo do zero absoluto, que não existe.
    """
    celsius = _para_celsius(float(valor), (de or "").strip().lower())
    if celsius < -273.15 - 1e-9:
        raise ConversaoError("Não há temperaturas abaixo do zero absoluto.")
    return _de_celsius(celsius, (para or "").strip().lower())


def converter(valor: float, de: str, para: str, familia: Optional[str] = None) -> float:
    """Converte ``valor`` de uma unidade para outra.

    A família é deduzida das unidades quando não é indicada. Converter entre
    famílias diferentes — metros para quilos — é recusado, e não devolve um
    número só porque a multiplicação era possível.

    Raises:
        UnidadeDesconhecidaError: unidade que não existe.
        ConversaoError: unidades de famílias diferentes.
    """
    de = (de or "").strip().lower()
    para = (para or "").strip().lower()

    if familia == TEMPERATURA or (
        familia is None and de in UNIDADES_TEMPERATURA and para in UNIDADES_TEMPERATURA
    ):
        return converter_temperatura(valor, de, para)

    if familia is not None:
        if familia not in FAMILIAS:
            raise ConversaoError(f"Não conheço a família {familia!r}.")
        escolhida = FAMILIAS[familia]
        for unidade in (de, para):
            if unidade not in escolhida.fatores:
                raise UnidadeDesconhecidaError(
                    f"{unidade!r} não é uma unidade de {familia!r}."
                )
    else:
        escolhida = _familia_de(de, para)

    return float(valor) * escolhida.fatores[de] / escolhida.fatores[para]


def _familia_de(de: str, para: str) -> Familia:
    familias_de = [f for f in FAMILIAS.values() if de in f.fatores]
    familias_para = [f for f in FAMILIAS.values() if para in f.fatores]

    if not familias_de:
        raise UnidadeDesconhecidaError(f"Não conheço a unidade {de!r}.")
    if not familias_para:
        raise UnidadeDesconhecidaError(f"Não conheço a unidade {para!r}.")

    comuns = [f for f in familias_de if f in familias_para]
    if not comuns:
        raise ConversaoError(
            f"{de!r} e {para!r} medem coisas diferentes "
            f"({familias_de[0].chave} e {familias_para[0].chave})."
        )
    return comuns[0]


def tabela(valor: float, de: str, familia: Optional[str] = None) -> List[Tuple[str, float]]:
    """O mesmo valor em todas as unidades da família — é o que se quer ver."""
    de = (de or "").strip().lower()
    if familia == TEMPERATURA or (familia is None and de in UNIDADES_TEMPERATURA):
        return [(u, converter_temperatura(valor, de, u)) for u in UNIDADES_TEMPERATURA]

    escolhida = FAMILIAS[familia] if familia in FAMILIAS else _familia_de(de, de)
    return [(u, converter(valor, de, u, escolhida.chave)) for u in escolhida.unidades()]
