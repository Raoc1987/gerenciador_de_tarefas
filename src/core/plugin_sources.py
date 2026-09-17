"""Fontes de plugins — de onde os pacotes podem vir.

O :class:`~core.plugin_manager.PluginManager` instala sempre a partir de um
``.zip`` local já validado. Este módulo abstrai *como* esse ``.zip`` aparece,
para que uma futura Plugin Store online seja mais uma fonte e não uma
reescrita do gerenciador:

* :class:`FonteZipsLocais` — uma pasta com pacotes ``.zip``;
* :class:`FontePastasLocais` — plugins que acompanham a aplicação (embutidos);
* :class:`FonteRemota` — esqueleto da loja online (ainda sem servidor).

Uma fonte só é responsável por **listar** o que oferece e por **entregar um
``.zip`` local**. Validação, segurança e instalação continuam a ser do
gerenciador, iguais para todas as fontes.
"""

from __future__ import annotations

import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.log import obter_logger
from core.plugin_api import (
    NOME_MANIFESTO,
    ManifestoInvalidoError,
    ManifestoPlugin,
    PacoteInvalidoError,
)
from core.paths import diretorio_plugins_temp
from core.plugin_package import IGNORADOS
from core.version import APP_VERSION

logger = obter_logger(__name__)

#: Um plugin que veio dentro da aplicação. A aplicação responde por ele: as
#: correções que publica têm de lhe chegar (ADR-0006).
PROVENIENCIA_EMBUTIDO = "embutido"

#: Um plugin que o utilizador instalou. É dele; a aplicação não lhe mexe.
PROVENIENCIA_UTILIZADOR = "utilizador"


@dataclass(frozen=True)
class PluginDisponivel:
    """Um plugin oferecido por uma fonte, ainda não instalado."""

    manifesto: ManifestoPlugin
    origem: str
    """Descrição legível de onde veio (pasta, URL...)."""

    referencia: str
    """Como pedir o pacote à fonte (caminho local, URL, id do catálogo...)."""

    @property
    def id(self) -> str:
        """Identificador do plugin."""
        return self.manifesto.id

    @property
    def versao(self) -> str:
        """Versão oferecida."""
        return self.manifesto.versao

    def compativel(self, app_version: str = APP_VERSION) -> bool:
        """Se esta versão serve para a aplicação indicada."""
        return self.manifesto.compativel_com(app_version)


class FontePlugins(ABC):
    """Contrato comum a todas as fontes de plugins."""

    nome: str = "fonte"

    proveniencia: str = PROVENIENCIA_UTILIZADOR
    """De quem fica a ser o plugin que esta fonte entrega.

    Por omissão, do utilizador: instalar de uma pasta de downloads ou da loja
    é uma decisão dele, e a aplicação não volta a essa pasta por sua conta.
    Não confundir com :attr:`PluginDisponivel.origem`, que é apenas a frase
    que diz de que pasta ou URL o pacote veio.
    """

    def disponivel(self) -> bool:
        """Se a fonte pode ser consultada agora (pasta existe, rede acessível...)."""
        return True

    @abstractmethod
    def listar(self) -> List[PluginDisponivel]:
        """Plugins oferecidos pela fonte. Nunca levanta: falhas viram lista vazia."""

    @abstractmethod
    def obter_pacote(self, disponivel: PluginDisponivel) -> Path:
        """Devolve o caminho de um ``.zip`` local pronto a instalar.

        Raises:
            PacoteInvalidoError: se o pacote não puder ser obtido.
        """

    def procurar(self, plugin_id: str) -> Optional[PluginDisponivel]:
        """O plugin com este id, se a fonte o oferecer."""
        for disponivel in self.listar():
            if disponivel.id == plugin_id:
                return disponivel
        return None


