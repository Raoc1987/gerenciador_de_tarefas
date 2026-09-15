"""Papéis e permissões da plataforma (RBAC).

Quem entra na aplicação (ver :mod:`core.utilizadores`) tem um papel, e o papel
concede permissões nomeadas. Há um ponto único de verificação — :func:`pode` e
:func:`exigir` — usado pela interface, pela análise, pelos relatórios e pelo
serviço de tarefas.

Sem sessão iniciada, a sessão corrente é o utilizador local guardado na
configuração: é o que permite correr o ``--autoteste`` e os testes sem um ecrã
de início de sessão.

Quem vê que tarefas é decidido em :mod:`tarefas_servico`, a partir de
``TAREFAS_VER_TODAS``.

Uso::

    from core import permissoes

    if permissoes.pode(permissoes.Permissao.PLUGINS_GERIR):
        ...

    permissoes.exigir(permissoes.Permissao.TAREFAS_ESCREVER)  # levanta se não
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
)

from core import config
from core.log import obter_logger

logger = obter_logger(__name__)

_CHAVE_PAPEL = "papel"
_CHAVE_UTILIZADOR = "utilizador"


class PermissaoNegadaError(PermissionError):
    """A sessão atual não tem a permissão exigida."""

    def __init__(self, permissao) -> None:
        # Também serve as permissões de módulos, que são nomes e não membros
        # do enum: a mensagem é a mesma e quem apanha não tem de distinguir.
        nome = getattr(permissao, "value", permissao)
        super().__init__(f"Permissão necessária: {nome}")
        self.permissao = permissao
        self.chave_mensagem = "permissao_negada"


class PoliticaNegouError(PermissaoNegadaError):
    """O papel concedia, mas uma política recusou **este** caso.

    Subclasse de :class:`PermissaoNegadaError` de propósito: quem já apanhava
    uma recusa continua a apanhá-la sem mudar nada. O que esta acrescenta é o
    **motivo** — uma recusa sem razão é a pior resposta que este módulo pode
    dar, e aqui há sempre uma razão, porque alguém a escreveu ao declarar a
    política.
    """

    def __init__(self, permissao, motivo: str, politica: str = "") -> None:
        super().__init__(permissao)
        self.chave_mensagem = motivo or "permissao_negada"
        self.politica = politica


class Permissao(str, Enum):
    """O que se pode fazer na plataforma.

    Os nomes seguem ``area.acao``, para que um módulo novo acrescente as suas
    sem colidir (ex.: ``estoque.escrever``).
    """

    TAREFAS_LER = "tarefas.ler"
    TAREFAS_ESCREVER = "tarefas.escrever"
    TAREFAS_VER_TODAS = "tarefas.ver_todas"
    """Ver e editar tarefas de outras pessoas, além das próprias."""

    TAREFAS_VER_UNIDADE = "tarefas.ver_unidade"
    """Ver e editar as tarefas da sua unidade e das que estão abaixo dela.

    O meio-termo entre "só as minhas" e "as de toda a gente", que é onde a
    maioria dos chefes de departamento realmente está. Sem unidade atribuída
    não alcança nada: o âmbito é a sub-árvore, e uma pessoa sem lugar na
    estrutura tem sub-árvore vazia.
    """

    # O texto de cada permissão é dado guardado: está nos papéis, nas
    # declarações dos plugins e nas chaves de tradução. Renomear o módulo
    # `analytics` para `analitica` não o muda — quem já tem esta permissão
    # continua a tê-la.
    ANALYTICS_LER = "analytics.ler"
    RELATORIOS_LER = "relatorios.ler"
    RELATORIOS_EXPORTAR = "relatorios.exportar"
    PLUGINS_GERIR = "plugins.gerir"
    UTILIZADORES_GERIR = "utilizadores.gerir"
    SISTEMA_ADMIN = "sistema.admin"


@dataclass(frozen=True)
class Papel:
    """Um conjunto nomeado de permissões."""

    nome: str
    permissoes: FrozenSet[Permissao] = field(default_factory=frozenset)

    def pode(self, permissao: Permissao) -> bool:
        """Se este papel concede a permissão.

        ``SISTEMA_ADMIN`` concede tudo: é o papel do dono da instalação.
        """
        return Permissao.SISTEMA_ADMIN in self.permissoes or permissao in self.permissoes


_TODAS = frozenset(Permissao)

#: Papéis de origem. Um produto multiutilizador poderá torná-los editáveis.
PAPEIS: Dict[str, Papel] = {
    "administrador": Papel("administrador", _TODAS),
    "gestor": Papel(
        "gestor",
        frozenset(
            {
                Permissao.TAREFAS_LER,
                Permissao.TAREFAS_ESCREVER,
                Permissao.TAREFAS_VER_TODAS,
                Permissao.ANALYTICS_LER,
                Permissao.RELATORIOS_LER,
                Permissao.RELATORIOS_EXPORTAR,
                Permissao.PLUGINS_GERIR,
            }
        ),
    ),
    "supervisor": Papel(
        "supervisor",
        frozenset(
            {
                Permissao.TAREFAS_LER,
                Permissao.TAREFAS_ESCREVER,
                Permissao.TAREFAS_VER_TODAS,
                Permissao.ANALYTICS_LER,
                Permissao.RELATORIOS_LER,
            }
        ),
    ),
    # Vê e escreve as suas tarefas, e a análise das suas: agora que as tarefas
    # têm dono, ver os próprios números deixou de ser um privilégio.
    "colaborador": Papel(
        "colaborador",
        frozenset(
            {
                Permissao.TAREFAS_LER,
                Permissao.TAREFAS_ESCREVER,
                Permissao.ANALYTICS_LER,
                Permissao.RELATORIOS_LER,
            }
        ),
    ),
    # Manda no seu departamento e no que está abaixo dele — não na empresa
    # toda. Papel novo: nenhum dos que já existiam muda de comportamento com
    # a chegada da estrutura.
    "gestor_de_unidade": Papel(
        "gestor_de_unidade",
        frozenset(
            {
                Permissao.TAREFAS_LER,
                Permissao.TAREFAS_ESCREVER,
                Permissao.TAREFAS_VER_UNIDADE,
                Permissao.ANALYTICS_LER,
                Permissao.RELATORIOS_LER,
                Permissao.RELATORIOS_EXPORTAR,
            }
        ),
    ),
    # Vê tudo, não escreve nada: é um papel de acompanhamento.
    "visualizador": Papel(
        "visualizador",
        frozenset(
            {
                Permissao.TAREFAS_LER,
                Permissao.TAREFAS_VER_TODAS,
                Permissao.ANALYTICS_LER,
                Permissao.RELATORIOS_LER,
            }
        ),
    ),
}

PAPEL_PADRAO = "administrador"


# ------------------------------------------------- permissões de um módulo

#: Permissões que os módulos de negócio trazem consigo: ``{nome: {papéis}}``.
#:
#: O núcleo não conhece "estoque" nem "recursos humanos", e não devia. Um
#: módulo declara as suas no manifesto e elas passam a existir enquanto ele
#: estiver carregado.
#:
#: A regra de segurança é o espaço de nomes: um módulo só pode definir
#: permissões com o seu próprio id à frente (``estoque.ler``). Assim o pior
#: que consegue conceder é acesso aos **seus** dados — nunca às tarefas, às
#: contas ou ao sistema, que continuam a ser decisão de quem administra.
_DE_MODULOS: Dict[str, Dict[str, FrozenSet[str]]] = {}


def registar_permissoes_de_modulo(
    plugin_id: str, mapa: Dict[str, Iterable[str]]
) -> None:
    """Regista as permissões que um módulo traz, com os papéis que as têm.

    Raises:
        ValueError: se alguma permissão não estiver no espaço de nomes do
            módulo, ou colidir com uma permissão do núcleo.
    """
    prefixo = f"{plugin_id}."
    do_nucleo = {p.value for p in Permissao}
    registo: Dict[str, FrozenSet[str]] = {}

    for nome, papeis in (mapa or {}).items():
        if not nome.startswith(prefixo):
            raise ValueError(
                f"O módulo {plugin_id!r} não pode definir {nome!r}: "
                f"as suas permissões começam por {prefixo!r}."
            )
        if nome in do_nucleo:
            raise ValueError(f"{nome!r} é uma permissão do núcleo.")
        registo[nome] = frozenset(str(papel) for papel in papeis)

    _DE_MODULOS[plugin_id] = registo
    if registo:
        logger.info("Permissões do módulo %s: %s", plugin_id, ", ".join(sorted(registo)))


def esquecer_permissoes_de_modulo(plugin_id: str) -> None:
    """Tira do registo as permissões de um módulo descarregado."""
    _DE_MODULOS.pop(plugin_id, None)


def limpar_permissoes_de_modulos() -> None:
    """Esquece todas as permissões de módulos.

    O registo é global, como o barramento e a sessão. Num processo novo está
    vazio; nos testes tem de voltar a estar, senão um módulo carregado num
    teste concede permissões no seguinte.
    """
    _DE_MODULOS.clear()


def permissoes_de_modulos() -> Dict[str, FrozenSet[str]]:
    """Todas as permissões de módulos atualmente registadas."""
    juntas: Dict[str, FrozenSet[str]] = {}
    for registo in _DE_MODULOS.values():
        juntas.update(registo)
    return juntas


# ------------------------------------------------- políticas por atributo
#
# O RBAC responde a "podes fazer isto?". Toda a regra de negócio que uma
# empresa realmente precisa tem a outra forma: "podes fazer isto **a isto**?".
# É a diferença entre ter a chave do arquivo e poder mexer numa pasta em
# concreto.
#
# Uma política é a segunda pergunta, e tem três propriedades que não são
# negociáveis:
#
# 1. **Só recusa.** Nunca concede. Uma política mal escrita — ou vinda de um
#    plugin — no pior caso tranca alguém de fora, o que é visível e
#    reclamável. Se pudesse conceder, no pior caso abria uma porta em
#    silêncio, e ninguém repara numa porta aberta.
# 2. **Corre depois do papel.** Se o RBAC já disse não, nenhuma política
#    chega a ser avaliada: não há nada a recusar e não se paga o custo.
# 3. **Rebenta fechada.** Uma política que levanta uma exceção recusa, com
#    registo. É o mesmo princípio do motor de importação: uma validação
#    partida não pode passar por validação bem sucedida. Numa regra de
#    acesso, rebentar aberta seria desligar a segurança sem ninguém saber.


@dataclass(frozen=True)
class Pedido:
    """O que a sessão está a tentar fazer, e a quê.

    Não é só o objeto: é o par ``(ação, objeto)``. Fingir que a permissão já
    é a ação obriga a inventar uma permissão nova sempre que se quer
    distinguir "editar" de "apagar" — e a granularidade dos papéis passaria a
    ser decidida pelas políticas, que é exatamente ao contrário.

    Attributes:
        acao: o verbo — ``"criar"``, ``"concluir"``, ``"reabrir"``,
            ``"remover"``. Vocabulário de quem regista o pedido.
        tipo: o que é o objeto — ``"tarefa"``, ``"estoque.item"``.
        atributos: os factos sobre o objeto. Texto e números simples; o
            núcleo não conhece as classes de ninguém e não as vai importar.
    """

    acao: str
    tipo: str
    atributos: Mapping[str, Any] = field(default_factory=dict)

    def atributo(self, nome: str, omissao: Any = None) -> Any:
        return self.atributos.get(nome, omissao)


#: Assinatura de uma política: recebe a sessão e o pedido, devolve ``None``
#: para deixar passar, ou a **chave de tradução** do motivo para recusar.
#:
#: Chave e não frase: o motivo aparece a quem foi recusado, e esta aplicação
#: fala três línguas.
Avaliador = Callable[["Sessao", Pedido], Optional[str]]


@dataclass(frozen=True)
class Politica:
    """Uma regra que pode recusar um pedido que o papel permitia."""

    nome: str
    acoes: FrozenSet[str]
    tipos: FrozenSet[str]
    avaliar: Avaliador
    #: Interruptor no catálogo de funcionalidades. Sem ele, a política está
    #: sempre a valer.
    funcionalidade: Optional[str] = None
    dono: str = ""

    def aplica_se_a(self, pedido: Pedido) -> bool:
        return pedido.acao in self.acoes and pedido.tipo in self.tipos

    def ligada(self) -> bool:
        """Se está a valer nesta instalação."""
        if self.funcionalidade is None:
            return True
        from core import funcionalidades

        try:
            return funcionalidades.ativa(self.funcionalidade)
        except Exception:
            # Uma política presa a uma funcionalidade que não existe está mal
            # declarada. Fechada: recusar de mais é recuperável, recusar de
            # menos numa regra de acesso não é.
            logger.exception(
                "A política %s depende da funcionalidade %r, que não existe.",
                self.nome,
                self.funcionalidade,
            )
            return True


_POLITICAS: Dict[str, Politica] = {}


def registar_politica(
    nome: str,
    acoes: Iterable[str],
    tipos: Iterable[str],
    avaliar: Avaliador,
    funcionalidade: Optional[str] = None,
    dono: str = "",
) -> Politica:
    """Põe uma política a valer.

    A inversão é a mesma das permissões de módulos: o núcleo avalia, mas não
    conhece nenhuma regra de negócio — quem a declara vive fora.

    Raises:
        ValueError: nome vazio, sem ações ou sem tipos, avaliador que não é
            chamável, ou — vindo de um módulo — nome fora do espaço de nomes
            desse módulo.
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Uma política precisa de um nome.")
    acoes, tipos = frozenset(acoes or ()), frozenset(tipos or ())
    if not acoes or not tipos:
        raise ValueError(f"A política {nome!r} tem de dizer a que ações e tipos se aplica.")
    if not callable(avaliar):
        raise ValueError(f"A política {nome!r} precisa de um avaliador.")
    if dono and not nome.startswith(f"{dono}."):
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar as suas políticas com {dono + '.'!r}."
        )

    politica = Politica(nome, acoes, tipos, avaliar, funcionalidade, dono)
    _POLITICAS[nome] = politica
    logger.info("Política registada: %s (%s sobre %s)", nome, sorted(acoes), sorted(tipos))
    return politica


