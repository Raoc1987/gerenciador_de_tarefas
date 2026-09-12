"""Avaliação de expressões — escrita à mão, de propósito.

A forma rápida de fazer uma calculadora em Python é ``eval()``. Não se faz
aqui. ``eval`` executa **código**, não aritmética: numa aplicação que guarda
tarefas, contas e inventário de uma empresa, uma caixa de texto ligada ao
``eval`` é um buraco por onde entra tudo — basta alguém colar uma linha que
parece uma conta.

Por isso há aqui um analisador a sério: transforma o texto em símbolos,
percorre-os com precedência e associatividade, e só conhece números,
operadores e uma lista fechada de funções. O que não estiver nessa lista não
existe, e dizer "função desconhecida" é a resposta certa.

Nada aqui sabe o que é uma janela.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional


class ErroDeCalculo(Exception):
    """A expressão não pode ser calculada."""

    chave_mensagem = "calc_erro"


class ExpressaoInvalidaError(ErroDeCalculo):
    """O texto não é uma expressão bem formada."""

    chave_mensagem = "calc_expressao_invalida"


class NomeDesconhecidoError(ErroDeCalculo):
    """Usou-se uma função ou constante que não existe."""

    chave_mensagem = "calc_nome_desconhecido"


class DominioError(ErroDeCalculo):
    """A operação não está definida para esses valores.

    Divisão por zero, raiz de negativo, logaritmo de zero — casos em que não
    há resultado, e inventar um seria pior do que recusar.
    """

    chave_mensagem = "calc_dominio"


class Angulo(str, Enum):
    """Como interpretar os ângulos das funções trigonométricas."""

    GRAUS = "graus"
    RADIANOS = "radianos"


# ------------------------------------------------------------------ símbolos


class Tipo(str, Enum):
    NUMERO = "numero"
    NOME = "nome"
    OPERADOR = "operador"
    ABRE = "abre"
    FECHA = "fecha"
    VIRGULA = "virgula"


@dataclass(frozen=True)
class Simbolo:
    tipo: Tipo
    texto: str
    posicao: int


#: Operadores binários: precedência e se associam à direita.
OPERADORES = {
    "+": (1, False),
    "-": (1, False),
    "*": (2, False),
    "/": (2, False),
    "%": (2, False),
    "//": (2, False),
    "^": (4, True),
}

#: Estes caracteres são aceites como sinónimos, porque é o que as pessoas
#: escrevem quando copiam de uma folha de cálculo ou de um documento.
SINONIMOS = {"×": "*", "÷": "/", "−": "-", ",": ".", "**": "^"}


def dividir_em_simbolos(texto: str) -> List[Simbolo]:
    """Parte a expressão nos seus símbolos.

    Raises:
        ExpressaoInvalidaError: se aparecer um caractere que não pertence a
            uma expressão aritmética.
    """
    simbolos: List[Simbolo] = []
    indice = 0
    texto = (texto or "").replace("×", "*").replace("÷", "/").replace("−", "-")

    while indice < len(texto):
        caractere = texto[indice]

        if caractere.isspace():
            indice += 1
            continue

        if caractere.isdigit() or caractere == ".":
            inicio = indice
            visto_ponto = False
            while indice < len(texto) and (texto[indice].isdigit() or texto[indice] == "."):
                if texto[indice] == ".":
                    if visto_ponto:
                        raise ExpressaoInvalidaError(
                            f"Número com dois pontos decimais na posição {inicio + 1}."
                        )
                    visto_ponto = True
                indice += 1
            simbolos.append(Simbolo(Tipo.NUMERO, texto[inicio:indice], inicio))
            continue

        if caractere.isalpha() or caractere == "_":
            inicio = indice
            while indice < len(texto) and (texto[indice].isalnum() or texto[indice] == "_"):
                indice += 1
            simbolos.append(Simbolo(Tipo.NOME, texto[inicio:indice].lower(), inicio))
            continue

        if texto.startswith("**", indice):
            simbolos.append(Simbolo(Tipo.OPERADOR, "^", indice))
            indice += 2
            continue
        if texto.startswith("//", indice):
            simbolos.append(Simbolo(Tipo.OPERADOR, "//", indice))
            indice += 2
            continue

        if caractere in OPERADORES:
            simbolos.append(Simbolo(Tipo.OPERADOR, caractere, indice))
            indice += 1
            continue
        if caractere in "([{":
            simbolos.append(Simbolo(Tipo.ABRE, "(", indice))
            indice += 1
            continue
        if caractere in ")]}":
            simbolos.append(Simbolo(Tipo.FECHA, ")", indice))
            indice += 1
            continue
        if caractere in ",;":
            simbolos.append(Simbolo(Tipo.VIRGULA, ",", indice))
            indice += 1
            continue

        raise ExpressaoInvalidaError(
            f"Caractere inesperado {caractere!r} na posição {indice + 1}."
        )

    return simbolos


# ------------------------------------------------------------------ funções


def _fatorial(valor: float) -> float:
    if valor < 0 or valor != int(valor):
        raise DominioError("O fatorial só existe para inteiros não negativos.")
    if valor > 170:
        raise DominioError("O fatorial desse número é grande demais.")
    return float(math.factorial(int(valor)))


def _raiz(valor: float) -> float:
    if valor < 0:
        raise DominioError("A raiz quadrada de um número negativo não é real.")
    return math.sqrt(valor)


def _log(valor: float, base: Optional[float] = None) -> float:
    if valor <= 0:
        raise DominioError("O logaritmo só está definido para números positivos.")
    if base is None:
        return math.log10(valor)
    if base <= 0 or base == 1:
        raise DominioError("A base do logaritmo tem de ser positiva e diferente de 1.")
    return math.log(valor, base)


def _ln(valor: float) -> float:
    if valor <= 0:
        raise DominioError("O logaritmo só está definido para números positivos.")
    return math.log(valor)


def _asin(valor: float) -> float:
    if not -1 <= valor <= 1:
        raise DominioError("O arco-seno só está definido entre -1 e 1.")
    return math.asin(valor)


def _acos(valor: float) -> float:
    if not -1 <= valor <= 1:
        raise DominioError("O arco-cosseno só está definido entre -1 e 1.")
    return math.acos(valor)


#: Funções de um argumento que não dependem da unidade de ângulo.
FUNCOES: Dict[str, Callable] = {
    "abs": abs,
    "raiz": _raiz,
    "sqrt": _raiz,
    "exp": math.exp,
    "ln": _ln,
    "log": _log,
    "log2": math.log2,
    "fact": _fatorial,
    "fatorial": _fatorial,
    "floor": lambda v: float(math.floor(v)),
    "ceil": lambda v: float(math.ceil(v)),
    "round": lambda v, casas=0: round(v, int(casas)),
    "sinal": lambda v: float((v > 0) - (v < 0)),
    "max": max,
    "min": min,
}

#: Trigonométricas: recebem ou devolvem ângulos, e por isso dependem do modo.
TRIGONOMETRICAS = {"sin", "cos", "tan", "sen"}
TRIGONOMETRICAS_INVERSAS = {"asin", "acos", "atan", "asen"}

CONSTANTES = {"pi": math.pi, "e": math.e, "tau": math.tau}


def nomes_conhecidos() -> List[str]:
    """Tudo o que se pode escrever numa expressão, para a ajuda e os testes."""
    return sorted(
        set(FUNCOES) | TRIGONOMETRICAS | TRIGONOMETRICAS_INVERSAS | set(CONSTANTES)
    )


# --------------------------------------------------------------- analisador


class Calculadora:
    """Avalia expressões aritméticas, sem executar código.

    Example:
        >>> Calculadora().avaliar("2 + 3 * 4")
        14.0
        >>> Calculadora().avaliar("sin(90)")   # em graus, por omissão
        1.0
    """

    def __init__(self, angulo: Angulo = Angulo.GRAUS) -> None:
        self.angulo = Angulo(angulo)

    # ------------------------------------------------------------- público

    def avaliar(self, expressao: str) -> float:
        """Calcula o valor de uma expressão.

        Raises:
            ExpressaoInvalidaError: texto malformado.
            NomeDesconhecidoError: função ou constante que não existe.
            DominioError: operação sem resultado definido.
        """
        self._simbolos = dividir_em_simbolos(expressao)
        if not self._simbolos:
            raise ExpressaoInvalidaError("Não há nada para calcular.")
        self._posicao = 0

        valor = self._expressao()
        if self._posicao < len(self._simbolos):
            sobra = self._simbolos[self._posicao]
            raise ExpressaoInvalidaError(
                f"Sobra {sobra.texto!r} na posição {sobra.posicao + 1}."
            )
        return self._finito(valor)

    # -------------------------------------------------------------- apoio

    @staticmethod
    def _finito(valor: float) -> float:
        """Recusa infinitos e NaN em vez de os devolver como se fossem números."""
        if isinstance(valor, complex):  # pragma: no cover - defensivo
            raise DominioError("O resultado não é um número real.")
        valor = float(valor)
        if math.isnan(valor):
            raise DominioError("O resultado não é um número.")
        if math.isinf(valor):
            raise DominioError("O resultado é grande demais.")
        return valor

    def _atual(self) -> Optional[Simbolo]:
        if self._posicao < len(self._simbolos):
            return self._simbolos[self._posicao]
        return None

    def _consumir(self) -> Simbolo:
        simbolo = self._atual()
        if simbolo is None:
            raise ExpressaoInvalidaError("A expressão termina a meio.")
        self._posicao += 1
        return simbolo

    # ------------------------------------------------------------ gramática

    def _expressao(self, precedencia_minima: int = 1) -> float:
        """Precedência por subida: o laço trata os operadores binários."""
        esquerda = self._unario()

        while True:
            simbolo = self._atual()
            if simbolo is None or simbolo.tipo != Tipo.OPERADOR:
                break
            precedencia, direita_associativo = OPERADORES[simbolo.texto]
            if precedencia < precedencia_minima:
                break

            self._consumir()
            seguinte = precedencia if direita_associativo else precedencia + 1
            direita = self._expressao(seguinte)
            esquerda = self._aplicar(simbolo.texto, esquerda, direita)

        return esquerda

    def _unario(self) -> float:
        simbolo = self._atual()
        if simbolo is not None and simbolo.tipo == Tipo.OPERADOR and simbolo.texto in "+-":
            self._consumir()
            # Precedência 3: acima de * e /, abaixo de ^ — é o que faz
            # -2^2 valer -4, como em qualquer calculadora científica.
            valor = self._expressao(3)
            return -valor if simbolo.texto == "-" else valor
        return self._posfixo()

    def _posfixo(self) -> float:
        valor = self._primario()
        while True:
            simbolo = self._atual()
            if simbolo is not None and simbolo.tipo == Tipo.NOME and simbolo.texto == "":
                break  # pragma: no cover - defensivo
            break
        return valor

    def _primario(self) -> float:
        simbolo = self._consumir()

        if simbolo.tipo == Tipo.NUMERO:
            try:
                return float(simbolo.texto)
            except ValueError as erro:  # pragma: no cover - o divisor já validou
                raise ExpressaoInvalidaError(f"Número inválido: {simbolo.texto!r}") from erro

        if simbolo.tipo == Tipo.ABRE:
            valor = self._expressao()
            fecho = self._atual()
            if fecho is None or fecho.tipo != Tipo.FECHA:
                raise ExpressaoInvalidaError("Falta fechar um parêntese.")
            self._consumir()
            return valor

        if simbolo.tipo == Tipo.NOME:
            return self._nome(simbolo)

        raise ExpressaoInvalidaError(
            f"Não esperava {simbolo.texto!r} na posição {simbolo.posicao + 1}."
        )

    def _nome(self, simbolo: Simbolo) -> float:
        nome = simbolo.texto
        seguinte = self._atual()

        # Sem parêntese a seguir, só pode ser uma constante.
        if seguinte is None or seguinte.tipo != Tipo.ABRE:
            if nome in CONSTANTES:
                return CONSTANTES[nome]
            raise NomeDesconhecidoError(f"Não conheço {nome!r}.")

        self._consumir()  # o "("
        argumentos: List[float] = []
        if self._atual() is not None and self._atual().tipo != Tipo.FECHA:
            argumentos.append(self._expressao())
            while self._atual() is not None and self._atual().tipo == Tipo.VIRGULA:
                self._consumir()
                argumentos.append(self._expressao())

        fecho = self._atual()
        if fecho is None or fecho.tipo != Tipo.FECHA:
            raise ExpressaoInvalidaError(f"Falta fechar o parêntese de {nome!r}.")
        self._consumir()

        return self._chamar(nome, argumentos)

    def _chamar(self, nome: str, argumentos: List[float]) -> float:
        if nome in TRIGONOMETRICAS:
            valor = self._exigir_um(nome, argumentos)
            if self.angulo == Angulo.GRAUS:
                valor = math.radians(valor)
            funcao = {"sin": math.sin, "sen": math.sin, "cos": math.cos, "tan": math.tan}[nome]
            resultado = funcao(valor)
            # tan(90°) é infinito; arredondar o seno/cosseno perto de zero
            # evita que cos(90) apareça como 6.1e-17 e assuste quem só queria 0.
            if abs(resultado) < 1e-15:
                return 0.0
            return self._finito(resultado)

        if nome in TRIGONOMETRICAS_INVERSAS:
            valor = self._exigir_um(nome, argumentos)
            funcao = {"asin": _asin, "asen": _asin, "acos": _acos, "atan": math.atan}[nome]
            resultado = funcao(valor)
            if self.angulo == Angulo.GRAUS:
                resultado = math.degrees(resultado)
            return resultado

        funcao = FUNCOES.get(nome)
        if funcao is None:
            raise NomeDesconhecidoError(f"Não conheço a função {nome!r}.")
        try:
            return float(funcao(*argumentos))
        except (ErroDeCalculo, TypeError) as erro:
            if isinstance(erro, ErroDeCalculo):
                raise
            raise ExpressaoInvalidaError(
                f"A função {nome!r} não aceita {len(argumentos)} argumento(s)."
            ) from erro
        except (ValueError, OverflowError) as erro:
            raise DominioError(f"{nome}: {erro}") from erro

    @staticmethod
    def _exigir_um(nome: str, argumentos: List[float]) -> float:
        if len(argumentos) != 1:
            raise ExpressaoInvalidaError(f"{nome} precisa de exatamente um argumento.")
        return argumentos[0]

    def _aplicar(self, operador: str, esquerda: float, direita: float) -> float:
        if operador == "+":
            return esquerda + direita
        if operador == "-":
            return esquerda - direita
        if operador == "*":
            return esquerda * direita
        if operador in ("/", "//", "%"):
            if direita == 0:
                raise DominioError("Não se divide por zero.")
            if operador == "/":
                return esquerda / direita
            if operador == "//":
                return float(math.floor(esquerda / direita))
            return math.fmod(esquerda, direita)
        if operador == "^":
            try:
                resultado = esquerda**direita
            except (OverflowError, ZeroDivisionError) as erro:
                raise DominioError(f"Potência impossível: {erro}") from erro
            if isinstance(resultado, complex):
                raise DominioError("Essa potência não dá um número real.")
            return self._finito(resultado)
        raise ExpressaoInvalidaError(f"Operador desconhecido: {operador!r}")  # pragma: no cover


def avaliar(expressao: str, angulo: Angulo = Angulo.GRAUS) -> float:
    """Atalho para uma avaliação única."""
    return Calculadora(angulo).avaliar(expressao)
