"""Indicadores declarados: cada módulo diz o que sabe medir.

O painel mostra tarefas porque o painel foi escrito para tarefas. Um módulo de
negócio instalado não aparece lá — e "a análise atravessa todo o produto" fica
por cumprir no sítio onde mais se nota.

Aqui cada parte da aplicação **declara** um indicador: a chave, como se
calcula, e se subir é bom. O painel mostra o que estiver registado sem saber o
que é um item de inventário.

**Service** (ADR-0004), como a pesquisa. Não é Core: é um registo, e os
registos já provaram que vivem bem fora do núcleo.

Três regras que o resto do ficheiro serve:

* **um indicador que falha não derruba o painel.** Uma divisão por zero num
  módulo não pode tapar os números de todos os outros;
* **um indicador pode exigir permissão.** Um número é informação: "há 3 itens
  abaixo do mínimo" diz que existe um inventário e como está;
* **sem dados diz-se "sem dados".** Mostrar zero quando não se sabe é mentir
  com um número, que é a forma mais convincente de mentir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)


@dataclass(frozen=True)
class Valor:
    """O que um indicador vale agora."""

    numero: Optional[float] = None
    """``None`` quando não há dados. Zero é um número; "não sei" não é."""

    sufixo: str = ""
    """Unidade ou símbolo a seguir ao número (``%``, ``un``)."""

    variacao: Optional[float] = None
    """Variação face ao período anterior, quando faz sentido compará-los."""

    @property
    def tem_dados(self) -> bool:
        return self.numero is not None

    def formatado(self) -> str:
        """O número como se lê num cartão."""
        if self.numero is None:
            return "—"
        if float(self.numero) == int(self.numero):
            texto = str(int(self.numero))
        else:
            texto = f"{self.numero:.1f}"
        return f"{texto}{self.sufixo}"


@dataclass(frozen=True)
class Indicador:
    """Algo que se mede.

    Attributes:
        chave: identificador estável, com o dono à frente quando vem de um
            módulo (``estoque.em_falta``).
        calcular: função sem argumentos que devolve um :class:`Valor`.
        subir_e_bom: se um número maior é melhor. "Tarefas atrasadas" não é.
        permissao: nome de uma permissão necessária para ver este número.
    """

    chave: str
    calcular: Callable[[], Valor]
    chave_titulo: str = ""
    subir_e_bom: bool = True
    permissao: Optional[str] = None
    dono: str = ""


@dataclass(frozen=True)
class Leitura:
    """Um indicador já calculado, pronto a mostrar."""

    indicador: Indicador
    valor: Valor

    @property
    def chave(self) -> str:
        return self.indicador.chave


_REGISTO: Dict[str, Indicador] = {}


def registar(
    chave: str,
    calcular: Callable[[], Valor],
    chave_titulo: str = "",
    subir_e_bom: bool = True,
    permissao: Optional[str] = None,
    dono: str = "",
) -> Indicador:
    """Põe um indicador à disposição do painel.

    Registar a mesma chave substitui — é o que acontece quando um plugin é
    recarregado.

    Raises:
        ValueError: chave vazia, função que não é chamável, ou — quando vem
            de um módulo — chave fora do espaço de nomes desse módulo.
    """
    chave = (chave or "").strip()
    if not chave:
        raise ValueError("Um indicador precisa de uma chave.")
    if not callable(calcular):
        raise ValueError(f"O indicador {chave!r} não é uma função.")
    if dono and not chave.startswith(f"{dono}."):
        # A mesma regra das permissões de módulo, pela mesma razão: dois
        # módulos que escolham "total" deixavam de se poder distinguir, e o
        # último a carregar apagava o outro sem aviso.
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar os seus indicadores com {dono + '.'!r}."
        )

    indicador = Indicador(
        chave, calcular, chave_titulo or f"indicador_{chave}", subir_e_bom, permissao, dono
    )
    _REGISTO[chave] = indicador
    logger.info("Indicador registado: %s", chave)
    return indicador


def esquecer(chave: str) -> bool:
    """Tira um indicador do registo."""
    return _REGISTO.pop((chave or "").strip(), None) is not None


def esquecer_por_dono(dono: str) -> int:
    """Tira todos os indicadores de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [chave for chave, i in _REGISTO.items() if i.dono == dono]
    for chave in saem:
        _REGISTO.pop(chave, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _REGISTO.clear()


def registados() -> List[Indicador]:
    """Os indicadores registados, por chave."""
    return [_REGISTO[chave] for chave in sorted(_REGISTO)]


def _pode_ver(indicador: Indicador) -> bool:
    if indicador.permissao is None:
        return True
    from core import permissoes

    return permissoes.pode(indicador.permissao)


def ler() -> List[Leitura]:
    """Calcula todos os indicadores que a sessão pode ver.

    Um indicador que rebenta é registado e omitido: um módulo partido não pode
    tapar os números dos outros. Um que a sessão não pode ver não aparece —
    nem sequer como "—", que já diria que existe.
    """
    leituras: List[Leitura] = []
    for indicador in registados():
        if not _pode_ver(indicador):
            continue
        try:
            valor = indicador.calcular()
        except Exception:
            logger.exception("O indicador %r falhou.", indicador.chave)
            continue
        if not isinstance(valor, Valor):  # pragma: no cover - defensivo
            logger.error("O indicador %r não devolveu um Valor.", indicador.chave)
            continue
        leituras.append(Leitura(indicador, valor))
    return leituras


def ler_de(dono: str) -> List[Leitura]:
    """Só os indicadores de um dono — para um módulo mostrar os seus."""
    return [leitura for leitura in ler() if leitura.indicador.dono == dono]
