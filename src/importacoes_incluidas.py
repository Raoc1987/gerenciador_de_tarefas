"""Para onde esta aplicação sabe importar.

A ligação fina entre :mod:`importacao`, que não conhece domínios, e as
tarefas. Um módulo de negócio regista os seus destinos pelo contexto do
plugin, sem passar por aqui.

A criação passa por :mod:`tarefas_servico`: uma importação não é uma forma de
escrever o que não se pode escrever à mão.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, List

from core.log import obter_logger
from importacao import motor
from importacao.motor import Campo

logger = obter_logger(__name__)

#: Formatos de data aceites, por ordem de tentativa.
#:
#: O primeiro é o que a aplicação usa; os outros são os que saem de uma folha
#: de cálculo portuguesa ou inglesa. Recusar "31/12/2030" porque não está em
#: ISO seria recusar o formato em que o ficheiro realmente vem.
FORMATOS_DE_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")

MAX_DESCRICAO = 500


def interpretar_data(texto: str) -> str:
    """Converte uma data escrita de várias maneiras para ``AAAA-MM-DD``.

    Devolve ``""`` se o texto estiver vazio — uma tarefa sem prazo é legítima.

    Raises:
        ValueError: se houver texto mas não for uma data reconhecível. Guardar
            "amanhã" como prazo daria uma lista que nunca mais faz sentido.
    """
    texto = (texto or "").strip()
    if not texto:
        return ""

    # Uma folha de cálculo pode trazer a data com hora colada.
    texto = texto.split("T")[0].split(" ")[0]
    for formato in FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Data não reconhecida: {texto!r}")


def _validar_tarefa(dados: Dict[str, str]) -> List[str]:
    problemas = []

    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        problemas.append("A descrição está vazia.")
    elif len(descricao) > MAX_DESCRICAO:
        problemas.append(f"A descrição tem mais de {MAX_DESCRICAO} caracteres.")

    try:
        interpretar_data(dados.get("vencimento", ""))
    except ValueError as erro:
        problemas.append(str(erro))

    return problemas


def _criar_tarefa(dados: Dict[str, str]) -> None:
    import tarefas_servico

    tarefas_servico.adicionar(
        (dados.get("descricao") or "").strip(),
        interpretar_data(dados.get("vencimento", "")) or None,
    )


def registar_incluidos() -> None:
    """Põe no registo os destinos que vêm com a aplicação."""
    motor.registar(
        "tarefas",
        campos=[
            Campo("descricao", "campo_descricao", obrigatorio=True, exemplo="Rever contrato"),
            Campo("vencimento", "campo_vencimento", exemplo="2030-01-31"),
        ],
        validar=_validar_tarefa,
        criar=_criar_tarefa,
        chave_titulo="destino_tarefas",
        permissao="tarefas.escrever",
    )
