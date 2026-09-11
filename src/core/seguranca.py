"""Palavras-passe: derivação, verificação e força.

Uma palavra-passe **nunca** é guardada nem registada em lado nenhum — o que
se guarda é o resultado de uma derivação lenta com sal próprio, do qual não se
volta atrás.

Algoritmo: PBKDF2-HMAC-SHA256, da biblioteca padrão (ADR-0002: nada de
dependências novas). Não é o mais moderno — Argon2 e scrypt resistem melhor a
ataque com hardware dedicado — mas é o melhor que a biblioteca padrão oferece
sem compilar nada, e o formato guardado inclui o algoritmo e o número de
iterações, para se poder mudar depois sem invalidar as contas existentes.

Formato guardado::

    pbkdf2_sha256$<iterações>$<sal em base64>$<derivado em base64>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata
from typing import List

ALGORITMO = "pbkdf2_sha256"

#: Custo atual. ~90 ms nesta geração de máquinas: incomodativo para quem
#: tenta adivinhar, imperceptível para quem sabe a palavra-passe.
ITERACOES = 320_000

TAMANHO_DO_SAL = 16
COMPRIMENTO_MINIMO = 8
COMPRIMENTO_MAXIMO = 128

#: As mais usadas do mundo; recusá-las evita o pior caso por um custo nulo.
_TRIVIAIS = {
    "password", "palavra-passe", "passe", "123456", "12345678", "123456789",
    "qwerty", "abc123", "senha", "senha123", "admin", "administrador",
    "111111", "iloveyou", "gerenciador", "tarefas",
}


class SenhaInvalidaError(ValueError):
    """A palavra-passe não cumpre os requisitos mínimos."""

    def __init__(self, problemas: List[str]) -> None:
        super().__init__("; ".join(problemas))
        self.problemas = problemas
        self.chave_mensagem = "senha_invalida"


def _normalizar(senha: str) -> bytes:
    """Normaliza para que a mesma palavra-passe digitada de formas diferentes
    (acentos compostos vs. pré-compostos) dê sempre o mesmo resultado."""
    return unicodedata.normalize("NFKC", senha).encode("utf-8")


def gerar_hash(senha: str, iteracoes: int = ITERACOES) -> str:
    """Deriva a palavra-passe com um sal novo e devolve a forma a guardar."""
    if not isinstance(senha, str) or not senha:
        raise SenhaInvalidaError(["senha_vazia"])

    sal = os.urandom(TAMANHO_DO_SAL)
    derivado = hashlib.pbkdf2_hmac("sha256", _normalizar(senha), sal, iteracoes)
    return "$".join(
        (
            ALGORITMO,
            str(iteracoes),
            base64.b64encode(sal).decode("ascii"),
            base64.b64encode(derivado).decode("ascii"),
        )
    )


def verificar(senha: str, guardado: str) -> bool:
    """Confirma uma palavra-passe contra a forma guardada.

    A comparação é feita em tempo constante: comparar byte a byte deixaria o
    tempo de resposta revelar quantos bytes acertaram.
    """
    if not senha or not guardado:
        return False

    try:
        algoritmo, iteracoes, sal_b64, derivado_b64 = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(derivado_b64)
        obtido = hashlib.pbkdf2_hmac("sha256", _normalizar(senha), sal, int(iteracoes))
    except (ValueError, TypeError, base64.binascii.Error):
        return False

    return hmac.compare_digest(obtido, esperado)


def precisa_de_rehash(guardado: str, iteracoes: int = ITERACOES) -> bool:
    """Se o registo foi criado com um custo inferior ao atual.

    Permite subir o custo com o tempo: quando alguém entra com sucesso, o
    registo é regravado com o número de iterações corrente.
    """
    try:
        algoritmo, atuais, _, _ = guardado.split("$")
    except (ValueError, AttributeError):
        return True
    return algoritmo != ALGORITMO or int(atuais) < iteracoes


def problemas_da_senha(senha: str, nome_utilizador: str = "") -> List[str]:
    """Chaves de tradução dos requisitos que a palavra-passe não cumpre.

    Lista vazia significa aceitável. Devolve chaves e não frases para a
    interface as poder traduzir.
    """
    problemas: List[str] = []
    if not senha:
        return ["senha_vazia"]

    if len(senha) < COMPRIMENTO_MINIMO:
        problemas.append("senha_curta")
    if len(senha) > COMPRIMENTO_MAXIMO:
        problemas.append("senha_longa")
    if senha.strip() != senha:
        problemas.append("senha_com_espacos_nas_pontas")
    if senha.isdigit():
        problemas.append("senha_so_digitos")
    if senha.lower() in _TRIVIAIS:
        problemas.append("senha_trivial")
    if nome_utilizador and nome_utilizador.lower() in senha.lower():
        problemas.append("senha_contem_utilizador")
    if re.fullmatch(r"(.)\1*", senha):
        problemas.append("senha_repetitiva")
    return problemas


def validar_senha(senha: str, nome_utilizador: str = "") -> None:
    """Garante que a palavra-passe é aceitável.

    Raises:
        SenhaInvalidaError: com a lista de problemas encontrados.
    """
    problemas = problemas_da_senha(senha, nome_utilizador)
    if problemas:
        raise SenhaInvalidaError(problemas)