class FonteZipsLocais(FontePlugins):
    """Pasta do disco com pacotes ``.zip`` (ex.: uma pasta de downloads)."""

    nome = "zips locais"

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)

    def disponivel(self) -> bool:
        """Se a pasta existe."""
        return self.pasta.is_dir()

    def listar(self) -> List[PluginDisponivel]:
        """Inspeciona cada ``.zip`` da pasta, ignorando os inválidos."""
        from core import plugin_package

        if not self.disponivel():
            return []

        encontrados: List[PluginDisponivel] = []
        for arquivo in sorted(self.pasta.glob("*.zip")):
            try:
                pacote = plugin_package.inspecionar(arquivo)
            except (PacoteInvalidoError, ManifestoInvalidoError) as erro:
                logger.debug("Pacote ignorado em %s: %s", arquivo.name, erro)
                continue
            encontrados.append(
                PluginDisponivel(
                    manifesto=pacote.manifesto,
                    origem=str(self.pasta),
                    referencia=str(arquivo),
                )
            )
        return encontrados

    def obter_pacote(self, disponivel: PluginDisponivel) -> Path:
        """O ``.zip`` já está no disco: devolve o próprio caminho."""
        caminho = Path(disponivel.referencia)
        if not caminho.is_file():
            raise PacoteInvalidoError(f"Pacote inexistente: {caminho}")
        return caminho


class FontePastasLocais(FontePlugins):
    """Plugins em forma de pasta — tipicamente os que acompanham a aplicação.

    Como o gerenciador instala sempre a partir de ``.zip``, cada pasta é
    empacotada num ``.zip`` temporário antes da instalação. Assim os plugins
    embutidos passam exatamente pelas mesmas validações que os externos.
    """

    nome = "plugins embutidos"
    proveniencia = PROVENIENCIA_EMBUTIDO

    def __init__(self, pasta: Path) -> None:
        self.pasta = Path(pasta)

    def disponivel(self) -> bool:
        """Se a pasta de plugins embutidos existe."""
        return self.pasta.is_dir()

    def listar(self) -> List[PluginDisponivel]:
        """Lê o manifesto de cada subpasta, ignorando as inválidas."""
        if not self.disponivel():
            return []

        encontrados: List[PluginDisponivel] = []
        for subpasta in sorted(p for p in self.pasta.iterdir() if p.is_dir()):
            if subpasta.name.startswith((".", "_")):
                continue
            try:
                manifesto = ManifestoPlugin.ler_de_pasta(subpasta)
            except ManifestoInvalidoError as erro:
                logger.warning("Plugin embutido inválido em %s: %s", subpasta.name, erro)
                continue
            encontrados.append(
                PluginDisponivel(
                    manifesto=manifesto,
                    origem=str(self.pasta),
                    referencia=str(subpasta),
                )
            )
        return encontrados

    def obter_pacote(self, disponivel: PluginDisponivel) -> Path:
        """Empacota a pasta do plugin num ``.zip`` temporário."""
        origem = Path(disponivel.referencia)
        if not (origem / NOME_MANIFESTO).is_file():
            raise PacoteInvalidoError(f"Plugin embutido sem manifesto: {origem}")

        destino = diretorio_plugins_temp() / f"{disponivel.id}-{disponivel.versao}.zip"
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
            for arquivo in sorted(origem.rglob("*")):
                relativo = arquivo.relative_to(origem)
                if any(parte in IGNORADOS for parte in relativo.parts):
                    continue
                if arquivo.is_file():
                    pacote.write(arquivo, (Path(disponivel.id) / relativo).as_posix())
        logger.debug("Plugin embutido %s empacotado em %s", disponivel.id, destino)
        return destino


class FonteRemota(FontePlugins):
    """Esqueleto da futura Plugin Store online.

    A forma final está definida — catálogo com metadados, versões e
    compatibilidade, seguido de download para um ``.zip`` local — mas ainda
    não existe servidor. A classe existe para garantir que o gerenciador não
    assume que os plugins só podem vir de arquivos locais: quando a loja
    existir, basta implementar :meth:`listar` e :meth:`obter_pacote`.
    """

    nome = "loja online"

    def __init__(self, url_catalogo: str, app_version: str = APP_VERSION) -> None:
        self.url_catalogo = url_catalogo
        self.app_version = app_version

    def disponivel(self) -> bool:
        """Ainda não: não há servidor configurado."""
        return False

    def listar(self) -> List[PluginDisponivel]:
        """Sem servidor, o catálogo é vazio (e não é um erro)."""
        logger.info("Loja de plugins ainda não disponível (%s).", self.url_catalogo)
        return []

    def obter_pacote(self, disponivel: PluginDisponivel) -> Path:
        """Ainda não implementado — o download será validado como qualquer zip."""
        raise NotImplementedError(
            "A loja de plugins online ainda não está disponível."
        )
