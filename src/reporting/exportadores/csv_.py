"""Exportação para CSV.

Um CSV é uma grelha só, e um relatório tem várias secções. A convenção usada
aqui — título da secção numa linha, a secção a seguir, linha em branco entre
secções — mantém o arquivo legível tanto por pessoas como pelo Excel.

Escrito com ``utf-8-sig``: sem o BOM, o Excel em Windows abre acentos trocados.
"""

from __future__ import annotations

import csv
from pathlib import Path

from reporting.modelo import Relatorio, como_linhas

EXTENSAO = ".csv"
DESCRICAO = "CSV"


def exportar(relatorio: Relatorio, destino: Path) -> Path:
    """Escreve o relatório em CSV e devolve o caminho."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    with open(destino, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow([relatorio.titulo])
        if relatorio.subtitulo:
            escritor.writerow([relatorio.subtitulo])
        if relatorio.periodo:
            escritor.writerow([relatorio.periodo])
        escritor.writerow([relatorio.gerado_em.strftime("%d/%m/%Y %H:%M")])

        for secao in relatorio.secoes_com_conteudo():
            escritor.writerow([])
            escritor.writerow([secao.titulo])
            for linha in como_linhas(secao):
                escritor.writerow(list(linha))

    return destino
