"""Que partes do produto estão ligadas nesta instalação.

Não confundir com permissões, que é o erro que este módulo existe para evitar:

* :mod:`core.permissoes` responde *esta **pessoa** pode fazer isto?*
* este módulo responde *esta **instalação** tem isto, de todo?*

São perguntas diferentes e as respostas combinam-se: um administrador com
todas as permissões do mundo não vê os relatórios se a instalação não os
tiver. Usar uma no lugar da outra dá sempre a coisa errada — permissões para
licenciar obriga a mexer nos papéis de toda a gente, e flags para autorizar
não distingue quem está à frente do ecrã.

**As funcionalidades são declaradas, não inventadas.** O catálogo abaixo é a
lista completa; perguntar por uma chave que não existe levanta erro em vez de
devolver ``False``. Uma pergunta com um erro de escrita a responder "está
desligada" é a maneira mais silenciosa de desligar alguma coisa sem querer.

Todas nascem ligadas. Desligar é uma decisão deliberada de quem administra —
e fica na trilha de auditoria, porque muda o que toda a gente vê.

Isto é o que evita que o licenciamento futuro seja um ``if licenca`` espalhado
por cem ficheiros: o *entitlement engine* passa a ter um sítio só onde dizer
o que este cliente comprou.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core import config, eventos, permissoes
from core.log import obter_logger
from core.permissoes import Permissao

logger = obter_logger(__name__)

#: Chave onde as decisões ficam guardadas na configuração da aplicação.
CHAVE_CONFIG = "funcionalidades"


class FuncionalidadeDesconhecidaError(KeyError):
    """Perguntaram por uma funcionalidade que não está no catálogo."""

    chave_mensagem = "funcionalidade_desconhecida"


class FuncionalidadeDesligadaError(Exception):
    """A funcionalidade existe mas está desligada nesta instalação."""

    chave_mensagem = "funcionalidade_desligada"

    def __init__(self, chave: str) -> None:
        super().__init__(f"A funcionalidade {chave!r} está desligada.")
        self.chave = chave


@dataclass(frozen=True)
class Funcionalidade:
    """Uma parte do produto que pode estar ligada ou desligada.

    Attributes:
        chave: identificador estável. É o que fica guardado e o que o código
            pergunta; mudá-lo é uma migração, não uma renomeação.
        padrao: como nasce numa instalação nova.
        essencial: se não pode ser desligada de todo.
    """

    chave: str
    padrao: bool = True
    essencial: bool = False

    @property
    def chave_nome(self) -> str:
        """Chave de tradução do nome apresentável."""
        return f"funcionalidade_{self.chave}"

    @property
    def chave_descricao(self) -> str:
        """Chave de tradução da explicação do que se perde ao desligar."""
        return f"funcionalidade_{self.chave}_ajuda"


#: O catálogo completo.
#:
#: O que **não** está aqui é deliberado tanto quanto o que está:
#:
#: * as tarefas, as contas e os plugins são o produto — desligá-los não deixa
#:   aplicação nenhuma;
#: * a cópia de segurança nunca se desliga: uma opção que permite ficar sem
#:   rede de proteção não é uma opção, é uma armadilha;
#: * a trilha de auditoria fica de fora de propósito. Parar de registar é uma
#:   decisão de conformidade, não uma preferência, e já tem o seu mecanismo
#:   próprio (a retenção). Um interruptor geral convidava a desligá-la para
#:   esconder alguma coisa — e o registo de que foi desligada seria a última
#:   linha da trilha.
CATALOGO: Dict[str, Funcionalidade] = {
    f.chave: f
    for f in (
        Funcionalidade("painel"),
        Funcionalidade("relatorios"),
        Funcionalidade("estrutura"),
        Funcionalidade("copia_seguranca", essencial=True),
    )
}


@dataclass(frozen=True)
class Estado:
    """Uma funcionalidade e como está agora."""

    funcionalidade: Funcionalidade
    ativa: bool
    #: ``True`` quando alguém decidiu; ``False`` quando está como veio.
    decidida: bool

    @property
    def chave(self) -> str:
        return self.funcionalidade.chave


# -------------------------------------------------------------------- leitura


def _decisoes() -> Dict[str, bool]:
    """As decisões guardadas, ignorando lixo na configuração.

    Uma chave que já não existe no catálogo (versão anterior, ficheiro
    editado à mão) é ignorada em silêncio: não é motivo para a aplicação não
    arrancar.
    """
    guardado = config.obter(CHAVE_CONFIG, {})
    if not isinstance(guardado, dict):
        return {}
    return {
        chave: bool(valor)
        for chave, valor in guardado.items()
        if chave in CATALOGO and isinstance(valor, bool)
    }


def obter(chave: str) -> Funcionalidade:
    """A funcionalidade do catálogo.

    Raises:
        FuncionalidadeDesconhecidaError: se a chave não existir.
    """
    try:
        return CATALOGO[chave]
    except KeyError as erro:
        conhecidas = ", ".join(sorted(CATALOGO))
        raise FuncionalidadeDesconhecidaError(
            f"Funcionalidade desconhecida: {chave!r}. Existem: {conhecidas}."
        ) from erro


def ativa(chave: str) -> bool:
    """Se a funcionalidade está ligada nesta instalação.

    Raises:
        FuncionalidadeDesconhecidaError: a chave tem de existir. Devolver
            ``False`` a um erro de escrita desligaria a funcionalidade em
            silêncio, e ninguém saberia porquê.
    """
    funcionalidade = obter(chave)
    if funcionalidade.essencial:
        return True
    return _decisoes().get(chave, funcionalidade.padrao)


def exigir(chave: str) -> None:
    """Levanta :class:`FuncionalidadeDesligadaError` se estiver desligada.

    Para o ponto de entrada do serviço. Esconder o botão não chega: quem
    chegar lá por outro caminho — um plugin, um atalho — tem de encontrar a
    mesma resposta.
    """
    if not ativa(chave):
        raise FuncionalidadeDesligadaError(chave)


def listar() -> List[Estado]:
    """Todas as funcionalidades, por chave."""
    decisoes = _decisoes()
    return [
        Estado(
            funcionalidade=funcionalidade,
            ativa=ativa(chave),
            decidida=chave in decisoes,
        )
        for chave, funcionalidade in sorted(CATALOGO.items())
    ]


# -------------------------------------------------------------------- escrita


def definir(chave: str, ligada: bool) -> bool:
    """Liga ou desliga uma funcionalidade nesta instalação.

    Returns:
        ``True`` se alguma coisa mudou.

    Raises:
        FuncionalidadeDesconhecidaError: a chave não existe.
        PermissaoNegadaError: só quem administra a instalação decide isto.
        ValueError: a funcionalidade é essencial e não se desliga.
    """
    funcionalidade = obter(chave)
    permissoes.exigir(Permissao.SISTEMA_ADMIN)

    if funcionalidade.essencial and not ligada:
        raise ValueError(
            f"A funcionalidade {chave!r} é essencial e não pode ser desligada."
        )

    estava = ativa(chave)
    if estava == ligada and chave in _decisoes():
        return False

    decisoes = _decisoes()
    decisoes[chave] = bool(ligada)
    config.definir(CHAVE_CONFIG, decisoes)

    logger.info("Funcionalidade %s: %s", chave, "ligada" if ligada else "desligada")
    eventos.publicar(
        eventos.FUNCIONALIDADE_ALTERADA,
        origem="funcionalidades",
        id=chave,
        ligada=bool(ligada),
        antes={"ligada": estava},
        depois={"ligada": bool(ligada)},
    )
    return True


def repor(chave: Optional[str] = None) -> None:
    """Volta ao valor de origem: uma funcionalidade, ou todas.

    Raises:
        PermissaoNegadaError: só quem administra a instalação.
    """
    permissoes.exigir(Permissao.SISTEMA_ADMIN)
    if chave is None:
        config.definir(CHAVE_CONFIG, {})
        logger.info("Funcionalidades repostas nos valores de origem.")
        return

    obter(chave)
    decisoes = _decisoes()
    if decisoes.pop(chave, None) is not None:
        config.definir(CHAVE_CONFIG, decisoes)
        eventos.publicar(
            eventos.FUNCIONALIDADE_ALTERADA,
            origem="funcionalidades",
            id=chave,
            ligada=ativa(chave),
        )
