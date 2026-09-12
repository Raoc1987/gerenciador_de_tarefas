"""Estrutura de um relatório, independente do formato de saída.

Um relatório é uma lista de secções com dados já calculados e já traduzidos.
Quem o constrói não sabe se vai virar CSV, XLSX ou PDF; quem o exporta não
sabe de onde vieram os números.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class Indicadores:
    """Pares rótulo/valor, como os cartões do dashboard."""

    titulo: str
    itens: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        """Se não há nada para mostrar."""
        return not self.itens


@dataclass(frozen=True)
class Tabela:
    """Linhas e colunas. Os valores já vêm formatados como texto."""

    titulo: str
    colunas: List[str] = field(default_factory=list)
    linhas: List[List[str]] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        """Se não há linhas."""
        return not self.linhas

    def validar(self) -> None:
        """Confirma que todas as linhas têm o número certo de colunas.

        Raises:
            ValueError: se alguma linha divergir do cabeçalho.
        """
        for indice, linha in enumerate(self.linhas):
            if len(linha) != len(self.colunas):
                raise ValueError(
                    f"Linha {indice} da tabela {self.titulo!r} tem {len(linha)} "
                    f"valores, esperados {len(self.colunas)}."
                )


@dataclass(frozen=True)
class Lista:
    """Pontos soltos — a análise em texto, por exemplo."""

    titulo: str
    itens: List[str] = field(default_factory=list)

    @property
    def vazia(self) -> bool:
        """Se não há itens."""
        return not self.itens


Secao = Union[Indicadores, Tabela, Lista]


@dataclass(frozen=True)
class Relatorio:
    """Um relatório completo, pronto a exportar."""

    titulo: str
    subtitulo: str = ""
    gerado_em: datetime = field(default_factory=datetime.now)
    inicio: Optional[date] = None
    fim: Optional[date] = None
    secoes: List[Secao] = field(default_factory=list)
    rodape: str = ""

    def validar(self) -> None:
        """Valida as secções que têm invariantes próprias."""
        for secao in self.secoes:
            if isinstance(secao, Tabela):
                secao.validar()

    def secoes_com_conteudo(self) -> List[Secao]:
        """Só as secções que têm alguma coisa dentro."""
        return [secao for secao in self.secoes if not secao.vazia]

    @property
    def periodo(self) -> str:
        """Período em texto, ou vazio se o relatório não for de um período."""
        if self.inicio and self.fim:
            return f"{self.inicio.strftime('%d/%m/%Y')} – {self.fim.strftime('%d/%m/%Y')}"
        return ""


def texto_seguro(valor) -> str:
    """Converte qualquer valor para texto, tratando ``None`` como vazio."""
    if valor is None:
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def como_linhas(secao: Secao) -> Sequence[Sequence[str]]:
    """Representação tabular de qualquer secção.

    É o que permite exportar tudo para formatos de grelha (CSV, XLSX) sem
    cada exportador ter de conhecer todos os tipos de secção.
    """
    if isinstance(secao, Tabela):
        return [list(secao.colunas), *[[texto_seguro(v) for v in l] for l in secao.linhas]]
    if isinstance(secao, Indicadores):
        return [[texto_seguro(r), texto_seguro(v)] for r, v in secao.itens]
    if isinstance(secao, Lista):
        return [[texto_seguro(item)] for item in secao.itens]
    raise TypeError(f"Secção desconhecida: {type(secao).__name__}")  # pragma: no cover
