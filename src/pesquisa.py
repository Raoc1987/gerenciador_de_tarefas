"""Pesquisa global: uma caixa que procura em tudo o que existir.

Cada parte da aplicação **regista o que sabe procurar**; a pesquisa junta as
respostas. Não sabe o que é uma tarefa nem um item de inventário, e é isso que
permite a um módulo novo aparecer aqui sem tocar neste ficheiro.

É o mesmo padrão do catálogo de ações do motor de regras (:mod:`regras.acoes`),
e pela mesma razão: um sítio que conhecesse todos os domínios seria o ponto
onde o produto se voltaria a colar todo.

**Classificação (ADR-0004): Service.** Não é Core. O `CLASSIFICACAO.md` dizia
Core, e estava errado — um registo destes vive bem fora do núcleo, como o das
ações já demonstrou, e o núcleo não precisa de crescer para isto existir.

Duas regras que o resto do ficheiro serve:

* **quem regista aplica as suas permissões.** A pesquisa não filtra resultados
  por si; devolve o que cada fonte lhe der. Uma fonte que devolva o que a
  sessão não pode ver é uma fuga, e a defesa tem de estar onde os dados estão;
* **uma fonte que falha não estraga a pesquisa.** Um plugin partido deixa de
  contribuir, e as restantes respondem à mesma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from core.log import obter_logger

logger = obter_logger(__name__)

#: Quantos resultados se pedem a cada fonte.
#:
#: Um limite por fonte, e não só no total: sem ele, uma fonte com muitos
#: resultados enchia a lista e escondia as outras — e quem procura deixava de
#: saber que as outras existem.
LIMITE_POR_FONTE = 8

#: Comprimento mínimo do termo.
#:
#: Uma letra devolve tudo, e "tudo" não é um resultado de pesquisa: é a base
#: de dados impressa no ecrã.
MINIMO_DO_TERMO = 2


@dataclass(frozen=True)
class Resultado:
    """Uma coisa encontrada.

    Attributes:
        fonte: quem a encontrou — serve para agrupar e para traduzir.
        titulo: o que se lê primeiro.
        detalhe: contexto, numa linha.
        chave: identificador dentro da fonte, para quem quiser lá chegar.
    """

    fonte: str
    titulo: str
    detalhe: str = ""
    chave: str = ""


#: Uma fonte recebe o termo e o limite, e devolve resultados.
Procurador = Callable[[str, int], Sequence[Resultado]]


@dataclass(frozen=True)
class Fonte:
    """Algo que sabe procurar."""

    nome: str
    procurar: Procurador
    chave_titulo: str = ""
    dono: str = ""


_FONTES: Dict[str, Fonte] = {}


def registar(
    nome: str, procurar: Procurador, chave_titulo: str = "", dono: str = ""
) -> Fonte:
    """Põe uma fonte ao serviço da pesquisa.

    Registar o mesmo nome substitui — é o que acontece quando um plugin é
    recarregado, e falhar aí obrigaria a reiniciar a aplicação.

    Raises:
        ValueError: nome vazio ou procurador que não é chamável.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Uma fonte de pesquisa precisa de um nome.")
    if not callable(procurar):
        raise ValueError(f"A fonte {nome!r} não é uma função.")

    fonte = Fonte(nome, procurar, chave_titulo or f"pesquisa_fonte_{nome}", dono)
    _FONTES[nome] = fonte
    logger.info("Fonte de pesquisa registada: %s", nome)
    return fonte


def esquecer(nome: str) -> bool:
    """Tira uma fonte do registo."""
    return _FONTES.pop((nome or "").strip(), None) is not None


def esquecer_por_dono(dono: str) -> int:
    """Tira todas as fontes de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [nome for nome, fonte in _FONTES.items() if fonte.dono == dono]
    for nome in saem:
        _FONTES.pop(nome, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _FONTES.clear()


def fontes() -> List[Fonte]:
    """As fontes registadas, por nome."""
    return [_FONTES[nome] for nome in sorted(_FONTES)]


def procurar(termo: str, limite_por_fonte: int = LIMITE_POR_FONTE) -> List[Resultado]:
    """Procura em todas as fontes e junta o que encontrarem.

    Um termo curto demais devolve nada — não é um erro, é a resposta certa a
    uma pergunta vaga.

    Uma fonte que rebenta é registada e ignorada: um módulo partido não pode
    tornar a pesquisa inútil para os outros.
    """
    termo = (termo or "").strip()
    if len(termo) < MINIMO_DO_TERMO:
        return []

    encontrados: List[Resultado] = []
    for fonte in fontes():
        try:
            resultados = list(fonte.procurar(termo, limite_por_fonte))
        except Exception:
            logger.exception("A fonte de pesquisa %r falhou.", fonte.nome)
            continue
        encontrados.extend(resultados[:limite_por_fonte])
    return encontrados


def agrupados(termo: str, limite_por_fonte: int = LIMITE_POR_FONTE) -> Dict[str, List[Resultado]]:
    """O mesmo, arrumado por fonte — é como se mostra numa lista."""
    por_fonte: Dict[str, List[Resultado]] = {}
    for resultado in procurar(termo, limite_por_fonte):
        por_fonte.setdefault(resultado.fonte, []).append(resultado)
    return por_fonte


def contem(texto: object, termo: str) -> bool:
    """Se o termo aparece no texto, sem distinguir maiúsculas nem acentos.

    Quem procura "atrasada" tem de encontrar "Atrasadas"; quem procura
    "reuniao" tem de encontrar "reunião". Obrigar a escrever o acento certo
    para encontrar o que já se sabe que existe é hostil.
    """
    import unicodedata

    def simples(valor: str) -> str:
        sem_acentos = unicodedata.normalize("NFKD", str(valor))
        return "".join(c for c in sem_acentos if not unicodedata.combining(c)).lower()

    return simples(termo) in simples(texto or "")
