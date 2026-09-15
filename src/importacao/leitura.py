"""Ler um ficheiro como ele realmente vem.

É aqui que uma importação se decide. Um leitor que só aceite UTF-8 separado
por vírgulas falha no primeiro ficheiro exportado de um Excel português — que
vem em ``cp1252``, separado por ponto e vírgula — e a pessoa conclui que o
programa não serve, o que é uma conclusão razoável a partir do que viu.

Por isso:

* a **codificação** é descoberta por tentativa, da mais provável para a mais
  permissiva, e há sempre uma que aceita tudo;
* o **separador** é descoberto pelo conteúdo, não assumido;
* o **XLSX** é lido à mão, como já é escrito à mão (ADR-0002): a aplicação
  continua sem dependências em execução.

Nada aqui sabe o que é uma tarefa. Devolve uma tabela de texto.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from xml.etree import ElementTree

from core.log import obter_logger

logger = obter_logger(__name__)

#: Codificações tentadas por ordem.
#:
#: ``utf-8-sig`` antes de ``utf-8`` para comer o BOM que o Excel escreve;
#: ``cp1252`` porque é o que sai de um Excel em português; ``latin-1`` no fim
#: porque aceita qualquer sequência de bytes — e um ficheiro mal codificado
#: lido com acentos trocados ainda é melhor do que um erro na cara de quem só
#: queria importar a sua lista.
CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

#: Separadores considerados, por ordem de frequência no mundo real.
SEPARADORES = (";", ",", "\t", "|")

#: Limite de linhas lidas. Uma importação de secretária não são milhões de
#: linhas, e um ficheiro enorme não pode encher a memória sem aviso.
MAX_LINHAS = 20_000

#: Limite do XML **descomprimido** dentro de um XLSX, por ficheiro.
#:
#: Um ZIP de 10 KB pode esconder gigabytes. É a mesma defesa que os pacotes de
#: plugins já usam, e pela mesma razão: o ficheiro vem de fora.
MAX_XML = 50 * 1024 * 1024


class ImportacaoError(Exception):
    """Não foi possível ler o ficheiro."""

    chave_mensagem = "importacao_erro"


class FicheiroIlegivelError(ImportacaoError):
    """O ficheiro não abre, ou não é de um formato conhecido."""

    chave_mensagem = "importacao_ilegivel"


class FicheiroVazioError(ImportacaoError):
    """O ficheiro não tem linhas para importar."""

    chave_mensagem = "importacao_vazio"


class FicheiroPerigosoError(ImportacaoError):
    """O ficheiro traz construções que não se devem processar."""

    chave_mensagem = "importacao_perigoso"


@dataclass(frozen=True)
class Tabela:
    """O conteúdo de um ficheiro, como texto."""

    cabecalho: List[str] = field(default_factory=list)
    linhas: List[List[str]] = field(default_factory=list)
    codificacao: str = ""
    separador: str = ""

    def __len__(self) -> int:
        return len(self.linhas)

    def como_dicionarios(self) -> List[Dict[str, str]]:
        """Cada linha com o cabeçalho por chave."""
        return [
            {
                coluna: (linha[i] if i < len(linha) else "")
                for i, coluna in enumerate(self.cabecalho)
            }
            for linha in self.linhas
        ]


# ------------------------------------------------------------------- texto


def descodificar(bruto: bytes) -> tuple:
    """Devolve ``(texto, codificação)``, tentando as codificações por ordem.

    Raises:
        FicheiroIlegivelError: se nenhuma servir — o que só acontece se
            ``latin-1`` também falhar, e esse aceita tudo.
    """
    for codificacao in CODIFICACOES:
        try:
            return bruto.decode(codificacao), codificacao
        except UnicodeDecodeError:
            continue
    raise FicheiroIlegivelError(  # pragma: no cover - latin-1 aceita tudo
        "Não foi possível interpretar o texto do ficheiro."
    )


def descobrir_separador(texto: str) -> str:
    """Descobre o separador olhando para o conteúdo.

    O ``csv.Sniffer`` acerta quase sempre, mas engana-se em ficheiros de uma
    coluna só e em texto com muita pontuação. Quando falha, conta-se qual dos
    candidatos aparece o mesmo número de vezes em todas as primeiras linhas —
    um separador a sério é regular; uma vírgula dentro de uma frase não é.
    """
    amostra = "\n".join(texto.splitlines()[:20])
    if not amostra.strip():
        return ","

    try:
        return csv.Sniffer().sniff(amostra, delimiters="".join(SEPARADORES)).delimiter
    except csv.Error:
        pass

    linhas = [l for l in amostra.splitlines() if l.strip()][:10]
    melhor, melhor_contagem = ",", 0
    for candidato in SEPARADORES:
        contagens = {l.count(candidato) for l in linhas}
        if len(contagens) == 1 and contagens != {0}:
            contagem = contagens.pop()
            if contagem > melhor_contagem:
                melhor, melhor_contagem = candidato, contagem
    return melhor


def ler_csv(bruto: bytes) -> Tabela:
    """Lê um CSV, descobrindo codificação e separador.

    Raises:
        FicheiroVazioError: se não houver cabeçalho e pelo menos uma linha.
    """
    texto, codificacao = descodificar(bruto)
    separador = descobrir_separador(texto)

    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=separador)
    todas = []
    for numero, linha in enumerate(leitor):
        if numero > MAX_LINHAS:
            logger.warning("Ficheiro truncado em %d linhas.", MAX_LINHAS)
            break
        # Linhas totalmente vazias aparecem no fim de quase todos os ficheiros
        # exportados; contá-las como dados daria "20 importadas, 3 com erro".
        if any(celula.strip() for celula in linha):
            todas.append([celula.strip() for celula in linha])

    if not todas:
        raise FicheiroVazioError("O ficheiro não tem linhas.")
    if len(todas) < 2:
        raise FicheiroVazioError("O ficheiro tem cabeçalho mas nenhuma linha de dados.")

    return Tabela(todas[0], todas[1:], codificacao, separador)


# -------------------------------------------------------------------- xlsx

_ESPACO = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _xml_seguro(bruto: bytes, origem: str):
    """Analisa XML vindo de fora, recusando o que não devia lá estar.

    A biblioteca padrão expande entidades declaradas no documento, o que torna
    um ficheiro de 1 KB capaz de consumir toda a memória da máquina — o
    ataque conhecido por *billion laughs*. A solução habitual é a biblioteca
    ``defusedxml``, que é uma dependência externa, e esta aplicação não tem
    nenhuma em execução (ADR-0002).

    A defesa possível sem dependências é recusar **antes de analisar**: uma
    folha de cálculo gerada por qualquer programa a sério não traz ``DOCTYPE``
    nem declarações de entidades. Um ficheiro que traga não é uma folha de
    cálculo: é uma tentativa.
    """
    if len(bruto) > MAX_XML:
        raise FicheiroPerigosoError(
            f"{origem} é grande demais depois de descomprimido."
        )

    cabeca = bruto[:4096].lower()
    for suspeito in (b"<!doctype", b"<!entity"):
        if suspeito in cabeca:
            logger.error("Recusado XML com %r em %s.", suspeito.decode(), origem)
            raise FicheiroPerigosoError(
                "O ficheiro traz declarações de entidades XML, que não são "
                "usadas por folhas de cálculo e podem esgotar a memória."
            )

    return ElementTree.fromstring(bruto)


def _texto_da_celula(celula, partilhadas: Sequence[str]) -> str:
    """O texto de uma célula, venha ele de onde vier.

    Três origens possíveis num XLSX: a tabela de strings partilhadas (o mais
    comum no Excel), texto embutido, ou um valor direto. Ignorar qualquer uma
    delas dá colunas vazias sem explicação.
    """
    tipo = celula.get("t", "")
    if tipo == "s":
        valor = celula.find(f"{_ESPACO}v")
        if valor is None or valor.text is None:
            return ""
        try:
            return partilhadas[int(valor.text)]
        except (ValueError, IndexError):  # pragma: no cover - ficheiro estranho
            return ""
    if tipo == "inlineStr":
        return "".join(no.text or "" for no in celula.iter(f"{_ESPACO}t"))
    valor = celula.find(f"{_ESPACO}v")
    return (valor.text or "") if valor is not None else ""


def _coluna_de(referencia: str) -> int:
    """A coluna (0-based) de uma referência como ``"C7"``.

    O Excel **omite** as células vazias. Sem ler a referência, uma linha com
    um buraco no meio ficava com os valores todos deslocados para a esquerda —
    e a importação metia a data na coluna do nome sem ninguém reparar.
    """
    letras = "".join(c for c in referencia if c.isalpha()).upper()
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return max(indice - 1, 0)


def ler_xlsx(caminho: Path) -> Tabela:
    """Lê a primeira folha de um XLSX, sem dependências externas."""
    try:
        with zipfile.ZipFile(caminho) as pacote:
            nomes = pacote.namelist()
            partilhadas: List[str] = []
            if "xl/sharedStrings.xml" in nomes:
                raiz = _xml_seguro(
                    pacote.read("xl/sharedStrings.xml"), "sharedStrings.xml"
                )
                partilhadas = [
                    "".join(no.text or "" for no in item.iter(f"{_ESPACO}t"))
                    for item in raiz.findall(f"{_ESPACO}si")
                ]

            folhas = sorted(n for n in nomes if n.startswith("xl/worksheets/sheet"))
            if not folhas:
                raise FicheiroIlegivelError("O ficheiro não tem folhas.")
            raiz = _xml_seguro(pacote.read(folhas[0]), folhas[0])
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as erro:
        raise FicheiroIlegivelError(f"Não é um ficheiro XLSX válido: {erro}") from erro

    todas: List[List[str]] = []
    for numero, linha in enumerate(raiz.iter(f"{_ESPACO}row")):
        if numero > MAX_LINHAS:
            logger.warning("Ficheiro truncado em %d linhas.", MAX_LINHAS)
            break
        celulas: Dict[int, str] = {}
        for celula in linha.findall(f"{_ESPACO}c"):
            indice = _coluna_de(celula.get("r", ""))
            celulas[indice] = _texto_da_celula(celula, partilhadas).strip()
        if not celulas:
            continue
        largura = max(celulas) + 1
        valores = [celulas.get(i, "") for i in range(largura)]
        if any(valores):
            todas.append(valores)

    if len(todas) < 2:
        raise FicheiroVazioError("A folha não tem dados para importar.")

    largura = max(len(linha) for linha in todas)
    normalizadas = [linha + [""] * (largura - len(linha)) for linha in todas]
    return Tabela(normalizadas[0], normalizadas[1:], "xlsx", "")


# ------------------------------------------------------------------ entrada


def ler(caminho) -> Tabela:
    """Lê um ficheiro CSV ou XLSX.

    O formato vem da extensão, mas um ficheiro que comece pela assinatura de
    um ZIP é tratado como XLSX mesmo que se chame ``.csv`` — as pessoas
    renomeiam ficheiros, e recusar por causa do nome é recusar por nada.

    Raises:
        FicheiroIlegivelError: ficheiro inexistente ou de formato desconhecido.
        FicheiroVazioError: sem linhas de dados.
    """
    caminho = Path(caminho)
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        raise FicheiroIlegivelError(f"Não foi possível abrir {caminho.name}: {erro}") from erro

    if bruto[:2] == b"PK":
        return ler_xlsx(caminho)
    if caminho.suffix.lower() in (".csv", ".txt", ".tsv", ""):
        return ler_csv(bruto)
    raise FicheiroIlegivelError(
        f"Não sei ler ficheiros {caminho.suffix!r}. Use CSV ou XLSX."
    )
