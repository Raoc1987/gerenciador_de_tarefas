"""Contrato público entre a aplicação e os plugins.

Este módulo define **tudo** o que um plugin precisa de conhecer:

* :class:`ManifestoPlugin` — o ``plugin.json`` validado;
* :class:`ContextoPlugin` — os serviços que a aplicação oferece ao plugin;
* :class:`Plugin` — a classe base que todo o plugin deve estender;
* as exceções e os estados do ciclo de vida.

Ciclo de vida::

    DISCOVER -> VALIDATE -> INSTALL -> REGISTER -> LOAD -> ACTIVATE
             -> RUN -> DEACTIVATE -> UNLOAD

Um plugin **não** importa `banco_de_dados`, `gui` ou `core.plugin_manager`
diretamente: tudo o que lhe é permitido usar chega pelo :class:`ContextoPlugin`.
Isto mantém o acoplamento baixo e permite mudar a aplicação sem partir plugins.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
)

from core.permissoes import Permissao
from core.plugin_dados import ArmazenamentoPlugin
from core.version import (
    APP_VERSION,
    VersaoInvalidaError,
    parse_version,
    versao_compativel,
)

NOME_MANIFESTO = "plugin.json"

_PADRAO_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")

# Versão do próprio contrato de plugins. Incrementar apenas em mudanças
# incompatíveis da API oferecida aos plugins.
PLUGIN_API_VERSION = "1.0"

#: Permissões que um plugin **nunca** pode pedir.
#:
#: Gerir plugins, contas ou o sistema não são capacidades de negócio: são as
#: chaves da casa. Um plugin que instala plugins deixa de ter fronteira, e um
#: que cria contas concede-se a si próprio o que quiser. Estas ficam do lado
#: de cá, com o utilizador.
PERMISSOES_NEGADAS_A_PLUGINS = frozenset(
    {
        Permissao.PLUGINS_GERIR,
        Permissao.UTILIZADORES_GERIR,
        Permissao.SISTEMA_ADMIN,
    }
)

#: O que um plugin pode declarar no ``plugin.json``.
PERMISSOES_CONCEDIVEIS = frozenset(Permissao) - PERMISSOES_NEGADAS_A_PLUGINS


# --------------------------------------------------------------------- erros


class PluginError(Exception):
    """Erro base do sistema de plugins."""

    #: Chave de tradução usada pela interface para uma mensagem amigável.
    chave_mensagem = "plugin_erro_generico"


class ManifestoInvalidoError(PluginError):
    """O ``plugin.json`` está ausente, malformado ou incompleto."""

    chave_mensagem = "plugin_invalido"


class PluginIncompativelError(PluginError):
    """O plugin exige uma versão da aplicação diferente da instalada."""

    chave_mensagem = "plugin_incompativel"


class PacoteInvalidoError(PluginError):
    """O arquivo ``.zip`` do plugin é inválido ou inseguro."""

    chave_mensagem = "plugin_pacote_invalido"


class PluginJaInstaladoError(PluginError):
    """Já existe um plugin instalado com o mesmo identificador e versão."""

    chave_mensagem = "plugin_ja_instalado"


class CarregamentoPluginError(PluginError):
    """O módulo do plugin não pôde ser importado ou não expõe um Plugin."""

    chave_mensagem = "plugin_erro_carregar"


class AtivacaoPluginError(PluginError):
    """O plugin falhou ao ativar ou desativar."""

    chave_mensagem = "plugin_erro_ativar"


class PermissaoNaoDeclaradaError(PluginError):
    """O plugin tentou fazer algo que não pediu no manifesto.

    Não é o mesmo que :class:`~core.permissoes.PermissaoNegadaError`: aqui a
    sessão até podia ter o direito — foi o plugin que não o declarou.
    """

    chave_mensagem = "plugin_permissao_nao_declarada"

    def __init__(self, permissao: Permissao) -> None:
        super().__init__(
            f"O plugin não declarou a permissão {permissao.value!r} no manifesto."
        )
        self.permissao = permissao


# --------------------------------------------------------------------- estado


class EstadoPlugin(str, Enum):
    """Estado de um plugin no ciclo de vida."""

    DESCOBERTO = "descoberto"
    INVALIDO = "invalido"
    INCOMPATIVEL = "incompativel"
    INSTALADO = "instalado"
    CARREGADO = "carregado"
    ATIVO = "ativo"
    ERRO = "erro"

    @property
    def utilizavel(self) -> bool:
        """``True`` quando o plugin pode ser ativado pelo utilizador."""
        return self in (EstadoPlugin.INSTALADO, EstadoPlugin.CARREGADO, EstadoPlugin.ATIVO)


# ------------------------------------------------------------------ manifesto


@dataclass(frozen=True)
class ManifestoPlugin:
    """Representação validada do ``plugin.json``."""

    id: str
    nome: str
    versao: str
    entry_point: str
    min_app_version: str = "1.0.0"
    max_app_version: Optional[str] = None
    autor: str = ""
    descricao: str = ""
    permissoes: FrozenSet[Permissao] = frozenset()
    permissoes_proprias: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    """Permissões que este módulo traz, e os papéis que as recebem.

    Um módulo de negócio tem permissões do seu domínio que o núcleo não pode
    conhecer. Só pode defini-las no seu próprio espaço de nomes, por isso o
    pior que consegue conceder é acesso aos **seus** dados.
    """
    """O que o plugin declarou precisar. Declarar não concede: limita.

    O plugin recebe a interseção disto com o que a sessão pode fazer.
    """
    extras: Dict[str, Any] = field(default_factory=dict, compare=False)

    _OBRIGATORIOS = ("id", "name", "version", "entry_point", "min_app_version")

    # ------------------------------------------------------------ construção

    @classmethod
    def de_dicionario(cls, dados: Any) -> "ManifestoPlugin":
        """Valida e converte o conteúdo de um ``plugin.json``.

        Raises:
            ManifestoInvalidoError: se faltar um campo, o tipo estiver errado,
                o ``id`` não for um identificador aceitável ou a versão não for
                semântica.
        """
        if not isinstance(dados, dict):
            raise ManifestoInvalidoError("O manifesto deve ser um objeto JSON.")

        for campo in cls._OBRIGATORIOS:
            if campo not in dados:
                raise ManifestoInvalidoError(f"Campo obrigatório ausente: {campo!r}.")
            if not isinstance(dados[campo], str) or not dados[campo].strip():
                raise ManifestoInvalidoError(
                    f"Campo {campo!r} deve ser uma string não vazia."
                )

        identificador = dados["id"].strip()
        if not _PADRAO_ID.match(identificador):
            raise ManifestoInvalidoError(
                "O id deve ter 2 a 64 caracteres, apenas minúsculas, dígitos, "
                f"'_' ou '-', começando por letra ou dígito (recebido: {identificador!r})."
            )

        for campo in ("version", "min_app_version"):
            try:
                parse_version(dados[campo])
            except VersaoInvalidaError as erro:
                raise ManifestoInvalidoError(str(erro)) from erro

        maxima = dados.get("max_app_version")
        if maxima is not None:
            if not isinstance(maxima, str):
                raise ManifestoInvalidoError("max_app_version deve ser uma string.")
            try:
                parse_version(maxima)
            except VersaoInvalidaError as erro:
                raise ManifestoInvalidoError(str(erro)) from erro

        entry_point = dados["entry_point"].strip()
        if not cls._entry_point_seguro(entry_point):
            raise ManifestoInvalidoError(
                f"entry_point inválido: {entry_point!r}. Deve ser um arquivo .py "
                "relativo à pasta do plugin, sem '..' e sem caminho absoluto."
            )

        for campo in ("author", "description"):
            if campo in dados and not isinstance(dados[campo], str):
                raise ManifestoInvalidoError(f"Campo {campo!r} deve ser uma string.")

        permissoes = cls._permissoes_pedidas(dados.get("permissions", []))
        proprias = cls._permissoes_proprias(
            identificador, dados.get("provides_permissions", {})
        )

        conhecidos = {
            "id", "name", "version", "entry_point", "min_app_version",
            "max_app_version", "author", "description", "permissions",
            "provides_permissions",
        }
        extras = {c: v for c, v in dados.items() if c not in conhecidos}

        return cls(
            id=identificador,
            nome=dados["name"].strip(),
            versao=dados["version"].strip(),
            entry_point=entry_point,
            min_app_version=dados["min_app_version"].strip(),
            max_app_version=maxima.strip() if maxima else None,
            autor=str(dados.get("author", "")).strip(),
            descricao=str(dados.get("description", "")).strip(),
            permissoes=permissoes,
            permissoes_proprias=proprias,
            extras=extras,
        )

    @staticmethod
    def _permissoes_pedidas(pedidas: Any) -> FrozenSet[Permissao]:
        """Valida o campo ``permissions`` do manifesto.

        Raises:
            ManifestoInvalidoError: se não for uma lista de nomes conhecidos,
                ou se o plugin pedir uma permissão que nenhum plugin pode ter.
        """
        if not isinstance(pedidas, list):
            raise ManifestoInvalidoError("permissions deve ser uma lista.")

        permissoes = set()
        for nome in pedidas:
            if not isinstance(nome, str):
                raise ManifestoInvalidoError("permissions deve conter apenas strings.")
            try:
                permissao = Permissao(nome.strip())
            except ValueError as erro:
                conhecidas = ", ".join(sorted(p.value for p in PERMISSOES_CONCEDIVEIS))
                raise ManifestoInvalidoError(
                    f"Permissão desconhecida: {nome!r}. Disponíveis: {conhecidas}."
                ) from erro
            if permissao not in PERMISSOES_CONCEDIVEIS:
                raise ManifestoInvalidoError(
                    f"Nenhum plugin pode pedir {permissao.value!r}."
                )
            permissoes.add(permissao)
        return frozenset(permissoes)

    @staticmethod
    def _permissoes_proprias(
        plugin_id: str, dados: Any
    ) -> Dict[str, FrozenSet[str]]:
        """Valida o campo ``provides_permissions``.

        Raises:
            ManifestoInvalidoError: se não for ``{permissão: [papéis]}``, se a
                permissão sair do espaço de nomes do módulo, ou se colidir com
                uma do núcleo.
        """
        if not isinstance(dados, dict):
            raise ManifestoInvalidoError("provides_permissions deve ser um objeto.")

        prefixo = f"{plugin_id}."
        do_nucleo = {p.value for p in Permissao}
        resultado: Dict[str, FrozenSet[str]] = {}

        for nome, papeis in dados.items():
            if not isinstance(nome, str) or not nome.startswith(prefixo):
                raise ManifestoInvalidoError(
                    f"O módulo {plugin_id!r} não pode definir {nome!r}: as suas "
                    f"permissões começam por {prefixo!r}."
                )
            if nome in do_nucleo:
                raise ManifestoInvalidoError(f"{nome!r} é uma permissão do núcleo.")
            if not isinstance(papeis, list) or not all(
                isinstance(papel, str) for papel in papeis
            ):
                raise ManifestoInvalidoError(
                    f"Os papéis de {nome!r} devem ser uma lista de nomes."
                )
            resultado[nome] = frozenset(papel.strip() for papel in papeis)
        return resultado

    @staticmethod
    def _entry_point_seguro(entry_point: str) -> bool:
        if not entry_point.endswith(".py"):
            return False
        if entry_point.startswith(("/", "\\")) or ":" in entry_point:
            return False
        partes = re.split(r"[\\/]+", entry_point)
        return all(parte not in ("", ".", "..") for parte in partes)

    @classmethod
    def ler(cls, caminho: Path) -> "ManifestoPlugin":
        """Lê e valida um ``plugin.json`` do disco.

        Raises:
            ManifestoInvalidoError: se o arquivo não existir ou não for JSON válido.
        """
        try:
            texto = Path(caminho).read_text(encoding="utf-8")
        except FileNotFoundError as erro:
            raise ManifestoInvalidoError(f"Manifesto não encontrado: {caminho}") from erro
        except OSError as erro:
            raise ManifestoInvalidoError(f"Manifesto ilegível: {erro}") from erro

        try:
            dados = json.loads(texto)
        except json.JSONDecodeError as erro:
            raise ManifestoInvalidoError(f"JSON inválido em {caminho}: {erro}") from erro

        return cls.de_dicionario(dados)

    @classmethod
    def ler_de_pasta(cls, pasta: Path) -> "ManifestoPlugin":
        """Lê o ``plugin.json`` dentro de ``pasta``."""
        return cls.ler(Path(pasta) / NOME_MANIFESTO)

    # ---------------------------------------------------------------- apoio

    def para_dicionario(self) -> Dict[str, Any]:
        """Converte de volta ao formato do ``plugin.json``."""
        dados: Dict[str, Any] = {
            "id": self.id,
            "name": self.nome,
            "version": self.versao,
            "author": self.autor,
            "description": self.descricao,
            "min_app_version": self.min_app_version,
            "entry_point": self.entry_point,
        }
        if self.permissoes:
            dados["permissions"] = sorted(p.value for p in self.permissoes)
        if self.permissoes_proprias:
            dados["provides_permissions"] = {
                nome: sorted(papeis) for nome, papeis in sorted(self.permissoes_proprias.items())
            }
        if self.max_app_version:
            dados["max_app_version"] = self.max_app_version
        dados.update(self.extras)
        return dados

    def compativel_com(self, app_version: str = APP_VERSION) -> bool:
        """Indica se o plugin suporta a versão da aplicação indicada."""
        return versao_compativel(self.min_app_version, self.max_app_version, app_version)

    def verificar_compatibilidade(self, app_version: str = APP_VERSION) -> None:
        """Levanta :class:`PluginIncompativelError` se a versão não servir."""
        if not self.compativel_com(app_version):
            limite = (
                f" e no máximo {self.max_app_version}" if self.max_app_version else ""
            )
            raise PluginIncompativelError(
                f"O plugin {self.nome} requer a aplicação na versão "
                f"{self.min_app_version} ou superior{limite}. "
                f"Versão atual: {app_version}."
            )


# ------------------------------------------------------- serviços do anfitrião


class ServicoTarefas(Protocol):
    """Acesso às tarefas concedido aos plugins (fachada estreita do banco)."""

    def listar(self, incluir_concluidas: bool = True) -> List[tuple]: ...

    def listar_por_data(self, data_iso: str) -> List[tuple]: ...

    def adicionar(self, descricao: str, data_vencimento: Optional[str] = None) -> int: ...


class TarefasComPermissoes:
    """Limita um :class:`ServicoTarefas` ao que o plugin declarou.

    É a interseção de dois filtros independentes, e ambos têm de deixar passar:

    * este, que exige que o plugin tenha **pedido** a permissão no manifesto;
    * o :mod:`tarefas_servico` por baixo, que exige que a **sessão** a tenha.

    Um plugin que declare ``tarefas.ver_todas`` não passa a ver tudo: passa a
    poder ver tudo *se* quem está a usar a aplicação também puder.
    """

    def __init__(self, servico: ServicoTarefas, permissoes: Iterable[Permissao]) -> None:
        self._servico = servico
        self._permissoes = frozenset(permissoes)

    def _exigir(self, permissao: Permissao) -> None:
        if permissao not in self._permissoes:
            raise PermissaoNaoDeclaradaError(permissao)

    def listar(self, incluir_concluidas: bool = True) -> List[tuple]:
        self._exigir(Permissao.TAREFAS_LER)
        return self._servico.listar(incluir_concluidas=incluir_concluidas)

    def listar_por_data(self, data_iso: str) -> List[tuple]:
        self._exigir(Permissao.TAREFAS_LER)
        return self._servico.listar_por_data(data_iso)

    def adicionar(self, descricao: str, data_vencimento: Optional[str] = None) -> int:
        self._exigir(Permissao.TAREFAS_ESCREVER)
        return self._servico.adicionar(descricao, data_vencimento)


class InterfaceAnfitria(Protocol):
    """Pontos de extensão da interface gráfica oferecidos aos plugins."""

    def registrar_aba(
        self, plugin_id: str, titulo: str, construtor: Callable[[Any], Any]
    ) -> None:
        """Adiciona uma aba criada por ``construtor(pai)`` à janela principal."""

    def remover_abas(self, plugin_id: str) -> None:
        """Remove todas as abas registadas por um plugin."""

    def notificar(self, mensagem: str) -> None:
        """Mostra uma mensagem informativa ao utilizador."""


@dataclass
class ContextoPlugin:
    """Tudo o que um plugin pode usar da aplicação.

    Attributes:
        manifesto: o manifesto validado do próprio plugin.
        app_version: versão da aplicação em execução.
        diretorio_plugin: pasta onde o plugin está instalado (somente leitura).
        diretorio_dados: pasta privada e gravável para os dados do plugin.
        logger: logger já nomeado com o id do plugin.
        tarefas: fachada de acesso às tarefas (pode ser ``None`` em testes).
        ui: pontos de extensão da GUI (``None`` quando não há interface).
    """

    manifesto: ManifestoPlugin
    app_version: str
    diretorio_plugin: Path
    diretorio_dados: Path
    logger: logging.Logger
    tarefas: Optional[ServicoTarefas] = None
    ui: Optional[InterfaceAnfitria] = None
    _subscrever_evento: Optional[Callable[..., Any]] = None
    _publicar_evento: Optional[Callable[..., Any]] = None
    _ler_config: Optional[Callable[[str], Dict[str, Any]]] = None
    _gravar_config: Optional[Callable[[str, Dict[str, Any]], None]] = None
    _traduzir: Optional[Callable[..., str]] = None
    _registrar_textos: Optional[Callable[[str, Dict[str, Dict[str, str]]], None]] = None
    _armazenamento: Optional[ArmazenamentoPlugin] = field(default=None, repr=False)

    @property
    def dados(self) -> ArmazenamentoPlugin:
        """Banco privado deste plugin.

        É criado no disco na primeira escrita, não aqui: um plugin que nunca
        guarda nada não deixa ficheiros atrás de si.
        """
        if self._armazenamento is None:
            self._armazenamento = ArmazenamentoPlugin(
                self.manifesto.id, self.diretorio_dados
            )
        return self._armazenamento

    @property
    def permissoes(self) -> FrozenSet[Permissao]:
        """O que este plugin declarou no manifesto."""
        return self.manifesto.permissoes

    def pode(self, permissao) -> bool:
        """Se o plugin pode fazer isto, agora, com esta sessão.

        Duas origens, uma resposta:

        * uma permissão do núcleo tem de ter sido **declarada** no manifesto
          (senão o plugin está a pedir o que não disse que precisava);
        * uma permissão **do próprio módulo** não precisa de ser declarada —
          é dele — e responde pelos papéis que o manifesto lhe atribuiu.

        Use isto para esconder um botão em vez de o deixar falhar.
        """
        from core import permissoes as _permissoes

        if isinstance(permissao, Permissao):
            if permissao not in self.manifesto.permissoes:
                return False
        elif str(permissao) not in self.manifesto.permissoes_proprias:
            return False
        return _permissoes.pode(permissao)

    def exigir(self, permissao) -> None:
        """Levanta :class:`~core.permissoes.PermissaoNegadaError` se não puder."""
        if not self.pode(permissao):
            from core.permissoes import PermissaoNegadaError

            raise PermissaoNegadaError(permissao)

    def registar_indicador(
        self,
        chave: str,
        calcular,
        chave_titulo: str = "",
        subir_e_bom: bool = True,
        permissao=None,
    ):
        """Declara um número que este módulo sabe medir, para o painel mostrar.

        A chave é prefixada com o id do plugin automaticamente: dois módulos
        que escolham "total" deixavam de se poder distinguir, e o último a
        carregar apagava o outro sem aviso.

        O indicador sai do painel quando o plugin é descarregado.
        """
        import indicadores

        prefixo = f"{self.manifesto.id}."
        nome = chave if str(chave).startswith(prefixo) else prefixo + str(chave)
        return indicadores.registar(
            nome,
            calcular,
            chave_titulo=chave_titulo,
            subir_e_bom=subir_e_bom,
            permissao=permissao,
            dono=self.manifesto.id,
        )

    def registar_destino_de_importacao(
        self, nome: str, campos, validar, criar, chave_titulo: str = "", permissao=None
    ):
        """Declara para onde este módulo sabe importar dados de um ficheiro.

        Como nos indicadores, o nome é prefixado com o id do plugin: dois
        módulos com um destino "itens" deixavam de se poder distinguir.

        O destino sai da lista quando o plugin é descarregado.
        """
        from importacao import motor

        prefixo = f"{self.manifesto.id}."
        completo = nome if str(nome).startswith(prefixo) else prefixo + str(nome)
        return motor.registar(
            completo,
            campos,
            validar,
            criar,
            chave_titulo=chave_titulo,
            permissao=permissao,
            dono=self.manifesto.id,
        )

    def registar_politica(
        self, nome: str, acoes, tipos, avaliar, funcionalidade=None
    ):
        """Declara uma regra que **recusa** pedidos sobre objetos deste módulo.

        Como nos indicadores e nos destinos, o nome é prefixado com o id do
        plugin, e a política sai quando o plugin é descarregado.

        Uma política só pode **tirar**: o papel decide primeiro, e o que ela
        devolve é a recusa ou nada. É por isso que é seguro um plugin
        registar uma — no pior caso tranca alguém de fora do seu próprio
        módulo, que é visível e reclamável. Se pudesse conceder, um plugin
        passava a poder abrir portas, e o contrato inteiro deixava de valer.

        Args:
            avaliar: recebe ``(sessao, pedido)`` e devolve ``None`` para
                deixar passar, ou a **chave de tradução** do motivo da
                recusa — quem a lê pode não falar a sua língua.
        """
        from core import permissoes as _permissoes

        prefixo = f"{self.manifesto.id}."
        completo = nome if str(nome).startswith(prefixo) else prefixo + str(nome)
        return _permissoes.registar_politica(
            completo,
            acoes,
            tipos,
            avaliar,
            funcionalidade=funcionalidade,
            dono=self.manifesto.id,
        )

    def utilizador(self) -> str:
        """Quem está em sessão, para o módulo registar quem fez o quê."""
        from core import permissoes as _permissoes

        return _permissoes.sessao().utilizador

    def config(self) -> Dict[str, Any]:
        """Configuração privada do plugin (dicionário vazio se ainda não existir)."""
        if self._ler_config is None:
            return {}
        return self._ler_config(self.manifesto.id)

    def guardar_config(self, dados: Dict[str, Any]) -> None:
        """Persiste a configuração privada do plugin."""
        if self._gravar_config is not None:
            self._gravar_config(self.manifesto.id, dados)

    def traduzir(self, chave: str, padrao: Optional[str] = None, **formatacao: Any) -> str:
        """Texto traduzido no idioma atual.

        Procura primeiro nos textos do próprio plugin (ver
        :meth:`registrar_textos` e a pasta ``idiomas/``) e depois nos da
        aplicação.
        """
        if self._traduzir is None:
            return padrao if padrao is not None else chave
        return self._traduzir(chave, padrao, **formatacao)

    def subscrever(self, padrao: str, ouvinte: Callable[[Any], None]) -> Any:
        """Reage a eventos da plataforma, ex.: ``"tarefa.criada"`` ou ``"tarefa.*"``.

        As subscrições ficam associadas ao plugin e são canceladas
        automaticamente quando ele é desativado — um plugin desligado não
        continua a reagir.
        """
        if self._subscrever_evento is None:
            return None
        return self._subscrever_evento(padrao, ouvinte, self.manifesto.id)

    def publicar(self, nome: str, **dados: Any) -> Any:
        """Publica um evento do plugin.

        Use um prefixo próprio (ex.: ``"estoque.item_criado"``) para não
        colidir com os eventos do núcleo.
        """
        if self._publicar_evento is None:
            return None
        return self._publicar_evento(nome, self.manifesto.id, **dados)

    def registrar_textos(self, textos_por_idioma: Dict[str, Dict[str, str]]) -> None:
        """Regista textos próprios do plugin, no formato ``{idioma: {chave: texto}}``.

        Alternativa em código à pasta ``idiomas/`` do plugin, que é carregada
        automaticamente quando existe.
        """
        if self._registrar_textos is not None:
            self._registrar_textos(self.manifesto.id, textos_por_idioma)


# ------------------------------------------------------------ classe base


class Plugin(ABC):
    """Classe base de todos os plugins.

    Os métodos do ciclo de vida têm implementação vazia por omissão: um plugin
    só precisa de redefinir aqueles que usa. Exceções levantadas aqui são
    capturadas pelo :class:`~core.plugin_manager.PluginManager` e marcam o
    plugin como em erro — nunca derrubam a aplicação.
    """

    def __init__(self, contexto: ContextoPlugin) -> None:
        self.contexto = contexto

    # ------------------------------------------------------------ metadados

    @property
    def manifesto(self) -> ManifestoPlugin:
        """Manifesto validado deste plugin."""
        return self.contexto.manifesto

    @property
    def id(self) -> str:
        """Identificador único do plugin."""
        return self.contexto.manifesto.id

    @property
    def nome(self) -> str:
        """Nome apresentável do plugin."""
        return self.contexto.manifesto.nome

    @property
    def versao(self) -> str:
        """Versão do plugin."""
        return self.contexto.manifesto.versao

    # -------------------------------------------------------- ciclo de vida

    def inicializar(self) -> None:
        """LOAD — preparar recursos. Chamado uma vez após a importação."""

    def ativar(self) -> None:
        """ACTIVATE — passar a funcionar (registar abas, ligar eventos)."""

    def desativar(self) -> None:
        """DEACTIVATE — parar de funcionar, mantendo-se carregado."""

    def finalizar(self) -> None:
        """UNLOAD — libertar recursos antes de o módulo ser descartado."""

    def __repr__(self) -> str:  # pragma: no cover - apoio a depuração
        return f"<Plugin {self.id} v{self.versao}>"


def encontrar_classe_plugin(modulo: Any) -> type:
    """Localiza a subclasse concreta de :class:`Plugin` exportada por um módulo.

    Convenções aceites, por ordem de prioridade:

    1. o atributo ``PLUGIN_CLASS`` do módulo;
    2. uma única subclasse de :class:`Plugin` definida no próprio módulo.

    Raises:
        CarregamentoPluginError: se nenhuma ou mais do que uma forem encontradas.
    """
    explicita = getattr(modulo, "PLUGIN_CLASS", None)
    if explicita is not None:
        if isinstance(explicita, type) and issubclass(explicita, Plugin):
            return explicita
        raise CarregamentoPluginError(
            "PLUGIN_CLASS não é uma subclasse de Plugin."
        )

    candidatas: Sequence[type] = [
        objeto
        for objeto in vars(modulo).values()
        if isinstance(objeto, type)
        and issubclass(objeto, Plugin)
        and objeto is not Plugin
        and objeto.__module__ == modulo.__name__
    ]
    if not candidatas:
        raise CarregamentoPluginError(
            "O módulo do plugin não define nenhuma subclasse de Plugin."
        )
    if len(candidatas) > 1:
        nomes = ", ".join(sorted(c.__name__ for c in candidatas))
        raise CarregamentoPluginError(
            f"O módulo define várias classes de plugin ({nomes}); "
            "indique qual usar através de PLUGIN_CLASS."
        )
    return candidatas[0]
