"""Gerenciamento do ciclo de vida dos plugins.

O :class:`PluginManager` conhece a *infraestrutura* dos plugins (onde estão,
como se validam, como se carregam) mas nunca a lógica interna de cada um.

Princípio central: **um plugin defeituoso não derruba a aplicação**. Todas as
operações devolvem um :class:`ResultadoOperacao` e registam o erro no log; o
plugin fica marcado como ``EstadoPlugin.ERRO`` e os restantes continuam a
funcionar normalmente.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional

from core import config as config_app
from core import plugin_package
from core.log import obter_logger
from core.paths import (
    diretorio_dados_plugin,
    diretorio_plugins_instalados,
    diretorio_plugins_temp,
)
from core.plugin_api import (
    CarregamentoPluginError,
    ContextoPlugin,
    EstadoPlugin,
    InterfaceAnfitria,
    ManifestoInvalidoError,
    ManifestoPlugin,
    Plugin,
    PluginError,
    ServicoTarefas,
    encontrar_classe_plugin,
)
from core.version import APP_VERSION, comparar_versoes

logger = obter_logger(__name__)

#: Prefixo dos módulos importados dinamicamente, para não colidir com o resto.
PREFIXO_MODULO = "gdt_plugin_"


# ------------------------------------------------------------------ resultado


@dataclass
class ResultadoOperacao:
    """Resultado de uma operação sobre um plugin.

    A interface traduz ``chave_mensagem`` para mostrar algo compreensível; os
    ``detalhes`` técnicos vão para o log e para a área de detalhe do diálogo.
    """

    sucesso: bool
    chave_mensagem: str
    plugin_id: Optional[str] = None
    detalhes: str = ""

    def __bool__(self) -> bool:
        return self.sucesso


# -------------------------------------------------------------------- registo


@dataclass
class RegistroPlugin:
    """Estado de um plugin conhecido pelo gerenciador."""

    id: str
    pasta: Path
    manifesto: Optional[ManifestoPlugin] = None
    estado: EstadoPlugin = EstadoPlugin.DESCOBERTO
    erro: str = ""
    instancia: Optional[Plugin] = None
    modulo: Optional[ModuleType] = None
    habilitado: bool = False

    @property
    def nome(self) -> str:
        """Nome apresentável (cai para o id quando o manifesto é inválido)."""
        return self.manifesto.nome if self.manifesto else self.id

    @property
    def versao(self) -> str:
        """Versão do plugin, ou ``"?"`` se o manifesto não pôde ser lido."""
        return self.manifesto.versao if self.manifesto else "?"

    @property
    def descricao(self) -> str:
        """Descrição do plugin."""
        return self.manifesto.descricao if self.manifesto else ""

    @property
    def ativo(self) -> bool:
        """``True`` se o plugin está a correr."""
        return self.estado == EstadoPlugin.ATIVO


class RegistroEstado:
    """Porta de persistência do estado ativado/desativado dos plugins.

    A implementação por omissão guarda em memória (útil em testes); a
    aplicação usa a implementação sobre o banco de dados
    (:class:`core.plugin_registry.RegistroEstadoBanco`).
    """

    def __init__(self) -> None:
        self._estado: Dict[str, bool] = {}

    def habilitados(self) -> Dict[str, bool]:
        """Mapa ``plugin_id -> habilitado``."""
        return dict(self._estado)

    def registrar(self, manifesto: ManifestoPlugin, habilitado: bool = False) -> None:
        """Regista (ou atualiza) um plugin instalado."""
        self._estado.setdefault(manifesto.id, habilitado)

    def definir_habilitado(self, plugin_id: str, habilitado: bool) -> None:
        """Persiste a intenção do utilizador de ter o plugin ativo ou não."""
        self._estado[plugin_id] = habilitado

    def esquecer(self, plugin_id: str) -> None:
        """Remove o plugin do registo (após desinstalação)."""
        self._estado.pop(plugin_id, None)


# ------------------------------------------------------------------ gerenciador


class PluginManager:
    """Descobre, valida, carrega, ativa e remove plugins.

    Args:
        diretorio: pasta dos plugins instalados (por omissão, a do utilizador).
        app_version: versão da aplicação usada nas verificações de compatibilidade.
        registro: persistência do estado ativado/desativado.
        ui: pontos de extensão da interface, entregues aos plugins.
        tarefas: fachada de acesso às tarefas, entregue aos plugins.
    """

    def __init__(
        self,
        diretorio: Optional[Path] = None,
        app_version: str = APP_VERSION,
        registro: Optional[RegistroEstado] = None,
        ui: Optional[InterfaceAnfitria] = None,
        tarefas: Optional[ServicoTarefas] = None,
    ) -> None:
        self._diretorio = Path(diretorio) if diretorio else diretorio_plugins_instalados()
        self.app_version = app_version
        self._registro = registro if registro is not None else RegistroEstado()
        self._ui = ui
        self._tarefas = tarefas
        self._plugins: Dict[str, RegistroPlugin] = {}

    # ------------------------------------------------------------ propriedades

    @property
    def diretorio(self) -> Path:
        """Pasta onde os plugins instalados residem."""
        self._diretorio.mkdir(parents=True, exist_ok=True)
        return self._diretorio

    @property
    def registro(self) -> RegistroEstado:
        """Persistência do estado dos plugins."""
        return self._registro

    def listar(self) -> List[RegistroPlugin]:
        """Plugins conhecidos, ordenados por nome."""
        return sorted(self._plugins.values(), key=lambda r: r.nome.lower())

    def obter(self, plugin_id: str) -> Optional[RegistroPlugin]:
        """Registo de um plugin, ou ``None`` se desconhecido."""
        return self._plugins.get(plugin_id)

    # ------------------------------------------------------------- DISCOVER

    def descobrir(self) -> List[RegistroPlugin]:
        """Varre o diretório de plugins e (re)valida cada um.

        Nunca levanta: pastas inválidas ficam registadas com o estado
        ``INVALIDO`` ou ``INCOMPATIVEL`` e uma mensagem de erro legível.
        """
        if not self._diretorio.exists():
            logger.info("Diretório de plugins inexistente: %s", self._diretorio)
            return self.listar()

        habilitados = self._registro.habilitados()
        encontrados = set()

        for pasta in sorted(p for p in self._diretorio.iterdir() if p.is_dir()):
            if pasta.name.startswith((".", "_")):
                continue
            registro = self._plugins.get(pasta.name)
            if registro is not None and registro.estado in (
                EstadoPlugin.CARREGADO,
                EstadoPlugin.ATIVO,
            ):
                # Já em execução: não mexer.
                encontrados.add(pasta.name)
                continue

            registro = RegistroPlugin(id=pasta.name, pasta=pasta)
            try:
                manifesto = ManifestoPlugin.ler_de_pasta(pasta)
            except ManifestoInvalidoError as erro:
                registro.estado = EstadoPlugin.INVALIDO
                registro.erro = str(erro)
                logger.warning("Plugin inválido em %s: %s", pasta.name, erro)
                self._plugins[pasta.name] = registro
                encontrados.add(pasta.name)
                continue

            registro.manifesto = manifesto
            if manifesto.id != pasta.name:
                registro.estado = EstadoPlugin.INVALIDO
                registro.erro = (
                    f"O id do manifesto ({manifesto.id!r}) não corresponde à pasta "
                    f"({pasta.name!r})."
                )
                logger.warning("%s", registro.erro)
                self._plugins[pasta.name] = registro
                encontrados.add(pasta.name)
                continue

            if not (pasta / manifesto.entry_point).is_file():
                registro.estado = EstadoPlugin.INVALIDO
                registro.erro = f"entry_point inexistente: {manifesto.entry_point}"
                logger.warning("Plugin %s: %s", manifesto.id, registro.erro)
                self._plugins[pasta.name] = registro
                encontrados.add(pasta.name)
                continue

            if not manifesto.compativel_com(self.app_version):
                registro.estado = EstadoPlugin.INCOMPATIVEL
                registro.erro = (
                    f"Requer a aplicação {manifesto.min_app_version} ou superior "
                    f"(atual: {self.app_version})."
                )
                logger.warning("Plugin %s incompatível: %s", manifesto.id, registro.erro)
            else:
                registro.estado = EstadoPlugin.INSTALADO

            registro.habilitado = habilitados.get(manifesto.id, False)
            self._registro.registrar(manifesto, registro.habilitado)
            self._plugins[manifesto.id] = registro
            encontrados.add(manifesto.id)
            logger.debug("Plugin descoberto: %s v%s", manifesto.id, manifesto.versao)

        # Esquece plugins cuja pasta desapareceu e que não estão em execução.
        for plugin_id in list(self._plugins):
            if plugin_id not in encontrados and not self._plugins[plugin_id].ativo:
                self._plugins.pop(plugin_id)

        logger.info("Descoberta concluída: %d plugin(s).", len(self._plugins))
        return self.listar()

    # ------------------------------------------------------------------ LOAD

    def carregar(self, plugin_id: str) -> ResultadoOperacao:
        """Importa o módulo do plugin e instancia a sua classe."""
        registro = self._plugins.get(plugin_id)
        if registro is None:
            return ResultadoOperacao(False, "plugin_nao_encontrado", plugin_id)
        if registro.estado in (EstadoPlugin.CARREGADO, EstadoPlugin.ATIVO):
            return ResultadoOperacao(True, "plugin_carregado", plugin_id)
        if registro.manifesto is None or registro.estado == EstadoPlugin.INVALIDO:
            return ResultadoOperacao(False, "plugin_invalido", plugin_id, registro.erro)
        if registro.estado == EstadoPlugin.INCOMPATIVEL:
            return ResultadoOperacao(False, "plugin_incompativel", plugin_id, registro.erro)

        try:
            modulo = self._importar(registro)
            classe = encontrar_classe_plugin(modulo)
            contexto = self._criar_contexto(registro)
            instancia = classe(contexto)
            if not isinstance(instancia, Plugin):
                raise CarregamentoPluginError(
                    "A classe indicada não é uma subclasse de Plugin."
                )
            instancia.inicializar()
        except Exception as erro:  # isolamento: qualquer falha do plugin
            self._marcar_erro(registro, erro, "carregar")
            self._descartar_modulo(plugin_id)
            return ResultadoOperacao(False, "plugin_erro_carregar", plugin_id, str(erro))

        registro.modulo = modulo
        registro.instancia = instancia
        registro.estado = EstadoPlugin.CARREGADO
        registro.erro = ""
        logger.info("Plugin carregado: %s v%s", registro.id, registro.versao)
        return ResultadoOperacao(True, "plugin_carregado", plugin_id)

    def _importar(self, registro: RegistroPlugin) -> ModuleType:
        assert registro.manifesto is not None
        caminho = registro.pasta / registro.manifesto.entry_point
        nome_modulo = PREFIXO_MODULO + registro.id
        especificacao = importlib.util.spec_from_file_location(nome_modulo, caminho)
        if especificacao is None or especificacao.loader is None:
            raise CarregamentoPluginError(f"Não foi possível importar {caminho}.")

        modulo = importlib.util.module_from_spec(especificacao)
        sys.modules[nome_modulo] = modulo
        # Permite que o plugin importe módulos vizinhos da sua própria pasta.
        pasta = str(registro.pasta)
        adicionado = pasta not in sys.path
        if adicionado:
            sys.path.insert(0, pasta)
        try:
            especificacao.loader.exec_module(modulo)
        except Exception:
            sys.modules.pop(nome_modulo, None)
            raise
        finally:
            if adicionado:
                try:
                    sys.path.remove(pasta)
                except ValueError:  # pragma: no cover - defensivo
                    pass
        return modulo

    def _criar_contexto(self, registro: RegistroPlugin) -> ContextoPlugin:
        assert registro.manifesto is not None
        from language_manager import carregar_texto

        return ContextoPlugin(
            manifesto=registro.manifesto,
            app_version=self.app_version,
            diretorio_plugin=registro.pasta,
            diretorio_dados=diretorio_dados_plugin(registro.id),
            logger=obter_logger(f"plugin.{registro.id}"),
            tarefas=self._tarefas,
            ui=self._ui,
            _ler_config=config_app.carregar_config_plugin,
            _gravar_config=config_app.guardar_config_plugin,
            _traduzir=carregar_texto,
        )

    # -------------------------------------------------------------- ACTIVATE

    def ativar(self, plugin_id: str, persistir: bool = True) -> ResultadoOperacao:
        """Carrega (se preciso) e ativa o plugin."""
        registro = self._plugins.get(plugin_id)
        if registro is None:
            return ResultadoOperacao(False, "plugin_nao_encontrado", plugin_id)
        if registro.ativo:
            return ResultadoOperacao(True, "plugin_ativo", plugin_id)

        if registro.estado != EstadoPlugin.CARREGADO:
            resultado = self.carregar(plugin_id)
            if not resultado:
                return resultado

        assert registro.instancia is not None
        try:
            registro.instancia.ativar()
        except Exception as erro:
            self._marcar_erro(registro, erro, "ativar")
            # Tenta deixar o plugin num estado limpo.
            self._finalizar_silenciosamente(registro)
            self._descartar_modulo(plugin_id)
            registro.instancia = None
            registro.modulo = None
            if persistir:
                self._registro.definir_habilitado(plugin_id, False)
                registro.habilitado = False
            return ResultadoOperacao(False, "plugin_erro_ativar", plugin_id, str(erro))

        registro.estado = EstadoPlugin.ATIVO
        registro.erro = ""
        if persistir:
            self._registro.definir_habilitado(plugin_id, True)
        registro.habilitado = True
        logger.info("Plugin ativado: %s v%s", registro.id, registro.versao)
        return ResultadoOperacao(True, "plugin_ativo", plugin_id)

    def desativar(self, plugin_id: str, persistir: bool = True) -> ResultadoOperacao:
        """Desativa o plugin, mantendo-o instalado."""
        registro = self._plugins.get(plugin_id)
        if registro is None:
            return ResultadoOperacao(False, "plugin_nao_encontrado", plugin_id)
        if not registro.ativo:
            if persistir:
                self._registro.definir_habilitado(plugin_id, False)
            registro.habilitado = False
            return ResultadoOperacao(True, "plugin_inativo", plugin_id)

        detalhes = ""
        try:
            assert registro.instancia is not None
            registro.instancia.desativar()
        except Exception as erro:
            # A desativação falhou, mas o utilizador pediu para desligar:
            # regista o erro e continua a desligar assim mesmo.
            detalhes = str(erro)
            logger.exception("Falha ao desativar o plugin %s.", plugin_id)

        if self._ui is not None:
            try:
                self._ui.remover_abas(plugin_id)
            except Exception:  # pragma: no cover - defensivo
                logger.exception("Falha ao remover a UI do plugin %s.", plugin_id)

        registro.estado = EstadoPlugin.CARREGADO
        if persistir:
            self._registro.definir_habilitado(plugin_id, False)
        registro.habilitado = False
        logger.info("Plugin desativado: %s", plugin_id)
        return ResultadoOperacao(True, "plugin_inativo", plugin_id, detalhes)

    # ---------------------------------------------------------------- UNLOAD

    def descarregar(self, plugin_id: str) -> ResultadoOperacao:
        """Desativa e liberta completamente o plugin da memória."""
        registro = self._plugins.get(plugin_id)
        if registro is None:
            return ResultadoOperacao(False, "plugin_nao_encontrado", plugin_id)

        if registro.ativo:
            self.desativar(plugin_id, persistir=False)
        self._finalizar_silenciosamente(registro)
        self._descartar_modulo(plugin_id)
        registro.instancia = None
        registro.modulo = None
        if registro.estado not in (EstadoPlugin.INVALIDO, EstadoPlugin.INCOMPATIVEL, EstadoPlugin.ERRO):
            registro.estado = EstadoPlugin.INSTALADO
        logger.info("Plugin descarregado: %s", plugin_id)
        return ResultadoOperacao(True, "plugin_descarregado", plugin_id)

    # ------------------------------------------------------------- ARRANQUE

    def ativar_habilitados(self) -> List[ResultadoOperacao]:
        """Ativa, no arranque, os plugins que o utilizador deixou ligados.

        Cada plugin é tratado isoladamente: um erro num deles não impede os
        restantes de arrancar nem interrompe a aplicação.
        """
        resultados: List[ResultadoOperacao] = []
        for registro in self.listar():
            if not registro.habilitado:
                continue
            if registro.estado in (EstadoPlugin.INVALIDO, EstadoPlugin.INCOMPATIVEL):
                chave = (
                    "plugin_invalido"
                    if registro.estado == EstadoPlugin.INVALIDO
                    else "plugin_incompativel"
                )
                resultados.append(
                    ResultadoOperacao(False, chave, registro.id, registro.erro)
                )
                continue
            resultados.append(self.ativar(registro.id, persistir=False))
        falhas = [r for r in resultados if not r.sucesso]
        if falhas:
            logger.warning(
                "%d plugin(s) não arrancaram; a aplicação continua a funcionar.",
                len(falhas),
            )
        return resultados

    def desativar_todos(self) -> None:
        """Encerra todos os plugins ativos (no fecho da aplicação)."""
        for registro in list(self._plugins.values()):
            if registro.instancia is not None:
                self.descarregar(registro.id)

    # --------------------------------------------------- INSTALL / UPDATE

    def instalar_zip(
        self,
        caminho_zip: Path,
        permitir_atualizacao: bool = True,
    ) -> ResultadoOperacao:
        """Instala (ou atualiza) um plugin a partir de um arquivo ``.zip``.

        O ZIP é sempre tratado como não confiável: é inspecionado e validado
        antes de qualquer arquivo ser escrito, extraído para uma área
        temporária, revalidado, e só então promovido a plugin instalado.
        Nenhum código do plugin é executado durante a instalação.

        Em atualização, a versão anterior é guardada e reposta se algo falhar,
        de modo a nunca deixar um plugin meio-atualizado. A configuração e os
        dados do plugin vivem fora da sua pasta e são preservados.
        """
        caminho_zip = Path(caminho_zip)
        try:
            pacote = plugin_package.inspecionar(caminho_zip)
            pacote.manifesto.verificar_compatibilidade(self.app_version)
        except PluginError as erro:
            logger.warning("Instalação recusada (%s): %s", caminho_zip.name, erro)
            return ResultadoOperacao(False, erro.chave_mensagem, None, str(erro))

        manifesto = pacote.manifesto
        destino = self.diretorio / manifesto.id
        existente = self._plugins.get(manifesto.id)
        versao_anterior = existente.versao if existente and existente.manifesto else None
        atualizacao = destino.exists()

        if atualizacao and versao_anterior:
            comparacao = comparar_versoes(manifesto.versao, versao_anterior)
            if comparacao <= 0 or not permitir_atualizacao:
                chave = "plugin_ja_instalado"
                detalhes = (
                    f"Versão instalada: {versao_anterior}; "
                    f"versão do pacote: {manifesto.versao}."
                )
                logger.info("Instalação recusada para %s: %s", manifesto.id, detalhes)
                return ResultadoOperacao(False, chave, manifesto.id, detalhes)

        temporario = Path(tempfile.mkdtemp(prefix=f"{manifesto.id}_", dir=diretorio_plugins_temp()))
        backup: Optional[Path] = None
        try:
            extraido = plugin_package.extrair(pacote, temporario / "conteudo")
            plugin_package.validar_instalacao(extraido, manifesto)

            if atualizacao:
                self.descarregar(manifesto.id)
                backup = temporario / "backup"
                shutil.move(str(destino), str(backup))

            shutil.move(str(extraido), str(destino))
            plugin_package.validar_instalacao(destino, manifesto)
        except Exception as erro:
            logger.exception("Falha ao instalar o plugin %s.", manifesto.id)
            # Reposição: se a nova versão chegou a entrar, é descartada.
            if backup is not None and backup.exists():
                if destino.exists():
                    shutil.rmtree(destino, ignore_errors=True)
                try:
                    shutil.move(str(backup), str(destino))
                    logger.info("Versão anterior de %s reposta.", manifesto.id)
                except OSError:  # pragma: no cover - defensivo
                    logger.exception("Falha ao repor a versão anterior de %s.", manifesto.id)
            chave = erro.chave_mensagem if isinstance(erro, PluginError) else "plugin_erro_instalar"
            self.descobrir()
            return ResultadoOperacao(False, chave, manifesto.id, str(erro))
        finally:
            shutil.rmtree(temporario, ignore_errors=True)

        self._registro.registrar(manifesto, habilitado=False)
        self.descobrir()
        chave = "plugin_atualizado" if atualizacao else "plugin_instalado"
        logger.info(
            "Plugin %s: %s v%s%s",
            "atualizado" if atualizacao else "instalado",
            manifesto.id,
            manifesto.versao,
            f" (anterior: {versao_anterior})" if versao_anterior else "",
        )
        return ResultadoOperacao(True, chave, manifesto.id)

    def inspecionar_zip(self, caminho_zip: Path) -> ManifestoPlugin:
        """Lê o manifesto de um ``.zip`` sem instalar nada.

        Útil para a interface confirmar com o utilizador antes de instalar.

        Raises:
            PluginError: se o pacote for inválido ou inseguro.
        """
        return plugin_package.inspecionar(Path(caminho_zip)).manifesto

    # ---------------------------------------------------------------- REMOVE

    def remover(self, plugin_id: str, remover_dados: bool = False) -> ResultadoOperacao:
        """Desativa, descarrega e apaga os arquivos de um plugin.

        Args:
            remover_dados: também apaga a configuração e a pasta de dados
                privada do plugin. Por omissão, os dados são preservados.
        """
        registro = self._plugins.get(plugin_id)
        if registro is None:
            return ResultadoOperacao(False, "plugin_nao_encontrado", plugin_id)

        self.descarregar(plugin_id)
        pasta = registro.pasta
        try:
            if pasta.exists():
                shutil.rmtree(pasta)
        except OSError as erro:
            logger.exception("Falha ao remover a pasta do plugin %s.", plugin_id)
            return ResultadoOperacao(False, "plugin_erro_remover", plugin_id, str(erro))

        if remover_dados:
            config_app.remover_config_plugin(plugin_id)
            dados = diretorio_dados_plugin(plugin_id)
            try:
                shutil.rmtree(dados, ignore_errors=True)
            except OSError:  # pragma: no cover - defensivo
                logger.exception("Falha ao remover os dados do plugin %s.", plugin_id)

        self._registro.esquecer(plugin_id)
        self._plugins.pop(plugin_id, None)
        logger.info("Plugin removido: %s (dados removidos: %s)", plugin_id, remover_dados)
        return ResultadoOperacao(True, "plugin_removido", plugin_id)

    # ---------------------------------------------------------------- apoio

    def versao_instalada(self, plugin_id: str) -> Optional[str]:
        """Versão do plugin instalado, se existir."""
        registro = self._plugins.get(plugin_id)
        return registro.versao if registro and registro.manifesto else None

    def _marcar_erro(self, registro: RegistroPlugin, erro: Exception, acao: str) -> None:
        registro.estado = EstadoPlugin.ERRO
        registro.erro = str(erro)
        logger.exception("Falha ao %s o plugin %s.", acao, registro.id)

    def _finalizar_silenciosamente(self, registro: RegistroPlugin) -> None:
        if registro.instancia is None:
            return
        try:
            registro.instancia.finalizar()
        except Exception:
            logger.exception("Falha ao finalizar o plugin %s.", registro.id)

    @staticmethod
    def _descartar_modulo(plugin_id: str) -> None:
        sys.modules.pop(PREFIXO_MODULO + plugin_id, None)
