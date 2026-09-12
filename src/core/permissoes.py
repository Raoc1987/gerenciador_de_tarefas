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

    def __init__(self, permissao: "Permissao") -> None:
        super().__init__(f"Permissão necessária: {permissao.value}")
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


def pode(permissao: Permissao) -> bool:
    """Se a sessão atual tem a permissão."""
    return sessao().pode(permissao)


def exigir(permissao: Permissao) -> None:
    """Garante a permissão.

    Raises:
        PermissaoNegadaError: se a sessão não a tiver.
    """
    if not pode(permissao):
        logger.warning(
            "Permissão negada: %s (papel %s)", permissao.value, sessao().papel.nome
        )
        raise PermissaoNegadaError(permissao)


def permissoes_em_falta(necessarias: Iterable[Permissao]) -> FrozenSet[Permissao]:
    """Quais das permissões pedidas a sessão **não** tem."""
    atual = sessao()
    return frozenset(p for p in necessarias if not atual.pode(p))
