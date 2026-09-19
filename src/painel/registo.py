"""Quem tem alguma coisa para mostrar no painel, regista-a.

Antes disto, o painel era uma lista fixa: cinco cartões, dois gráficos e uma
caixa de análise, escritos à mão em ``dashboard_ui.py``. Um módulo de negócio
podia declarar um **número** (ver :mod:`indicadores`), mas não um gráfico nem
uma tabela — e "a análise atravessa todo o produto" ficava por cumprir no
sítio onde mais se nota.

Um widget declara-se com o espaço que ocupa, a ordem, a permissão e a
funcionalidade de que depende. A grelha desenha o que estiver registado e não
sabe o que nenhum deles mostra — o mesmo padrão dos indicadores, da pesquisa,
dos destinos de importação, das políticas e dos destinos de navegação.

O contrato de um widget é pequeno de propósito:

* ``construir(pai)`` devolve um widget do Tk;
* se esse widget tiver ``atualizar(contexto)``, a grelha chama-o sempre que
  os filtros mudam. Se não tiver, é desenhado uma vez e fica quieto — o que
  chega para uma nota, uma legenda ou uma ligação.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)

#: Quantas colunas tem a grelha à largura máxima.
#:
#: Quatro, e não doze como na web: um widget de 1/12 de um ecrã de secretária
#: não cabe com um número dentro. A grelha reparte-se em 4, 2 ou 1 conforme a
#: largura, o que dá três arranjos legíveis em vez de doze frações.
COLUNAS = 4


@dataclass(frozen=True)
class Widget:
    """Uma coisa que aparece no painel."""

    id: str
    chave_titulo: str
    construir: Callable
    #: Quantas colunas ocupa, de 1 a :data:`COLUNAS`.
    largura: int = 1
    ordem: int = 100
    permissao: Optional[str] = None
    funcionalidade: Optional[str] = None
    dono: str = ""

    def visivel(self) -> bool:
        """Se esta sessão, nesta instalação, deve ver este widget."""
        if self.funcionalidade is not None:
            from core import funcionalidades

            try:
                if not funcionalidades.ativa(self.funcionalidade):
                    return False
            except Exception:
                logger.exception(
                    "O widget %s depende da funcionalidade %r, que não existe.",
                    self.id,
                    self.funcionalidade,
                )
                return False
        if self.permissao is None:
            return True
        from core import permissoes

        return permissoes.pode(self.permissao)


_WIDGETS: Dict[str, Widget] = {}


def registar(
    id: str,
    chave_titulo: str,
    construir: Callable,
    largura: int = 1,
    ordem: int = 100,
    permissao: Optional[str] = None,
    funcionalidade: Optional[str] = None,
    dono: str = "",
) -> Widget:
    """Põe um widget no painel.

    Raises:
        ValueError: id vazio, construtor que não é chamável, largura fora de
            1..4, ou — vindo de um módulo — id fora do espaço de nomes desse
            módulo.
    """
    id = (id or "").strip()
    if not id:
        raise ValueError("Um widget precisa de um id.")
    if not callable(construir):
        raise ValueError(f"O widget {id!r} precisa de algo que o construa.")
    if not 1 <= largura <= COLUNAS:
        raise ValueError(
            f"O widget {id!r} pediu {largura} colunas; a grelha tem {COLUNAS}."
        )
    if dono and not id.startswith(f"{dono}."):
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar os seus widgets com {dono + '.'!r}."
        )

    widget = Widget(id, chave_titulo, construir, largura, ordem, permissao,
                    funcionalidade, dono)
    _WIDGETS[id] = widget
    logger.info("Widget de painel registado: %s (%d colunas)", id, largura)
    return widget


def esquecer_por_dono(dono: str) -> int:
    """Tira os widgets de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [id for id, w in _WIDGETS.items() if w.dono == dono]
    for id in saem:
        _WIDGETS.pop(id, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _WIDGETS.clear()


def obter(id: str) -> Optional[Widget]:
    return _WIDGETS.get((id or "").strip())


def disponiveis() -> List[Widget]:
    """Os widgets visíveis, pela ordem declarada."""
    return sorted(
        (w for w in _WIDGETS.values() if w.visivel()),
        key=lambda w: (w.ordem, w.id),
    )
