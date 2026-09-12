"""O que é uma regra, e como se decide se ela se aplica.

Puro: recebe dados, devolve uma resposta. Não sabe o que é o barramento, uma
base de dados ou uma janela — o que torna cada decisão testável sozinha.

As condições são **declarativas**: campo, operador, valor. Não há expressões
escritas pelo utilizador a serem avaliadas, pela mesma razão que não há
``eval`` na calculadora — uma regra guardada no banco é texto que alguém pode
alterar, e texto alterável não deve virar código a correr.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class Operador(str, Enum):
    """Como comparar o valor do evento com o valor da condição."""

    IGUAL = "igual"
    DIFERENTE = "diferente"
    MAIOR = "maior"
    MENOR = "menor"
    MAIOR_OU_IGUAL = "maior_ou_igual"
    MENOR_OU_IGUAL = "menor_ou_igual"
    CONTEM = "contem"
    COMECA_COM = "comeca_com"
    EXISTE = "existe"
    VAZIO = "vazio"


#: Operadores que não usam o valor da condição — só olham para o campo.
SEM_VALOR = {Operador.EXISTE, Operador.VAZIO}


class RegraInvalidaError(ValueError):
    """A regra não está bem formada e não pode ser guardada."""

    chave_mensagem = "workflow_regra_invalida"


@dataclass(frozen=True)
class Condicao:
    """Uma pergunta sobre os dados do evento."""

    campo: str
    operador: Operador = Operador.EXISTE
    valor: Any = None

    def verifica(self, dados: Dict[str, Any]) -> bool:
        """Se os dados do evento satisfazem esta condição.

        Um campo em falta responde ``False`` a tudo menos a ``VAZIO``: não se
        pode comparar o que não existe, e inventar uma resposta esconderia um
        engano de quem escreveu a regra.
        """
        presente = self.campo in dados
        atual = dados.get(self.campo)

        if self.operador == Operador.EXISTE:
            return presente and atual not in (None, "")
        if self.operador == Operador.VAZIO:
            return not presente or atual in (None, "")
        if not presente:
            return False

        if self.operador == Operador.IGUAL:
            return _iguais(atual, self.valor)
        if self.operador == Operador.DIFERENTE:
            return not _iguais(atual, self.valor)
        if self.operador == Operador.CONTEM:
            return str(self.valor).lower() in str(atual).lower()
        if self.operador == Operador.COMECA_COM:
            return str(atual).lower().startswith(str(self.valor).lower())

        return _comparar(self.operador, atual, self.valor)

    def para_dicionario(self) -> Dict[str, Any]:
        return {"campo": self.campo, "operador": self.operador.value, "valor": self.valor}

    @classmethod
    def de_dicionario(cls, dados: Any) -> "Condicao":
        """Lê uma condição vinda do banco.

        Raises:
            RegraInvalidaError: se faltar o campo ou o operador não existir.
        """
        if not isinstance(dados, dict) or not str(dados.get("campo", "")).strip():
            raise RegraInvalidaError("Uma condição precisa de um campo.")
        try:
            operador = Operador(dados.get("operador", Operador.EXISTE.value))
        except ValueError as erro:
            raise RegraInvalidaError(
                f"Operador desconhecido: {dados.get('operador')!r}."
            ) from erro
        return cls(str(dados["campo"]).strip(), operador, dados.get("valor"))


def _iguais(atual: Any, esperado: Any) -> bool:
    """Compara sem tropeçar em ``"5"`` contra ``5``.

    Os dados de um evento vêm de código; os valores de uma regra vêm de um
    formulário, e chegam como texto. Exigir que os tipos batam certo faria
    regras corretas nunca dispararem, sem dizer porquê.
    """
    if atual == esperado:
        return True
    numeros = _como_numeros(atual, esperado)
    if numeros is not None:
        return numeros[0] == numeros[1]
    return str(atual).strip().lower() == str(esperado).strip().lower()


def _como_numeros(*valores: Any) -> Optional[Tuple[float, ...]]:
    """Os valores como números, ou ``None`` se algum não for."""
    try:
        return tuple(float(str(valor).strip().replace(",", ".")) for valor in valores)
    except (TypeError, ValueError):
        return None


def _comparar(operador: Operador, atual: Any, esperado: Any) -> bool:
    """Os operadores de ordem, que só fazem sentido entre números."""
    numeros = _como_numeros(atual, esperado)
    if numeros is None:
        return False
    a, b = numeros
    return {
        Operador.MAIOR: a > b,
        Operador.MENOR: a < b,
        Operador.MAIOR_OU_IGUAL: a >= b,
        Operador.MENOR_OU_IGUAL: a <= b,
    }[operador]


@dataclass(frozen=True)
class Acao:
    """O que fazer, e com que argumentos.

    ``nome`` é a chave de uma ação registada. O motor não sabe o que ela faz;
    quem a registou é que sabe.
    """

    nome: str
    argumentos: Dict[str, Any] = field(default_factory=dict)

    def para_dicionario(self) -> Dict[str, Any]:
        return {"nome": self.nome, "argumentos": dict(self.argumentos)}

    @classmethod
    def de_dicionario(cls, dados: Any) -> "Acao":
        if not isinstance(dados, dict) or not str(dados.get("nome", "")).strip():
            raise RegraInvalidaError("Uma ação precisa de um nome.")
        argumentos = dados.get("argumentos") or {}
        if not isinstance(argumentos, dict):
            raise RegraInvalidaError("Os argumentos de uma ação são um objeto.")
        return cls(str(dados["nome"]).strip(), argumentos)


@dataclass(frozen=True)
class Regra:
    """Quando acontece ``evento``, e se as ``condicoes`` se verificarem, faz ``acoes``."""

    id: int
    nome: str
    evento: str
    condicoes: Tuple[Condicao, ...] = ()
    acoes: Tuple[Acao, ...] = ()
    ativa: bool = True
    criada_em: str = ""
    criada_por: str = ""

    def aplica_se(self, dados: Dict[str, Any]) -> bool:
        """Se **todas** as condições se verificam.

        Sem condições, aplica-se sempre: uma regra que só olha para o tipo de
        evento é legítima, e obrigar a inventar uma condição seria ruído.
        """
        return all(condicao.verifica(dados) for condicao in self.condicoes)


def validar_evento(evento: str) -> str:
    """Valida o padrão de evento de uma regra.

    Raises:
        RegraInvalidaError: se estiver vazio, ou se for ``*`` — reagir a tudo
            inclui reagir aos eventos que a própria regra provoca, e é a forma
            mais rápida de montar um ciclo sem dar por isso.
    """
    evento = (evento or "").strip()
    if not evento:
        raise RegraInvalidaError("A regra precisa de um evento.")
    if evento == "*":
        raise RegraInvalidaError(
            "Uma regra não pode reagir a todos os eventos: escolha uma família "
            "(ex.: 'tarefa.*') ou um evento concreto."
        )
    return evento
