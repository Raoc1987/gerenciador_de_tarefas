"""Indicadores (KPIs) calculados a partir das tarefas.

Funções puras: recebem as tarefas já lidas e devolvem números. É isto que
garante que dashboard, relatórios e alertas mostram sempre o mesmo valor —
está calculado num sítio só.

Formato esperado de cada tarefa (ver ``banco_de_dados.COLUNAS_TAREFA_COMPLETA``)::

    (id, descrição, data_vencimento, concluída, criada_em, concluída_em)

A sexta posição é opcional: tuplas de cinco elementos também funcionam,
tratando ``concluída_em`` como desconhecida.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence

from analitica.datas import para_data


@dataclass(frozen=True)
class Tarefa:
    """Uma tarefa, já normalizada para análise."""

    id: int
    descricao: str
    vencimento: Optional[date]
    concluida: bool
    criada_em: Optional[date]
    concluida_em: Optional[date]

    @classmethod
    def de_tupla(cls, linha: Sequence) -> "Tarefa":
        """Converte uma linha do banco (5 ou 6 colunas)."""
        return cls(
            id=int(linha[0]),
            descricao=str(linha[1]),
            vencimento=para_data(linha[2]),
            concluida=bool(linha[3]),
            criada_em=para_data(linha[4]),
            concluida_em=para_data(linha[5]) if len(linha) > 5 else None,
        )

    def esta_atrasada(self, hoje: date) -> bool:
        """Pendente e com vencimento já passado."""
        return (
            not self.concluida
            and self.vencimento is not None
            and self.vencimento < hoje
        )

    def dias_ate_vencer(self, hoje: date) -> Optional[int]:
        """Dias que faltam até vencer (negativo se já passou)."""
        if self.vencimento is None:
            return None
        return (self.vencimento - hoje).days

    def duracao_em_dias(self) -> Optional[int]:
        """Dias entre a criação e a conclusão."""
        if self.criada_em is None or self.concluida_em is None:
            return None
        return max((self.concluida_em - self.criada_em).days, 0)


def normalizar(tarefas: Iterable[Sequence]) -> List[Tarefa]:
    """Converte linhas do banco em :class:`Tarefa`."""
    return [t if isinstance(t, Tarefa) else Tarefa.de_tupla(t) for t in tarefas]


@dataclass(frozen=True)
class KPIs:
    """Os indicadores de um conjunto de tarefas, num dado dia."""

    total: int = 0
    concluidas: int = 0
    pendentes: int = 0
    atrasadas: int = 0
    vencem_hoje: int = 0
    sem_prazo: int = 0
    taxa_conclusao: float = 0.0
    """Percentagem de tarefas concluídas (0–100)."""

    taxa_atraso: float = 0.0
    """Percentagem das pendentes que está atrasada (0–100)."""

    duracao_media_dias: Optional[float] = None
    """Média de dias entre criar e concluir, quando há dados para a calcular."""

    @property
    def tem_dados(self) -> bool:
        """Se há alguma tarefa para analisar."""
        return self.total > 0


def _percentagem(parte: int, total: int) -> float:
    return round(parte * 100 / total, 1) if total else 0.0


def calcular_kpis(tarefas: Iterable[Sequence], hoje: Optional[date] = None) -> KPIs:
    """Calcula os indicadores de um conjunto de tarefas.

    Args:
        tarefas: linhas do banco ou :class:`Tarefa` já normalizadas.
        hoje: data de referência para atraso (por omissão, hoje).
    """
    hoje = hoje or date.today()
    itens = normalizar(tarefas)
    if not itens:
        return KPIs()

    concluidas = [t for t in itens if t.concluida]
    pendentes = [t for t in itens if not t.concluida]
    atrasadas = [t for t in pendentes if t.esta_atrasada(hoje)]
    vencem_hoje = [t for t in pendentes if t.vencimento == hoje]
    sem_prazo = [t for t in pendentes if t.vencimento is None]

    duracoes = [d for d in (t.duracao_em_dias() for t in concluidas) if d is not None]

    return KPIs(
        total=len(itens),
        concluidas=len(concluidas),
        pendentes=len(pendentes),
        atrasadas=len(atrasadas),
        vencem_hoje=len(vencem_hoje),
        sem_prazo=len(sem_prazo),
        taxa_conclusao=_percentagem(len(concluidas), len(itens)),
        taxa_atraso=_percentagem(len(atrasadas), len(pendentes)),
        duracao_media_dias=round(sum(duracoes) / len(duracoes), 1) if duracoes else None,
    )


def filtrar_por_periodo(
    tarefas: Iterable[Sequence],
    inicio: Optional[date] = None,
    fim: Optional[date] = None,
    campo: str = "criada_em",
) -> List[Tarefa]:
    """Tarefas cujo ``campo`` cai no intervalo (extremos incluídos).

    Args:
        campo: ``"criada_em"``, ``"concluida_em"`` ou ``"vencimento"``.

    Tarefas sem data nesse campo ficam de fora — não se inventa uma data.
    """
    itens = normalizar(tarefas)
    resultado = []
    for tarefa in itens:
        valor = getattr(tarefa, campo)
        if valor is None:
            continue
        if inicio is not None and valor < inicio:
            continue
        if fim is not None and valor > fim:
            continue
        resultado.append(tarefa)
    return resultado


def contar_por(tarefas: Iterable[Sequence], classificador) -> dict:
    """Conta tarefas agrupadas por uma função de classificação.

    Ex.: ``contar_por(tarefas, lambda t: "concluída" if t.concluida else "pendente")``
    """
    contagem: dict = {}
    for tarefa in normalizar(tarefas):
        chave = classificador(tarefa)
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def comparar(atual: KPIs, anterior: KPIs) -> dict:
    """Variação percentual entre dois períodos, por indicador.

    Devolve ``None`` para um indicador cujo período anterior era zero: uma
    variação percentual sobre zero não significa nada.
    """
    campos = ("total", "concluidas", "pendentes", "atrasadas", "taxa_conclusao")
    variacoes = {}
    for campo in campos:
        antes = getattr(anterior, campo)
        agora = getattr(atual, campo)
        variacoes[campo] = round((agora - antes) * 100 / antes, 1) if antes else None
    return variacoes
