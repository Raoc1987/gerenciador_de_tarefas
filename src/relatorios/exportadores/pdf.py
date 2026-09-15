"""Exportação para PDF, escrita à mão.

Um PDF simples é um conjunto de objetos numerados, um índice de posições
(*xref*) e um fluxo de conteúdo com operadores de texto. Escrevê-lo
diretamente evita trazer reportlab ou fpdf para o executável (ADR-0002).

Usa Helvetica e Helvetica-Bold — duas das 14 fontes que todo o leitor de PDF
tem, por isso não é preciso embutir nenhum ficheiro de fonte. O texto é
gravado em WinAnsi (cp1252), que cobre o português, o espanhol e o inglês; um
caractere fora dessa tabela é substituído em vez de corromper o arquivo.

Faz paginação, cabeçalho, tabelas com largura de coluna proporcional e
rodapé numerado. Não faz gráficos — o dashboard é o sítio para os ver.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

from relatorios.modelo import Indicadores, Lista, Relatorio, Tabela, texto_seguro

EXTENSAO = ".pdf"
DESCRICAO = "PDF"

# A4 em pontos (1 pt = 1/72 polegada).
LARGURA = 595.28
ALTURA = 841.89
MARGEM = 48.0

TAMANHO_TITULO = 17
TAMANHO_SUBTITULO = 10
TAMANHO_SECAO = 12
TAMANHO_TEXTO = 9.5
ENTRELINHA = 14.0

CINZENTO = (0.42, 0.47, 0.52)
PRETO = (0.15, 0.2, 0.25)
AZUL = (0.145, 0.388, 0.612)

#: Largura aproximada dos glifos da Helvetica, em fração do tamanho da fonte.
#: Não são as métricas exatas da fonte — chega para repartir colunas e partir
#: linhas sem embutir tabelas AFM.
_LARGURA_MEDIA = 0.52
_LARGURA_MEDIA_NEGRITO = 0.56
_ESTREITOS = set("iljtfrI.,:;'|!()[]-/ ")
_LARGOS = set("mwMW@%")


def _largura_do_glifo(caractere: str) -> float:
    """Largura relativa de um caractere, por classe."""
    if caractere in _ESTREITOS:
        return 0.30
    if caractere in _LARGOS:
        return 0.85
    if caractere.isdigit() or caractere.isupper():
        return 0.60
    return 0.52


def _largura(texto: str, tamanho: float, negrito: bool = False) -> float:
    """Largura estimada de um texto, em pontos."""
    escala = 1.08 if negrito else 1.0
    return sum(_largura_do_glifo(c) for c in texto) * tamanho * escala


def _para_winansi(texto: str) -> bytes:
    return texto.encode("cp1252", errors="replace")


def _escapar(texto: str) -> bytes:
    """Escapa parênteses e barras, que delimitam strings em PDF."""
    bruto = _para_winansi(texto)
    for alvo, substituto in ((b"\\", b"\\\\"), (b"(", b"\\("), (b")", b"\\)")):
        bruto = bruto.replace(alvo, substituto)
    return bruto


def _cortar(texto: str, largura_max: float, tamanho: float, negrito: bool = False) -> str:
    """Corta o texto com reticências quando não cabe na largura dada."""
    if _largura(texto, tamanho, negrito) <= largura_max:
        return texto
    cortado = texto
    while cortado and _largura(cortado + "…", tamanho, negrito) > largura_max:
        cortado = cortado[:-1]
    return cortado.rstrip() + "…" if cortado else "…"


def _quebrar(texto: str, largura_max: float, tamanho: float) -> List[str]:
    """Parte o texto em linhas que cabem na largura disponível."""
    palavras = texto.split()
    if not palavras:
        return [""]
    linhas: List[str] = []
    atual = palavras[0]
    for palavra in palavras[1:]:
        tentativa = f"{atual} {palavra}"
        if _largura(tentativa, tamanho) <= largura_max:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


@dataclass
class _Pagina:
    """Acumula os operadores de desenho de uma página."""

    operadores: List[bytes]

    def texto(
        self,
        conteudo: str,
        x: float,
        y: float,
        tamanho: float = TAMANHO_TEXTO,
        negrito: bool = False,
        cor: Tuple[float, float, float] = PRETO,
    ) -> None:
        fonte = b"/F2" if negrito else b"/F1"
        vermelho, verde, azul = cor
        self.operadores.append(
            b"BT " + fonte + b" %.2f Tf %.3f %.3f %.3f rg %.2f %.2f Td (" % (
                tamanho, vermelho, verde, azul, x, y
            )
            + _escapar(conteudo)
            + b") Tj ET\n"
        )

    def linha(self, x0: float, y0: float, x1: float, y1: float, cor=CINZENTO) -> None:
        vermelho, verde, azul = cor
        self.operadores.append(
            b"%.3f %.3f %.3f RG 0.6 w %.2f %.2f m %.2f %.2f l S\n"
            % (vermelho, verde, azul, x0, y0, x1, y1)
        )


class _Documento:
    """Constrói as páginas e serializa o PDF."""

    def __init__(self, rodape: str = "") -> None:
        self._paginas: List[_Pagina] = []
        self._rodape = rodape
        self._y = 0.0
        self.nova_pagina()

    # ---------------------------------------------------------- disposição

    @property
    def pagina(self) -> _Pagina:
        return self._paginas[-1]

    @property
    def y(self) -> float:
        return self._y

    def nova_pagina(self) -> None:
        self._paginas.append(_Pagina(operadores=[]))
        self._y = ALTURA - MARGEM

    def espaco(self, altura: float) -> None:
        """Garante espaço vertical, mudando de página se preciso."""
        if self._y - altura < MARGEM + 28:
            self.nova_pagina()

    def avancar(self, altura: float = ENTRELINHA) -> float:
        self._y -= altura
        return self._y

    # -------------------------------------------------------- serialização

    def _conteudo_da_pagina(self, indice: int) -> bytes:
        pagina = self._paginas[indice]
        rodape = _Pagina(operadores=[])
        numero = f"{indice + 1}/{len(self._paginas)}"
        rodape.texto(numero, LARGURA - MARGEM - 30, MARGEM - 16, 8, cor=CINZENTO)
        if self._rodape:
            rodape.texto(self._rodape, MARGEM, MARGEM - 16, 8, cor=CINZENTO)
        return zlib.compress(b"".join(pagina.operadores + rodape.operadores))

    def para_bytes(self) -> bytes:
        """Serializa o documento completo."""
        objetos: List[bytes] = []
        total_paginas = len(self._paginas)
        # 1 catálogo, 2 páginas, 3..n páginas, depois conteúdos e fontes.
        primeira_pagina = 3
        primeiro_conteudo = primeira_pagina + total_paginas
        fonte_normal = primeiro_conteudo + total_paginas
        fonte_negrito = fonte_normal + 1

        objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        filhos = " ".join(f"{primeira_pagina + i} 0 R" for i in range(total_paginas))
        objetos.append(
            f"<< /Type /Pages /Count {total_paginas} /Kids [{filhos}] >>".encode("ascii")
        )

        for indice in range(total_paginas):
            objetos.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {LARGURA:.2f} {ALTURA:.2f}] "
                    f"/Contents {primeiro_conteudo + indice} 0 R "
                    f"/Resources << /Font << /F1 {fonte_normal} 0 R "
                    f"/F2 {fonte_negrito} 0 R >> >> >>"
                ).encode("ascii")
            )

        for indice in range(total_paginas):
            fluxo = self._conteudo_da_pagina(indice)
            objetos.append(
                f"<< /Length {len(fluxo)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
                + fluxo
                + b"\nendstream"
            )

        for nome in (b"/Helvetica", b"/Helvetica-Bold"):
            objetos.append(
                b"<< /Type /Font /Subtype /Type1 /BaseFont "
                + nome
                + b" /Encoding /WinAnsiEncoding >>"
            )

        saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posicoes = []
        for numero, corpo in enumerate(objetos, start=1):
            posicoes.append(len(saida))
            saida += f"{numero} 0 obj\n".encode("ascii") + corpo + b"\nendobj\n"

        inicio_xref = len(saida)
        saida += f"xref\n0 {len(objetos) + 1}\n".encode("ascii")
        saida += b"0000000000 65535 f \n"
        for posicao in posicoes:
            saida += f"{posicao:010d} 00000 n \n".encode("ascii")
        saida += (
            f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
            f"startxref\n{inicio_xref}\n%%EOF\n"
        ).encode("ascii")
        return bytes(saida)


# ------------------------------------------------------------- composição


def _escrever_cabecalho(documento: _Documento, relatorio: Relatorio) -> None:
    documento.pagina.texto(relatorio.titulo, MARGEM, documento.y, TAMANHO_TITULO, True, AZUL)
    documento.avancar(20)

    detalhes = [d for d in (relatorio.subtitulo, relatorio.periodo) if d]
    if detalhes:
        documento.pagina.texto(
            " · ".join(detalhes), MARGEM, documento.y, TAMANHO_SUBTITULO, cor=CINZENTO
        )
        documento.avancar(14)

    documento.pagina.texto(
        relatorio.gerado_em.strftime("%d/%m/%Y %H:%M"),
        MARGEM,
        documento.y,
        TAMANHO_SUBTITULO,
        cor=CINZENTO,
    )
    documento.avancar(10)
    documento.pagina.linha(MARGEM, documento.y, LARGURA - MARGEM, documento.y)
    documento.avancar(18)


def _escrever_titulo_de_secao(documento: _Documento, titulo: str) -> None:
    documento.espaco(50)
    documento.pagina.texto(titulo, MARGEM, documento.y, TAMANHO_SECAO, True, AZUL)
    documento.avancar(16)


def _escrever_indicadores(documento: _Documento, secao: Indicadores) -> None:
    _escrever_titulo_de_secao(documento, secao.titulo)
    for rotulo, valor in secao.itens:
        documento.espaco(ENTRELINHA)
        documento.pagina.texto(texto_seguro(rotulo), MARGEM + 6, documento.y, cor=CINZENTO)
        documento.pagina.texto(
            texto_seguro(valor), MARGEM + 220, documento.y, TAMANHO_TEXTO, True
        )
        documento.avancar()
    documento.avancar(6)


def _escrever_lista(documento: _Documento, secao: Lista) -> None:
    _escrever_titulo_de_secao(documento, secao.titulo)
    largura_util = LARGURA - 2 * MARGEM - 16
    for item in secao.itens:
        for indice, linha in enumerate(_quebrar(texto_seguro(item), largura_util, TAMANHO_TEXTO)):
            documento.espaco(ENTRELINHA)
            prefixo = "• " if indice == 0 else "  "
            documento.pagina.texto(prefixo + linha, MARGEM + 6, documento.y)
            documento.avancar()
    documento.avancar(6)


def _larguras_das_colunas(secao: Tabela, largura_total: float) -> List[float]:
    """Reparte a largura pelas colunas conforme o que cada uma precisa.

    Mede a largura real do texto (não o número de caracteres) e garante um
    mínimo por coluna, para o cabeçalho de uma não espremer as outras.
    """
    necessarias = []
    for indice, coluna in enumerate(secao.colunas):
        maior = _largura(str(coluna), TAMANHO_TEXTO, negrito=True)
        for linha in secao.linhas:
            if indice < len(linha):
                maior = max(maior, _largura(texto_seguro(linha[indice]), TAMANHO_TEXTO))
        necessarias.append(maior + 10)  # espaço entre colunas

    total = sum(necessarias)
    if total <= largura_total:
        # Cabe tudo: a folga vai para a coluna mais larga (normalmente a
        # descrição), em vez de esticar as colunas de data.
        sobra = largura_total - total
        maior = necessarias.index(max(necessarias))
        necessarias[maior] += sobra
        return necessarias

    minimo = 42.0
    fixas = {i: minimo for i, l in enumerate(necessarias) if l <= minimo}
    restante = largura_total - minimo * len(fixas)
    soma_flexiveis = sum(l for i, l in enumerate(necessarias) if i not in fixas) or 1
    return [
        fixas.get(i, restante * l / soma_flexiveis) for i, l in enumerate(necessarias)
    ]


def _escrever_tabela(documento: _Documento, secao: Tabela) -> None:
    _escrever_titulo_de_secao(documento, secao.titulo)
    largura_total = LARGURA - 2 * MARGEM
    larguras = _larguras_das_colunas(secao, largura_total)

    def cabecalho() -> None:
        x = MARGEM
        for indice, coluna in enumerate(secao.colunas):
            documento.pagina.texto(
                _cortar(str(coluna), larguras[indice] - 6, TAMANHO_TEXTO, negrito=True),
                x,
                documento.y,
                TAMANHO_TEXTO,
                True,
            )
            x += larguras[indice]
        documento.avancar(4)
        documento.pagina.linha(MARGEM, documento.y, LARGURA - MARGEM, documento.y)
        documento.avancar(11)

    documento.espaco(60)
    cabecalho()

    for linha in secao.linhas:
        if documento.y - ENTRELINHA < MARGEM + 28:
            documento.nova_pagina()
            cabecalho()
        x = MARGEM
        for indice, valor in enumerate(linha):
            documento.pagina.texto(
                _cortar(texto_seguro(valor), larguras[indice] - 6, TAMANHO_TEXTO),
                x,
                documento.y,
            )
            x += larguras[indice]
        documento.avancar()
    documento.avancar(6)


def exportar(relatorio: Relatorio, destino: Path) -> Path:
    """Escreve o relatório em PDF e devolve o caminho."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    documento = _Documento(rodape=relatorio.rodape)
    _escrever_cabecalho(documento, relatorio)

    for secao in relatorio.secoes_com_conteudo():
        if isinstance(secao, Indicadores):
            _escrever_indicadores(documento, secao)
        elif isinstance(secao, Lista):
            _escrever_lista(documento, secao)
        elif isinstance(secao, Tabela):
            _escrever_tabela(documento, secao)

    destino.write_bytes(documento.para_bytes())
    return destino
