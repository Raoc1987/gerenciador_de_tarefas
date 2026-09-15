"""Leitura e extração segura de pacotes de plugin (``.zip``).

Um ``.zip`` de plugin é **conteúdo não confiável** até ser validado. Este
módulo trata dessa desconfiança e nada mais: não instala, não ativa e não
executa código do plugin.

Proteções implementadas:

* caminhos absolutos, letras de unidade e ``..`` são rejeitados;
* ligações simbólicas dentro do ZIP são rejeitadas;
* após a extração, cada arquivo é confirmado como estando dentro do destino;
* limites de quantidade de arquivos, tamanho total e rácio de compressão
  (defesa contra *zip bombs*);
* o manifesto é validado antes de qualquer arquivo ser escrito.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

from core.log import obter_logger
from core.plugin_api import (
    NOME_MANIFESTO,
    ManifestoInvalidoError,
    ManifestoPlugin,
    PacoteInvalidoError,
)

logger = obter_logger(__name__)

#: Número máximo de arquivos aceites num pacote.
MAX_ARQUIVOS = 2000
#: Tamanho máximo total após descompressão (50 MiB).
MAX_TAMANHO_TOTAL = 50 * 1024 * 1024
#: Tamanho máximo de um único arquivo (20 MiB).
MAX_TAMANHO_ARQUIVO = 20 * 1024 * 1024
#: Rácio máximo de compressão tolerado por arquivo (defesa contra zip bomb).
MAX_RACIO_COMPRESSAO = 200

#: Nomes que não fazem parte do conteúdo de um plugin: não entram num pacote
#: gerado a partir de uma pasta, nem contam para a sua impressão digital.
IGNORADOS = {"__pycache__", ".git", ".pytest_cache", ".DS_Store"}


@dataclass(frozen=True)
class PacotePlugin:
    """Um ``.zip`` já inspecionado e considerado seguro para extrair."""

    caminho: Path
    manifesto: ManifestoPlugin
    prefixo: str
    """Pasta raiz dentro do ZIP (``""`` quando os arquivos estão na raiz)."""

    membros: Tuple[str, ...]
    """Nomes dos membros a extrair, tal como aparecem no ZIP."""


def _normalizar(nome: str) -> str:
    """Converte separadores do Windows e remove prefixos ``./`` redundantes."""
    normalizado = nome.replace("\\", "/")
    while normalizado.startswith("./"):
        normalizado = normalizado[2:]
    return normalizado


def _validar_nome(nome: str) -> str:
    """Valida o nome de um membro do ZIP e devolve-o normalizado.

    Raises:
        PacoteInvalidoError: se o caminho tentar escapar do destino.
    """
    normalizado = _normalizar(nome)

    if not normalizado or normalizado in (".", "/"):
        raise PacoteInvalidoError(f"Entrada inválida no pacote: {nome!r}.")
    if normalizado.startswith("/"):
        raise PacoteInvalidoError(f"Caminho absoluto no pacote: {nome!r}.")
    if len(normalizado) > 1 and normalizado[1] == ":":
        raise PacoteInvalidoError(f"Caminho com unidade de disco no pacote: {nome!r}.")

    partes = PurePosixPath(normalizado).parts
    if any(parte == ".." for parte in partes):
        raise PacoteInvalidoError(f"Caminho com '..' no pacote: {nome!r}.")
    if any(parte.startswith("~") for parte in partes):
        raise PacoteInvalidoError(f"Caminho suspeito no pacote: {nome!r}.")
    return normalizado


def _e_link_simbolico(info: zipfile.ZipInfo) -> bool:
    modo = info.external_attr >> 16
    return stat.S_ISLNK(modo)


def _detectar_prefixo(nomes: List[str]) -> str:
    """Descobre a pasta raiz que contém o ``plugin.json``.

    Aceita tanto ``plugin.json`` na raiz do ZIP como ``<pasta>/plugin.json``.
    """
    if NOME_MANIFESTO in nomes:
        return ""

    candidatos = [
        nome[: -len(NOME_MANIFESTO) - 1]
        for nome in nomes
        if nome.endswith("/" + NOME_MANIFESTO)
    ]
    candidatos = [c for c in candidatos if "/" not in c]
    if not candidatos:
        raise PacoteInvalidoError(
            "O pacote não contém plugin.json na raiz nem numa única pasta de topo."
        )
    if len(candidatos) > 1:
        raise PacoteInvalidoError(
            "O pacote contém vários plugin.json: " + ", ".join(sorted(candidatos))
        )
    return candidatos[0]


def inspecionar(caminho_zip: Path) -> PacotePlugin:
    """Abre, valida e descreve um pacote de plugin — **sem** extrair nada.

    Raises:
        PacoteInvalidoError: ZIP corrompido, inseguro ou sem manifesto.
        ManifestoInvalidoError: manifesto presente mas inválido.
    """
    caminho_zip = Path(caminho_zip)
    if not caminho_zip.is_file():
        raise PacoteInvalidoError(f"Arquivo não encontrado: {caminho_zip}")

    try:
        with zipfile.ZipFile(caminho_zip) as pacote:
            if pacote.testzip() is not None:
                raise PacoteInvalidoError("O pacote está corrompido.")

            infos = pacote.infolist()
            if len(infos) > MAX_ARQUIVOS:
                raise PacoteInvalidoError(
                    f"O pacote contém arquivos a mais ({len(infos)} > {MAX_ARQUIVOS})."
                )

            total = 0
            nomes: List[str] = []
            membros: List[str] = []
            for info in infos:
                if _e_link_simbolico(info):
                    raise PacoteInvalidoError(
                        f"Ligações simbólicas não são permitidas: {info.filename!r}."
                    )
                normalizado = _validar_nome(info.filename)
                if info.is_dir():
                    continue
                if info.file_size > MAX_TAMANHO_ARQUIVO:
                    raise PacoteInvalidoError(
                        f"Arquivo demasiado grande no pacote: {normalizado!r}."
                    )
                if (
                    info.compress_size > 0
                    and info.file_size / info.compress_size > MAX_RACIO_COMPRESSAO
                ):
                    raise PacoteInvalidoError(
                        f"Rácio de compressão suspeito em {normalizado!r}."
                    )
                total += info.file_size
                if total > MAX_TAMANHO_TOTAL:
                    raise PacoteInvalidoError("O pacote descomprimido é demasiado grande.")
                nomes.append(normalizado)
                membros.append(info.filename)

            if not nomes:
                raise PacoteInvalidoError("O pacote está vazio.")

            prefixo = _detectar_prefixo(nomes)
            caminho_manifesto = f"{prefixo}/{NOME_MANIFESTO}" if prefixo else NOME_MANIFESTO
            indice = nomes.index(caminho_manifesto)

            try:
                dados = pacote.read(membros[indice]).decode("utf-8")
            except UnicodeDecodeError as erro:
                raise ManifestoInvalidoError(
                    "O plugin.json não está codificado em UTF-8."
                ) from erro

            try:
                manifesto = ManifestoPlugin.de_dicionario(json.loads(dados))
            except json.JSONDecodeError as erro:
                raise ManifestoInvalidoError(f"plugin.json inválido: {erro}") from erro

            relativo_entry = (
                f"{prefixo}/{manifesto.entry_point}" if prefixo else manifesto.entry_point
            )
            if _normalizar(relativo_entry) not in nomes:
                raise ManifestoInvalidoError(
                    f"O entry_point {manifesto.entry_point!r} não existe no pacote."
                )

    except zipfile.BadZipFile as erro:
        raise PacoteInvalidoError(f"Arquivo ZIP inválido: {erro}") from erro

    logger.info(
        "Pacote inspecionado: %s -> %s v%s (%d arquivos)",
        caminho_zip.name,
        manifesto.id,
        manifesto.versao,
        len(membros),
    )
    return PacotePlugin(
        caminho=caminho_zip,
        manifesto=manifesto,
        prefixo=prefixo,
        membros=tuple(membros),
    )


def extrair(pacote: PacotePlugin, destino: Path) -> Path:
    """Extrai um pacote já inspecionado para ``destino`` (que é criado).

    Cada arquivo é escrito manualmente, depois de se confirmar que o caminho
    final continua dentro de ``destino``.

    Returns:
        O próprio ``destino``, contendo já o ``plugin.json`` na raiz.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    raiz = destino.resolve()
    prefixo = f"{pacote.prefixo}/" if pacote.prefixo else ""

    with zipfile.ZipFile(pacote.caminho) as zf:
        for membro in pacote.membros:
            normalizado = _validar_nome(membro)
            if prefixo:
                if not normalizado.startswith(prefixo):
                    # Arquivo fora da pasta do plugin: ignorado de propósito.
                    logger.debug("Ignorado (fora da raiz do plugin): %s", normalizado)
                    continue
                relativo = normalizado[len(prefixo):]
            else:
                relativo = normalizado
            if not relativo:
                continue

            alvo = (raiz / relativo).resolve()
            if not _dentro(alvo, raiz):
                raise PacoteInvalidoError(
                    f"O pacote tentou escrever fora do destino: {membro!r}."
                )

            alvo.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(membro) as origem, open(alvo, "wb") as saida:
                saida.write(origem.read())

    if not (destino / NOME_MANIFESTO).is_file():
        raise PacoteInvalidoError("A extração não produziu um plugin.json.")
    return destino


