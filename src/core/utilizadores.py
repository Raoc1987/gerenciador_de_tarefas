"""Contas de utilizador: criação, autenticação e gestão.

Guarda quem pode usar a aplicação e com que papel. As palavras-passe passam
por :mod:`core.seguranca` e nunca são guardadas nem registadas em claro.

Duas salvaguardas que valem a pena conhecer:

* **Não é possível ficar sem administrador.** Desativar, despromover ou
  remover o último administrador ativo é recusado — senão a instalação ficava
  sem ninguém que a pudesse gerir.
* **Tentativas falhadas bloqueiam a conta temporariamente**, para uma
  adivinhação por força bruta deixar de ser prática.

Limite conhecido, declarado de propósito: **o banco não é cifrado**. Quem
tiver acesso ao ficheiro em ``%APPDATA%`` lê as tarefas — a autenticação
protege o uso da aplicação, não o disco.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from core import eventos, seguranca
from core.log import obter_logger
from core.permissoes import PAPEIS, PAPEL_PADRAO, Papel, obter_papel

logger = obter_logger(__name__)

#: Falhas seguidas antes de a conta bloquear.
TENTATIVAS_ATE_BLOQUEAR = 5
#: Duração do bloqueio.
MINUTOS_DE_BLOQUEIO = 5

COMPRIMENTO_MINIMO_UTILIZADOR = 3
COMPRIMENTO_MAXIMO_UTILIZADOR = 32


class UtilizadorError(Exception):
    """Erro de gestão de contas."""

    chave_mensagem = "utilizador_erro"


class NomeIndisponivelError(UtilizadorError):
    """Já existe uma conta com esse nome de utilizador."""

    chave_mensagem = "utilizador_ja_existe"


class NomeInvalidoError(UtilizadorError):
    """O nome de utilizador não é aceitável."""

    chave_mensagem = "utilizador_nome_invalido"


class UltimoAdministradorError(UtilizadorError):
    """A operação deixaria a instalação sem administrador ativo."""

    chave_mensagem = "utilizador_ultimo_admin"


class MotivoFalha(str, Enum):
    """Porque é que uma autenticação não passou."""

    CREDENCIAIS = "credenciais"
    INATIVO = "inativo"
    BLOQUEADO = "bloqueado"


@dataclass(frozen=True)
class Utilizador:
    """Uma conta."""

    id: int
    nome_utilizador: str
    nome: str
    papel_nome: str
    ativo: bool
    criado_em: str
    ultimo_acesso: Optional[str] = None
    tentativas_falhadas: int = 0
    bloqueado_ate: Optional[str] = None

    @property
    def papel(self) -> Papel:
        """O papel efetivo desta conta."""
        return obter_papel(self.papel_nome)

    @property
    def apresentacao(self) -> str:
        """Nome a mostrar: o nome próprio, ou o de utilizador."""
        return self.nome or self.nome_utilizador

    def esta_bloqueado(self, agora: Optional[datetime] = None) -> bool:
        """Se a conta está temporariamente bloqueada."""
        if not self.bloqueado_ate:
            return False
        try:
            ate = datetime.fromisoformat(self.bloqueado_ate)
        except ValueError:  # pragma: no cover - defensivo
            return False
        return (agora or datetime.now()) < ate


@dataclass(frozen=True)
class ResultadoAutenticacao:
    """O que aconteceu numa tentativa de entrada."""

    sucesso: bool
    utilizador: Optional[Utilizador] = None
    motivo: Optional[MotivoFalha] = None
    minutos_restantes: int = 0

    def __bool__(self) -> bool:
        return self.sucesso


# --------------------------------------------------------------- consulta


def _linha_para_utilizador(linha) -> Utilizador:
    return Utilizador(
        id=linha[0],
        nome_utilizador=linha[1],
        nome=linha[2],
        papel_nome=linha[4],
        ativo=bool(linha[5]),
        criado_em=linha[6],
        ultimo_acesso=linha[7],
        tentativas_falhadas=linha[8],
        bloqueado_ate=linha[9],
    )


_COLUNAS = (
    "id, nome_utilizador, nome, senha_hash, papel, ativo, criado_em, "
    "ultimo_acesso, tentativas_falhadas, bloqueado_ate"
)


def _conectar():
    import database

    database.criar_tabela()
    return database.conectar()


def listar(incluir_inativos: bool = True) -> List[Utilizador]:
    """Todas as contas, por nome de utilizador."""
    consulta = f"SELECT {_COLUNAS} FROM utilizadores"
    if not incluir_inativos:
        consulta += " WHERE ativo = 1"
    consulta += " ORDER BY nome_utilizador"
    with _conectar() as conexao:
        return [_linha_para_utilizador(linha) for linha in conexao.execute(consulta)]


def obter(nome_utilizador: str) -> Optional[Utilizador]:
    """Conta pelo nome de utilizador (sem distinguir maiúsculas)."""
    with _conectar() as conexao:
        linha = conexao.execute(
            f"SELECT {_COLUNAS} FROM utilizadores WHERE nome_utilizador = ?",
            ((nome_utilizador or "").strip(),),
        ).fetchone()
    return _linha_para_utilizador(linha) if linha else None


def existe_algum() -> bool:
    """Se já existe pelo menos uma conta (usado no primeiro arranque)."""
    with _conectar() as conexao:
        return conexao.execute("SELECT 1 FROM utilizadores LIMIT 1").fetchone() is not None


def administradores_ativos() -> List[Utilizador]:
    """Contas ativas com permissão de administração do sistema."""
    from core.permissoes import Permissao

    return [
        utilizador
        for utilizador in listar(incluir_inativos=False)
        if utilizador.papel.pode(Permissao.SISTEMA_ADMIN)
    ]


# ----------------------------------------------------------------- escrita


def validar_nome(nome_utilizador: str) -> str:
    """Valida e normaliza um nome de utilizador.

    Raises:
        NomeInvalidoError: se for curto, longo ou tiver caracteres estranhos.
    """
    nome = (nome_utilizador or "").strip()
    if not (COMPRIMENTO_MINIMO_UTILIZADOR <= len(nome) <= COMPRIMENTO_MAXIMO_UTILIZADOR):
        raise NomeInvalidoError(
            f"O nome de utilizador deve ter entre {COMPRIMENTO_MINIMO_UTILIZADOR} "
            f"e {COMPRIMENTO_MAXIMO_UTILIZADOR} caracteres."
        )
    if not all(c.isalnum() or c in "._-" for c in nome):
        raise NomeInvalidoError(
            "O nome de utilizador só pode ter letras, dígitos, '.', '_' ou '-'."
        )
    return nome


def criar(
    nome_utilizador: str,
    senha: str,
    papel: str = PAPEL_PADRAO,
    nome: str = "",
) -> Utilizador:
    """Cria uma conta.

    Raises:
        NomeInvalidoError: nome de utilizador inaceitável.
        NomeIndisponivelError: já existe uma conta com esse nome.
        SenhaInvalidaError: palavra-passe fraca demais.
    """
    nome_utilizador = validar_nome(nome_utilizador)
    seguranca.validar_senha(senha, nome_utilizador)
    if papel not in PAPEIS:
        papel = PAPEL_PADRAO

    if obter(nome_utilizador) is not None:
        raise NomeIndisponivelError(f"Já existe a conta {nome_utilizador!r}.")

    with _conectar() as conexao:
        conexao.execute(
            "INSERT INTO utilizadores (nome_utilizador, nome, senha_hash, papel,"
            " ativo, criado_em) VALUES (?, ?, ?, ?, 1, ?)",
            (
                nome_utilizador,
                (nome or "").strip(),
                seguranca.gerar_hash(senha),
                papel,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

    criado = obter(nome_utilizador)
    logger.info("Conta criada: %s (%s)", nome_utilizador, papel)
    eventos.publicar(
        eventos.UTILIZADOR_CRIADO, origem="utilizadores", id=nome_utilizador, papel=papel
    )
    assert criado is not None
    return criado


def alterar_senha(nome_utilizador: str, nova_senha: str) -> bool:
    """Define uma nova palavra-passe e limpa bloqueios."""
    utilizador = obter(nome_utilizador)
    if utilizador is None:
        return False
    seguranca.validar_senha(nova_senha, utilizador.nome_utilizador)

    with _conectar() as conexao:
        conexao.execute(
            "UPDATE utilizadores SET senha_hash = ?, tentativas_falhadas = 0,"
            " bloqueado_ate = NULL WHERE id = ?",
            (seguranca.gerar_hash(nova_senha), utilizador.id),
        )
    logger.info("Palavra-passe alterada: %s", utilizador.nome_utilizador)
    eventos.publicar(
        eventos.UTILIZADOR_ALTERADO,
        origem="utilizadores",
        id=utilizador.nome_utilizador,
        alteracao="senha",
    )
    return True


def _garantir_que_sobra_administrador(utilizador: Utilizador) -> None:
    from core.permissoes import Permissao

    if not utilizador.papel.pode(Permissao.SISTEMA_ADMIN) or not utilizador.ativo:
        return
    restantes = [u for u in administradores_ativos() if u.id != utilizador.id]
    if not restantes:
        raise UltimoAdministradorError(
            "Esta é a última conta de administração ativa da instalação."
        )


def definir_papel(nome_utilizador: str, papel: str) -> bool:
    """Muda o papel de uma conta.

    Raises:
        UltimoAdministradorError: se deixasse a instalação sem administrador.
    """
    utilizador = obter(nome_utilizador)
    if utilizador is None:
        return False
    if papel not in PAPEIS:
        raise UtilizadorError(f"Papel desconhecido: {papel!r}")

    from core.permissoes import Permissao

    if not obter_papel(papel).pode(Permissao.SISTEMA_ADMIN):
        _garantir_que_sobra_administrador(utilizador)

    with _conectar() as conexao:
        conexao.execute(
            "UPDATE utilizadores SET papel = ? WHERE id = ?", (papel, utilizador.id)
        )
    logger.info("Papel de %s alterado para %s", nome_utilizador, papel)
    eventos.publicar(
        eventos.UTILIZADOR_ALTERADO,
        origem="utilizadores",
        id=utilizador.nome_utilizador,
        alteracao=f"papel={papel}",
    )
    return True


def definir_ativo(nome_utilizador: str, ativo: bool) -> bool:
    """Ativa ou desativa uma conta."""
    utilizador = obter(nome_utilizador)
    if utilizador is None:
        return False
    if not ativo:
        _garantir_que_sobra_administrador(utilizador)

    with _conectar() as conexao:
        conexao.execute(
            "UPDATE utilizadores SET ativo = ?, tentativas_falhadas = 0,"
            " bloqueado_ate = NULL WHERE id = ?",
            (1 if ativo else 0, utilizador.id),
        )
    logger.info("Conta %s: ativo=%s", nome_utilizador, ativo)
    eventos.publicar(
        eventos.UTILIZADOR_ALTERADO,
        origem="utilizadores",
        id=utilizador.nome_utilizador,
        alteracao=f"ativo={ativo}",
    )
    return True


def remover(nome_utilizador: str) -> bool:
    """Apaga uma conta.

    Raises:
        UltimoAdministradorError: se fosse o último administrador ativo.
    """
    utilizador = obter(nome_utilizador)
    if utilizador is None:
        return False
    _garantir_que_sobra_administrador(utilizador)

    with _conectar() as conexao:
        conexao.execute("DELETE FROM utilizadores WHERE id = ?", (utilizador.id,))
    logger.info("Conta removida: %s", nome_utilizador)
    eventos.publicar(
        eventos.UTILIZADOR_REMOVIDO, origem="utilizadores", id=utilizador.nome_utilizador
    )
    return True


# ------------------------------------------------------------ autenticação


def _registar_falha(utilizador: Utilizador) -> int:
    tentativas = utilizador.tentativas_falhadas + 1
    bloqueio = None
    if tentativas >= TENTATIVAS_ATE_BLOQUEAR:
        bloqueio = (
            datetime.now() + timedelta(minutes=MINUTOS_DE_BLOQUEIO)
        ).isoformat(timespec="seconds")

    with _conectar() as conexao:
        conexao.execute(
            "UPDATE utilizadores SET tentativas_falhadas = ?, bloqueado_ate = ?"
            " WHERE id = ?",
            (tentativas, bloqueio, utilizador.id),
        )
    return tentativas


def autenticar(nome_utilizador: str, senha: str) -> ResultadoAutenticacao:
    """Verifica credenciais e, se estiverem certas, marca o acesso.

    Nunca diz se o que falhou foi o nome ou a palavra-passe: dizer "esse
    utilizador não existe" entregaria metade da resposta a quem tentasse
    adivinhar.
    """
    nome = (nome_utilizador or "").strip()
    utilizador = obter(nome) if nome else None

    if utilizador is None:
        # Deriva na mesma, para o tempo de resposta não revelar que a conta
        # não existe.
        seguranca.verificar(senha or "", seguranca.gerar_hash("inexistente"))
        eventos.publicar(eventos.SESSAO_FALHADA, origem="utilizadores", id=nome)
        return ResultadoAutenticacao(False, motivo=MotivoFalha.CREDENCIAIS)

    if utilizador.esta_bloqueado():
        restantes = max(
            1,
            int(
                (
                    datetime.fromisoformat(utilizador.bloqueado_ate) - datetime.now()
                ).total_seconds()
                // 60
            )
            + 1,
        )
        eventos.publicar(
            eventos.SESSAO_FALHADA,
            origem="utilizadores",
            id=utilizador.nome_utilizador,
            motivo="bloqueado",
        )
        return ResultadoAutenticacao(
            False, motivo=MotivoFalha.BLOQUEADO, minutos_restantes=restantes
        )

    with _conectar() as conexao:
        guardado = conexao.execute(
            "SELECT senha_hash FROM utilizadores WHERE id = ?", (utilizador.id,)
        ).fetchone()[0]

    if not seguranca.verificar(senha or "", guardado):
        tentativas = _registar_falha(utilizador)
        logger.warning(
            "Entrada recusada para %s (tentativa %d).", utilizador.nome_utilizador, tentativas
        )
        eventos.publicar(
            eventos.SESSAO_FALHADA,
            origem="utilizadores",
            id=utilizador.nome_utilizador,
            tentativas=tentativas,
        )
        return ResultadoAutenticacao(False, motivo=MotivoFalha.CREDENCIAIS)

    if not utilizador.ativo:
        eventos.publicar(
            eventos.SESSAO_FALHADA,
            origem="utilizadores",
            id=utilizador.nome_utilizador,
            motivo="inativo",
        )
        return ResultadoAutenticacao(False, motivo=MotivoFalha.INATIVO)

    novo_hash = (
        seguranca.gerar_hash(senha) if seguranca.precisa_de_rehash(guardado) else None
    )
    with _conectar() as conexao:
        if novo_hash:
            # Aproveita a entrada para subir o custo da derivação.
            conexao.execute(
                "UPDATE utilizadores SET senha_hash = ? WHERE id = ?",
                (novo_hash, utilizador.id),
            )
        conexao.execute(
            "UPDATE utilizadores SET ultimo_acesso = ?, tentativas_falhadas = 0,"
            " bloqueado_ate = NULL WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), utilizador.id),
        )

    atualizado = obter(utilizador.nome_utilizador)
    logger.info("Sessão iniciada: %s", utilizador.nome_utilizador)
    eventos.publicar(
        eventos.SESSAO_INICIADA,
        origem="utilizadores",
        id=utilizador.nome_utilizador,
        papel=utilizador.papel_nome,
    )
    return ResultadoAutenticacao(True, utilizador=atualizado)


def iniciar_sessao(utilizador: Utilizador) -> None:
    """Põe o utilizador autenticado como sessão corrente."""
    from core import permissoes

    permissoes.definir_sessao(
        utilizador.nome_utilizador, utilizador.papel_nome, persistir=False
    )


def terminar_sessao() -> None:
    """Encerra a sessão corrente."""
    from core import permissoes

    atual = permissoes.sessao().utilizador
    permissoes.terminar_sessao()
    eventos.publicar(eventos.SESSAO_TERMINADA, origem="utilizadores", id=atual)
