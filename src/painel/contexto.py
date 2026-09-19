"""O que está filtrado neste momento, e os dados que daí resultam.

Um widget do painel não vai buscar dados: **recebe-os**. É o que permite que
o mesmo widget sirva o painel principal, um painel de gestão e um relatório —
e é o que impede cada cartão de abrir a sua própria ligação ao banco e de dar
um número diferente do cartão do lado.

O contexto é a forma dos **filtros globais**. Hoje tem o período, que é o
único filtro que existe; amanhã terá a unidade, o responsável, o estado.
Acrescentar um campo não parte um widget que o ignore — é por isso que isto é
um objeto e não uma lista de argumentos.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional


@dataclass(frozen=True)
class Contexto:
    """O estado dos filtros, e o panorama já calculado para eles.

    Attributes:
        dias: o período em dias.
        panorama: o resultado da análise para este período, ou ``None``
            enquanto ainda não foi calculado — um widget tem de saber
            desenhar-se sem dados, porque há sempre um instante em que não os
            há.
        unidade: a unidade da organização a que o painel está restrito.
            Ainda não há interface que a mude; está aqui porque o campo tem
            de existir antes de haver quem o leia, e não depois.
    """

    dias: int = 30
    panorama: Optional[Any] = None
    unidade: Optional[int] = None
    #: Porque é que não há dados, quando não há.
    #:
    #: Sem permissão, ou com erro a ler. Um widget que receba isto mostra a
    #: razão em vez de um zero — um painel que responde "0" a "não tens
    #: permissão" está a mentir com um número.
    mensagem: Optional[str] = None

    @property
    def tem_dados(self) -> bool:
        return self.panorama is not None

    def com(self, **mudancas) -> "Contexto":
        """Uma cópia com alguns campos trocados."""
        return replace(self, **mudancas)
