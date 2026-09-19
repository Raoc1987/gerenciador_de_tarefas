"""Onde cada destino da aplicação declara que existe, e onde vive.

Antes disto, uma aba nova era uma linha acrescentada à mão em ``gui.py`` —
o que obrigava a janela principal a conhecer todos os módulos do produto.
Com trinta módulos, é o monólito de volta pela porta das traseiras.

Aqui um destino **declara-se**: o nome, o grupo onde aparece na barra
lateral, a permissão que exige e a ordem. A concha desenha o que estiver
registado e não sabe o que é nenhum deles — o mesmo padrão dos indicadores,
das fontes de pesquisa e dos destinos de importação.

Um destino que exige uma permissão que a sessão não tem **não aparece**:
oferecer para depois recusar é pior do que não oferecer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)

#: Os grupos da barra lateral, pela ordem em que aparecem.
#:
#: A lista é fechada de propósito. Um grupo novo por cada módulo daria uma
#: barra lateral com vinte secções de um item — que é uma lista, não uma
#: organização.
GRUPOS = ("principal", "operacoes", "inteligencia", "sistema")

GRUPO_PADRAO = "principal"


@dataclass(frozen=True)
class Destino:
    """Um sítio onde se pode estar na aplicação."""

    id: str
    grupo: str
    #: Chave de tradução do nome. Texto fixo também serve, mas não traduz.
    chave_titulo: str
    #: Um caractere ou dois para a barra recolhida. Sem ícones em ficheiro:
    #: seriam uma dependência e um problema de nitidez em cada resolução.
    marca: str = "•"
    ordem: int = 100
    permissao: Optional[str] = None
    funcionalidade: Optional[str] = None
    dono: str = ""

    def visivel(self) -> bool:
        """Se esta sessão, nesta instalação, deve ver este destino."""
        if self.funcionalidade is not None:
            from core import funcionalidades

            try:
                if not funcionalidades.ativa(self.funcionalidade):
                    return False
            except Exception:
                # Uma funcionalidade que não existe é uma declaração errada.
                # Esconder é a resposta segura: mostrar um destino que não se
                # sabe se devia existir é pior do que faltar um.
                logger.exception(
                    "O destino %s depende da funcionalidade %r, que não existe.",
                    self.id,
                    self.funcionalidade,
                )
                return False
        if self.permissao is None:
            return True
        from core import permissoes

        return permissoes.pode(self.permissao)


_DESTINOS: Dict[str, Destino] = {}


def registar(
    id: str,
    chave_titulo: str,
    grupo: str = GRUPO_PADRAO,
    marca: str = "•",
    ordem: int = 100,
    permissao: Optional[str] = None,
    funcionalidade: Optional[str] = None,
    dono: str = "",
) -> Destino:
    """Põe um destino na barra lateral.

    Raises:
        ValueError: id vazio, grupo desconhecido, ou — vindo de um módulo —
            id fora do espaço de nomes desse módulo.
    """
    id = (id or "").strip()
    if not id:
        raise ValueError("Um destino precisa de um id.")
    if grupo not in GRUPOS:
        raise ValueError(
            f"Grupo {grupo!r} desconhecido. Use um de: {', '.join(GRUPOS)}."
        )
    if dono and not id.startswith(f"{dono}."):
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar os seus destinos com {dono + '.'!r}."
        )

    destino = Destino(id, grupo, chave_titulo, marca, ordem, permissao, funcionalidade, dono)
    _DESTINOS[id] = destino
    logger.info("Destino registado: %s (grupo %s)", id, grupo)
    return destino


def esquecer_por_dono(dono: str) -> int:
    """Tira os destinos de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [id for id, d in _DESTINOS.items() if d.dono == dono]
    for id in saem:
        _DESTINOS.pop(id, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _DESTINOS.clear()


def obter(id: str) -> Optional[Destino]:
    return _DESTINOS.get((id or "").strip())


def por_grupo() -> List[tuple]:
    """Os destinos visíveis, agrupados e ordenados.

    Returns:
        ``[(grupo, [destinos])]``, na ordem de :data:`GRUPOS`, sem os grupos
        que ficariam vazios — um título de secção sem nada por baixo é ruído.
    """
    resultado = []
    for grupo in GRUPOS:
        dentro = sorted(
            (d for d in _DESTINOS.values() if d.grupo == grupo and d.visivel()),
            key=lambda d: (d.ordem, d.chave_titulo),
        )
        if dentro:
            resultado.append((grupo, dentro))
    return resultado
