"""Cálculos financeiros, em ``Decimal``.

Dinheiro não se guarda em ``float``. ``0.1 + 0.2`` não dá ``0.3`` em binário, e
numa tabela de amortização a 360 meses esse erro acumula até as parcelas
deixarem de somar o empréstimo — alguém repara, e a partir daí não confia em
nenhum número do programa. Aqui os valores são :class:`~decimal.Decimal` e o
arredondamento é explícito: meio para cima, como se faz com dinheiro.

As taxas são por período, e o período é o mesmo das parcelas. Uma taxa anual
com parcelas mensais é o erro mais comum destes cálculos, por isso há uma
função que faz a conversão em condições — a equivalente composta, não a
divisão por doze, que dá sempre um valor a menos.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Union

Numero = Union[int, float, str, Decimal]

CENTIMOS = Decimal("0.01")


class FinanceiroError(Exception):
    """Os dados não permitem o cálculo pedido."""

    chave_mensagem = "calc_financeiro_erro"


def dinheiro(valor: Numero) -> Decimal:
    """Converte para ``Decimal`` arredondado ao cêntimo.

    Raises:
        FinanceiroError: se o valor não for um número.
    """
    try:
        return Decimal(str(valor)).quantize(CENTIMOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, ArithmeticError) as erro:
        raise FinanceiroError(f"Valor inválido: {valor!r}") from erro


def _taxa(valor: Numero) -> Decimal:
    """Uma taxa como fração: ``0.05`` é 5%. Não se arredonda ao cêntimo."""
    try:
        taxa = Decimal(str(valor))
    except (InvalidOperation, ValueError) as erro:
        raise FinanceiroError(f"Taxa inválida: {valor!r}") from erro
    if taxa <= -1:
        raise FinanceiroError("A taxa não pode ser -100% ou menos.")
    return taxa


def _periodos(valor: Numero) -> int:
    try:
        periodos = int(valor)
    except (TypeError, ValueError) as erro:
        raise FinanceiroError(f"Número de períodos inválido: {valor!r}") from erro
    if periodos <= 0:
        raise FinanceiroError("O número de períodos tem de ser maior do que zero.")
    return periodos


# ------------------------------------------------------------------- taxas


def taxa_equivalente(taxa: Numero, periodos_por_ano: int = 12) -> Decimal:
    """Converte uma taxa anual na taxa **equivalente** do período.

    Dividir 12% por 12 dá 1% ao mês, mas 1% ao mês composto dá 12,68% ao ano —
    não 12%. A equivalente é ``(1 + i)^(1/n) - 1``, e é a que mantém a promessa
    de quem anunciou a taxa anual.
    """
    anual = _taxa(taxa)
    n = _periodos(periodos_por_ano)
    return (Decimal(1) + anual) ** (Decimal(1) / Decimal(n)) - Decimal(1)


def taxa_nominal_para_periodo(taxa: Numero, periodos_por_ano: int = 12) -> Decimal:
    """A divisão simples, que é o que a maioria dos contratos usa.

    Existe aqui ao lado da equivalente **de propósito**: são números
    diferentes, e quem calcula deve escolher qual, em vez de descobrir mais
    tarde que o programa escolheu por si.
    """
    return _taxa(taxa) / Decimal(_periodos(periodos_por_ano))


# ---------------------------------------------------------- juros e capital


def juros_compostos(
    capital: Numero, taxa: Numero, periodos: Numero, deposito: Numero = 0
) -> Decimal:
    """Valor futuro de um capital, com depósitos iguais no fim de cada período."""
    presente = Decimal(str(capital))
    i = _taxa(taxa)
    n = _periodos(periodos)
    aporte = Decimal(str(deposito))

    fator = (Decimal(1) + i) ** n
    if i == 0:
        return dinheiro(presente + aporte * n)
    return dinheiro(presente * fator + aporte * (fator - Decimal(1)) / i)


def valor_presente(valor_futuro: Numero, taxa: Numero, periodos: Numero) -> Decimal:
    """Quanto vale hoje uma quantia que só existe no futuro."""
    i = _taxa(taxa)
    n = _periodos(periodos)
    return dinheiro(Decimal(str(valor_futuro)) / (Decimal(1) + i) ** n)


def prestacao(capital: Numero, taxa: Numero, periodos: Numero) -> Decimal:
    """A prestação constante que amortiza um empréstimo (sistema francês).

    Raises:
        FinanceiroError: capital não positivo.
    """
    montante = Decimal(str(capital))
    if montante <= 0:
        raise FinanceiroError("O capital emprestado tem de ser maior do que zero.")
    i = _taxa(taxa)
    n = _periodos(periodos)

    if i == 0:
        return dinheiro(montante / Decimal(n))
    fator = (Decimal(1) + i) ** n
    return dinheiro(montante * i * fator / (fator - Decimal(1)))


@dataclass(frozen=True)
class Parcela:
    """Uma linha da tabela de amortização."""

    numero: int
    prestacao: Decimal
    juros: Decimal
    amortizacao: Decimal
    saldo: Decimal


def amortizacao(capital: Numero, taxa: Numero, periodos: Numero) -> List[Parcela]:
    """A tabela completa, prestação a prestação.

    A última parcela absorve os cêntimos que o arredondamento deixou pelo
    caminho, para o saldo final ser **exatamente** zero. Sem isso, uma tabela
    a 360 meses acaba a dever três cêntimos a ninguém, e quem confere deixa de
    acreditar no resto.
    """
    montante = dinheiro(capital)
    i = _taxa(taxa)
    n = _periodos(periodos)
    valor = prestacao(montante, i, n)

    linhas: List[Parcela] = []
    saldo = montante
    for numero in range(1, n + 1):
        juros = dinheiro(saldo * i)
        if numero == n:
            abatimento = saldo
            paga = dinheiro(saldo + juros)
        else:
            abatimento = dinheiro(valor - juros)
            paga = valor
        saldo = dinheiro(saldo - abatimento)
        linhas.append(Parcela(numero, paga, juros, abatimento, saldo))
    return linhas


def total_pago(parcelas: List[Parcela]) -> Decimal:
    """Quanto sai do bolso ao todo — o número que interessa antes de assinar."""
    return dinheiro(sum((p.prestacao for p in parcelas), Decimal(0)))


def total_juros(parcelas: List[Parcela]) -> Decimal:
    """Quanto disso é juro."""
    return dinheiro(sum((p.juros for p in parcelas), Decimal(0)))


# ------------------------------------------------------------- percentagens


def acrescentar_percentagem(valor: Numero, percentagem: Numero) -> Decimal:
    """Ex.: acrescentar IVA a um preço sem imposto."""
    base = Decimal(str(valor))
    return dinheiro(base * (Decimal(1) + Decimal(str(percentagem)) / Decimal(100)))


def retirar_percentagem(valor: Numero, percentagem: Numero) -> Decimal:
    """Ex.: tirar o IVA de um preço que já o inclui.

    Não é o mesmo que subtrair a percentagem: 100 + 23% = 123, mas 123 − 23%
    dá 94,71. O que se quer é o valor que, com o imposto, dá este.
    """
    incluida = Decimal(str(percentagem))
    if incluida <= -100:
        raise FinanceiroError("Percentagem inválida.")
    return dinheiro(Decimal(str(valor)) / (Decimal(1) + incluida / Decimal(100)))


def variacao(inicial: Numero, final: Numero) -> Decimal:
    """De quanto variou, em percentagem.

    Raises:
        FinanceiroError: se o valor inicial for zero — a variação a partir de
            nada é infinita, e devolver um número seria inventá-lo.
    """
    base = Decimal(str(inicial))
    if base == 0:
        raise FinanceiroError("Não há variação percentual a partir de zero.")
    return ((Decimal(str(final)) - base) / abs(base) * Decimal(100)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
