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
from typing import Dict, FrozenSet, Iterable, Optional

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


def pode(permissao) -> bool:
    """Se a sessão atual tem a permissão.

    Aceita uma :class:`Permissao` do núcleo ou o nome de uma permissão de
    módulo (``"estoque.ler"``). Uma permissão de módulo que ninguém registou
    é negada: ou o módulo não está carregado, ou o nome está errado — e nos
    dois casos a resposta certa é não.
    """
    if isinstance(permissao, Permissao):
        return sessao().pode(permissao)

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


def exigir(permissao) -> None:
    """Garante a permissão.

    Raises:
        PermissaoNegadaError: se a sessão não a tiver.
    """
    if not pode(permissao):
        nome = permissao.value if isinstance(permissao, Permissao) else str(permissao)
        logger.warning("Permissão negada: %s (papel %s)", nome, sessao().papel.nome)
        raise PermissaoNegadaError(permissao)


def permissoes_em_falta(necessarias: Iterable[Permissao]) -> FrozenSet[Permissao]:
    """Quais das permissões pedidas a sessão **não** tem."""
    atual = sessao()
    return frozenset(p for p in necessarias if not atual.pode(p))