def _dentro(alvo: Path, raiz: Path) -> bool:
    """``True`` se ``alvo`` está dentro de ``raiz``."""
    try:
        return os.path.commonpath([str(alvo), str(raiz)]) == str(raiz)
    except ValueError:
        # Unidades diferentes no Windows.
        return False


def validar_instalacao(pasta: Path, esperado: Optional[ManifestoPlugin] = None) -> ManifestoPlugin:
    """Revalida uma pasta já extraída antes de a promover a plugin instalado.

    Raises:
        ManifestoInvalidoError: manifesto ausente, inválido, divergente do
            esperado, ou ``entry_point`` inexistente.
    """
    manifesto = ManifestoPlugin.ler_de_pasta(pasta)
    if esperado is not None and (
        manifesto.id != esperado.id or manifesto.versao != esperado.versao
    ):
        raise ManifestoInvalidoError(
            "O conteúdo extraído não corresponde ao manifesto inspecionado."
        )
    if not (Path(pasta) / manifesto.entry_point).is_file():
        raise ManifestoInvalidoError(
            f"entry_point inexistente após a extração: {manifesto.entry_point}"
        )
    return manifesto


def impressao_da_pasta(pasta: Path) -> str:
    """Impressão digital do conteúdo instalado de um plugin.

    Serve uma pergunta só, e é preciso que a saiba responder com certeza:
    **o que está no disco é exatamente o que a aplicação lá pôs?** É isso que
    distingue "a versão embutida é mais recente, pode substituir" de "alguém
    mexeu nisto à mão, não se toca" (ADR-0006).

    Entra o caminho relativo de cada arquivo e o seu conteúdo — renomear um
    arquivo muda a impressão tanto como editá-lo. Ficheiros gerados
    (``__pycache__`` e companhia) ficam de fora: um plugin que corre escreve
    ``.pyc`` dentro da sua própria pasta, e isso não é uma modificação do
    utilizador.
    """
    pasta = Path(pasta)
    digestor = hashlib.sha256()
    for arquivo in sorted(pasta.rglob("*"), key=lambda p: p.relative_to(pasta).as_posix()):
        relativo = arquivo.relative_to(pasta)
        if any(parte in IGNORADOS for parte in relativo.parts):
            continue
        if not arquivo.is_file():
            continue
        digestor.update(relativo.as_posix().encode("utf-8"))
        digestor.update(b"\0")
        digestor.update(arquivo.read_bytes())
        digestor.update(b"\0")
    return digestor.hexdigest()
