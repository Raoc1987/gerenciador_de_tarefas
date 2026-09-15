"""Exportação para XLSX, escrita à mão.

Um ``.xlsx`` é um ZIP com alguns XML lá dentro. Escrevê-lo diretamente custa ~150
linhas e evita trazer o openpyxl (e as suas dependências) para dentro do
executável — ver ADR-0002. O openpyxl é usado, isso sim, **nos testes**, para
confirmar que o que sai daqui é mesmo um ficheiro que o Excel lê.

Simplificações deliberadas, suficientes para relatórios:

* uma folha por secção;
* texto em ``inlineStr`` (dispensa a tabela de strings partilhadas);
* números detetados e gravados como números, para o Excel os somar;
* uma linha de cabeçalho a negrito nas tabelas.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import List, Sequence
from xml.sax.saxutils import escape

from relatorios.modelo import Indicadores, Relatorio, Tabela, como_linhas

EXTENSAO = ".xlsx"
DESCRICAO = "Excel (XLSX)"

#: Caracteres que o Excel proíbe em nomes de folha.
_PROIBIDOS_NA_FOLHA = re.compile(r"[\[\]:*?/\\]")
_NUMERO = re.compile(r"^-?\d+(?:[.,]\d+)?$")

_TIPOS_DE_CONTEUDO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{folhas}
</Types>"""

_RELS_RAIZ = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _nome_de_folha(titulo: str, usados: List[str]) -> str:
    """Nome de folha aceite pelo Excel: sem caracteres proibidos, até 31 chars."""
    nome = _PROIBIDOS_NA_FOLHA.sub("-", titulo).strip() or "Folha"
    nome = nome[:31]
    base = nome
    contador = 2
    while nome.lower() in (u.lower() for u in usados):
        sufixo = f" ({contador})"
        nome = base[: 31 - len(sufixo)] + sufixo
        contador += 1
    usados.append(nome)
    return nome


def _referencia(coluna: int, linha: int) -> str:
    """``(0, 0)`` -> ``A1``."""
    letras = ""
    coluna += 1
    while coluna:
        coluna, resto = divmod(coluna - 1, 26)
        letras = chr(65 + resto) + letras
    return f"{letras}{linha + 1}"


def _e_numero(texto: str) -> bool:
    """Se o texto deve ir para a folha como número e não como texto.

    Um valor com zero à esquerda (``007``) é um código, não um número: gravá-lo
    como número perderia os zeros.
    """
    limpo = texto.strip()
    if not _NUMERO.match(limpo):
        return False
    digitos = limpo.lstrip("-")
    return not (len(digitos) > 1 and digitos[0] == "0" and digitos[1] not in ".,")


def _celula(valor: str, coluna: int, linha: int, negrito: bool = False) -> str:
    referencia = _referencia(coluna, linha)
    estilo = ' s="1"' if negrito else ""
    texto = "" if valor is None else str(valor)

    if _e_numero(texto):
        return f'<c r="{referencia}"{estilo}><v>{texto.strip().replace(",", ".")}</v></c>'

    return (
        f'<c r="{referencia}"{estilo} t="inlineStr"><is><t xml:space="preserve">'
        f"{escape(texto)}</t></is></c>"
    )


def _folha(linhas: Sequence[Sequence[str]], linha_de_cabecalho: bool) -> str:
    partes = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for indice, linha in enumerate(linhas):
        celulas = "".join(
            _celula(valor, coluna, indice, negrito=linha_de_cabecalho and indice == 0)
            for coluna, valor in enumerate(linha)
        )
        partes.append(f'<row r="{indice + 1}">{celulas}</row>')
    partes.append("</sheetData></worksheet>")
    return "".join(partes)


def exportar(relatorio: Relatorio, destino: Path) -> Path:
    """Escreve o relatório em XLSX e devolve o caminho."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    cabecalho: List[List[str]] = [[relatorio.titulo]]
    if relatorio.subtitulo:
        cabecalho.append([relatorio.subtitulo])
    if relatorio.periodo:
        cabecalho.append([relatorio.periodo])
    cabecalho.append([relatorio.gerado_em.strftime("%d/%m/%Y %H:%M")])

    folhas = []
    usados: List[str] = []
    secoes = relatorio.secoes_com_conteudo()

    if secoes:
        primeira = secoes[0]
        linhas = list(cabecalho) + [[]] + [list(l) for l in como_linhas(primeira)]
        folhas.append((_nome_de_folha(primeira.titulo, usados), linhas, False))
        for secao in secoes[1:]:
            folhas.append(
                (
                    _nome_de_folha(secao.titulo, usados),
                    [list(l) for l in como_linhas(secao)],
                    isinstance(secao, Tabela),
                )
            )
    else:
        folhas.append((_nome_de_folha(relatorio.titulo, usados), cabecalho, False))

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        overrides = "\n".join(
            f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(len(folhas))
        )
        pacote.writestr("[Content_Types].xml", _TIPOS_DE_CONTEUDO.format(folhas=overrides))
        pacote.writestr("_rels/.rels", _RELS_RAIZ)

        entradas = "".join(
            f'<sheet name="{escape(nome)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
            for i, (nome, _, _) in enumerate(folhas)
        )
        pacote.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{entradas}</sheets></workbook>",
        )

        relacoes = "".join(
            f'<Relationship Id="rId{i + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i + 1}.xml"/>'
            for i in range(len(folhas))
        )
        relacoes += (
            f'<Relationship Id="rId{len(folhas) + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
        )
        pacote.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relacoes}</Relationships>",
        )
        pacote.writestr("xl/styles.xml", _ESTILOS)

        for indice, (_, linhas, cabecalho_negrito) in enumerate(folhas):
            pacote.writestr(
                f"xl/worksheets/sheet{indice + 1}.xml", _folha(linhas, cabecalho_negrito)
            )

    return destino