def esquecer_politicas_de_dono(dono: str) -> int:
    """Tira as políticas de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [nome for nome, p in _POLITICAS.items() if p.dono == dono]
    for nome in saem:
        _POLITICAS.pop(nome, None)
    return len(saem)


def limpar_politicas() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _POLITICAS.clear()


def politicas() -> List[Politica]:
    """As políticas registadas, por nome."""
    return [_POLITICAS[nome] for nome in sorted(_POLITICAS)]


@dataclass(frozen=True)
class Recusa:
    """Uma política disse que não, e qual e porquê."""

    politica: str
    motivo: str
    """Chave de tradução da razão, para ser mostrada na língua de quem lê."""


def recusa(pedido: Pedido) -> Optional[Recusa]:
    """A primeira política que recusa este pedido — ``None`` se nenhuma.

    A primeira, e não todas: quem foi recusado precisa de uma razão, não de
    uma lista. A ordem é a alfabética do nome, para a resposta ser sempre a
    mesma e não depender da ordem em que os plugins carregaram.
    """
    atual = sessao()
    for politica in politicas():
        if not politica.aplica_se_a(pedido) or not politica.ligada():
            continue
        try:
            motivo = politica.avaliar(atual, pedido)
        except Exception:
            logger.exception("A política %s rebentou a avaliar.", politica.nome)
            return Recusa(politica.nome, "politica_falhou")
        if motivo:
            logger.info(
                "Política %s recusou %s de %s sobre %s.",
                politica.nome,
                pedido.acao,
                atual.utilizador,
                pedido.tipo,
            )
            return Recusa(politica.nome, motivo)
    return None


@dataclass(frozen=True)
class Sessao:
    """Quem está a usar a aplicação neste momento."""

    utilizador: str
    papel: Papel

    def pode(self, permissao: Permissao) -> bool:
        """Se a sessão tem a permissão."""
        return self.papel.pode(permissao)

    def permissoes(self) -> FrozenSet[Permissao]:
        """Permissões efetivas desta sessão."""
        if Permissao.SISTEMA_ADMIN in self.papel.permissoes:
            return _TODAS
        return self.papel.permissoes


_sessao: Optional[Sessao] = None


def obter_papel(nome: str) -> Papel:
    """Papel pelo nome; cai no papel padrão se não existir."""
    papel = PAPEIS.get(nome)
    if papel is None:
        logger.warning("Papel desconhecido %r; a usar %r.", nome, PAPEL_PADRAO)
        return PAPEIS[PAPEL_PADRAO]
    return papel


def sessao() -> Sessao:
    """Sessão corrente, criando-a a partir da configuração se preciso.

    Enquanto não houver autenticação, a sessão é o utilizador local com o
    papel guardado em ``app_config.json``.
    """
    global _sessao
    if _sessao is None:
        nome = str(config.obter(_CHAVE_UTILIZADOR, "local"))
        papel = obter_papel(str(config.obter(_CHAVE_PAPEL, PAPEL_PADRAO)))
        _sessao = Sessao(utilizador=nome, papel=papel)
        logger.info("Sessão iniciada: %s (%s)", nome, papel.nome)
    return _sessao


def definir_sessao(utilizador: str, papel: str, persistir: bool = True) -> Sessao:
    """Define quem está a usar a aplicação.

    É por aqui que um futuro ecrã de autenticação entra, sem mexer no resto.
    """
    global _sessao
    _sessao = Sessao(utilizador=utilizador, papel=obter_papel(papel))
    if persistir:
        try:
            config.definir(_CHAVE_UTILIZADOR, utilizador)
            config.definir(_CHAVE_PAPEL, _sessao.papel.nome)
        except OSError:
            logger.warning("Não foi possível guardar a sessão.")
    logger.info("Sessão definida: %s (%s)", utilizador, _sessao.papel.nome)
    return _sessao


def terminar_sessao() -> None:
    """Esquece a sessão em memória (a próxima leitura recria-a da config)."""
    global _sessao
    _sessao = None


def pode(permissao, pedido: Optional[Pedido] = None) -> bool:
    """Se a sessão atual pode fazer isto — e, havendo ``pedido``, a **isto**.

    Aceita uma :class:`Permissao` do núcleo ou o nome de uma permissão de
    módulo (``"estoque.ler"``). Uma permissão de módulo que ninguém registou
    é negada: ou o módulo não está carregado, ou o nome está errado — e nos
    dois casos a resposta certa é não.

    Sem ``pedido``, a resposta é a do papel, exatamente como sempre foi. Com
    ``pedido``, o papel continua a decidir primeiro: só se ele disser que sim
    é que as políticas são consultadas, e elas só podem tirar.
    """
    if not _concede_o_papel(permissao):
        return False
    if pedido is None:
        return True
    return recusa(pedido) is None


def _concede_o_papel(permissao) -> bool:
    """A pergunta do RBAC, isolada: o papel concede esta permissão?"""
    if isinstance(permissao, Permissao):
        return sessao().pode(permissao)

    # Um nome do núcleo em texto é a mesma permissão do núcleo. Sem isto,
    # `pode("tarefas.ler")` era negado em silêncio até ao administrador — e um
    # "não" sem razão é a pior resposta que este módulo pode dar.
    try:
        return sessao().pode(Permissao(str(permissao)))
    except ValueError:
        pass

    papeis = permissoes_de_modulos().get(str(permissao))
    if papeis is None:
        # Não registada: ou o módulo não está carregado, ou o nome está
        # errado. **Nem o administrador a tem** — dizer que sim a uma
        # permissão que não existe esconderia um erro de escrita de quem
        # administra e mostrá-lo-ia só a quem não administra.
        return False

    atual = sessao()
    if Permissao.SISTEMA_ADMIN in atual.papel.permissoes:
        return True
    return atual.papel.nome in papeis


def exigir(permissao, pedido: Optional[Pedido] = None) -> None:
    """Garante a permissão — e, havendo ``pedido``, que nenhuma política recusa.

    As duas recusas são distinguidas porque têm respostas diferentes: à
    primeira, quem foi recusado precisa de outro papel; à segunda, o papel
    está certo e o que falha é este caso em concreto — e a política diz
    porquê.

    Raises:
        PermissaoNegadaError: se o papel não conceder.
        PoliticaNegouError: se o papel conceder e uma política recusar.
    """
    nome = permissao.value if isinstance(permissao, Permissao) else str(permissao)
    if not _concede_o_papel(permissao):
        logger.warning("Permissão negada: %s (papel %s)", nome, sessao().papel.nome)
        raise PermissaoNegadaError(permissao)

    if pedido is None:
        return

    negada = recusa(pedido)
    if negada is not None:
        logger.warning(
            "Política %s recusou %s sobre %s a %s.",
            negada.politica,
            pedido.acao,
            pedido.tipo,
            sessao().utilizador,
        )
        _anunciar_recusa(nome, pedido, negada)
        raise PoliticaNegouError(permissao, negada.motivo, negada.politica)


def _anunciar_recusa(permissao: str, pedido: Pedido, negada: "Recusa") -> None:
    """Põe a tentativa recusada na trilha de auditoria.

    Dentro de um ``try``: se o barramento falhar, a recusa **mantém-se**. Não
    poder registar é mau; deixar passar porque não se conseguiu registar seria
    pior, e trocar o erro de acesso por outro qualquer esconderia os dois.
    """
    try:
        from core import eventos

        eventos.publicar(
            eventos.POLITICA_RECUSOU,
            origem="permissoes",
            politica=negada.politica,
            motivo=negada.motivo,
            permissao=permissao,
            acao=pedido.acao,
            tipo=pedido.tipo,
            alvo=pedido.atributo("id"),
        )
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Não foi possível registar a recusa da política.")


def permissoes_em_falta(necessarias: Iterable[Permissao]) -> FrozenSet[Permissao]:
    """Quais das permissões pedidas a sessão **não** tem."""
    atual = sessao()
    return frozenset(p for p in necessarias if not atual.pode(p))
