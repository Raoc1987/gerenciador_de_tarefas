"""A caixa de entrada: onde o que foi anunciado se lê.

A cadeia estava feita até ao penúltimo elo — tarefa, evento, métrica, painel,
modelo, previsão, **alerta** — e parava aí. Os alertas eram publicados no
barramento e uma regra de automação podia agir sobre eles, mas **não havia
sítio onde uma pessoa os lesse**. Um aviso que só existe no barramento é um
aviso que ninguém recebeu.

Este módulo é esse sítio. Guarda o que foi anunciado a cada pessoa, e o que
essa pessoa já leu.

Três decisões que fazem o resto:

**Uma notificação tem destinatário, e a caixa só sabe responder à da sessão.**
A vigilância corre com o âmbito de quem a desencadeou, por isso o que ela
conclui pode falar de dados que mais ninguém pode ver. Se este módulo
aceitasse um destinatário como argumento, a fuga estava a uma chamada de
distância — e mais tarde alguém escrevia essa chamada por engano. Não se
consegue vazar o que a API não sabe dizer.

**Guarda-se a chave de tradução e os parâmetros, nunca a frase.** O produto
fala três idiomas e o idioma muda em execução. "Há 15 tarefas atrasadas"
gravado em texto congelava a notificação no idioma do dia em que aconteceu —
e quem trocasse para inglês ficava com uma caixa metade em português.

**É uma caixa de correio, não um painel de estado.** Uma notificação diz o que
era verdade às 14:05, e isso continua a ter sido verdade às 14:05. Por isso
``analise.resolvido`` **não** apaga nem esconde nada: quem quer saber como as
coisas estão agora tem o painel, que é o sítio para essa pergunta. O custo é
real e fica dito — uma caixa por ler pode mostrar um alarme que já passou.

É um **Service** (ADR-0004): não tem interface, não tem domínio próprio, e
existe para ligar duas peças que não se conhecem. Ver ADR-0013.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.log import obter_logger

logger = obter_logger(__name__)

#: Quantas notificações se guardam por pessoa.
#:
#: Só se descartam **lidas**, e as mais antigas primeiro. O que ainda não foi
#: lido nunca é apagado para dar lugar a nada: uma caixa que deita fora avisos
#: por ler é pior do que uma caixa cheia, porque a pessoa não fica a saber.
LIMITE_POR_PESSOA = 200

#: Gravidades aceites. São as da análise, para a caixa não inventar um segundo
#: vocabulário para a mesma coisa.
NIVEIS = ("informacao", "positivo", "atencao", "critico")

NIVEL_PADRAO = "informacao"


@dataclass(frozen=True)
class Notificacao:
    """Uma coisa que foi anunciada a alguém."""

    id: int
    chave: str
    """Chave de tradução — a frase é montada quando for para mostrar."""

    parametros: Dict[str, Any] = field(default_factory=dict)
    nivel: str = NIVEL_PADRAO
    origem: str = ""
    """Quem a criou: ``alertas``, o id de um módulo, uma regra."""

    assunto: str = ""
    """Identificador estável do que ela é sobre, quando existe.

    É o que permite a quem cria não repetir o mesmo aviso. Vazio quer dizer
    "não há assunto", e nunca agrupa com nada.
    """

    criada_em: str = ""
    lida_em: Optional[str] = None

    @property
    def lida(self) -> bool:
        return self.lida_em is not None


# --------------------------------------------------------------- destinatário


def destinatario() -> str:
    """Quem está a ver a caixa: o utilizador da sessão.

    Não é um argumento de propósito. Ver a nota no topo do módulo.
    """
    from core import permissoes

    return str(permissoes.sessao().utilizador)


def _conectar():
    import banco_de_dados

    banco_de_dados.criar_tabela()
    return banco_de_dados.conectar()


_COLUNAS = "id, chave, parametros, nivel, origem, assunto, criada_em, lida_em"


def _de(linha) -> Notificacao:
    ident, chave, parametros, nivel, origem, assunto, criada_em, lida_em = linha
    try:
        valores = json.loads(parametros)
        if not isinstance(valores, dict):  # pragma: no cover - linha corrompida
            valores = {}
    except (TypeError, ValueError):  # pragma: no cover - linha corrompida
        logger.warning("Parâmetros ilegíveis na notificação %s.", ident)
        valores = {}
    return Notificacao(
        id=int(ident),
        chave=chave,
        parametros=valores,
        nivel=nivel,
        origem=origem,
        assunto=assunto,
        criada_em=criada_em,
        lida_em=lida_em,
    )


# ------------------------------------------------------------------- escrever


def criar(
    chave: str,
    nivel: str = NIVEL_PADRAO,
    origem: str = "",
    assunto: str = "",
    **parametros: Any,
) -> Optional[int]:
    """Anuncia alguma coisa a quem está em sessão. Devolve o ``id``.

    Args:
        chave: chave de tradução. Vazia é um erro de quem chama, e é recusada
            aqui em vez de dar uma linha em branco na caixa.
        nivel: um de :data:`NIVEIS`. Um nível desconhecido **não** rejeita a
            notificação — vira ``informacao`` e fica no log. Perder um aviso
            por causa de uma etiqueta errada seria trocar um problema pequeno
            por um grande.
        assunto: identificador do que ela é sobre, para quem cria poder
            perguntar depois se já o anunciou.

    Returns:
        O ``id`` da notificação, ou ``None`` se não foi possível guardá-la.
        **Nunca levanta por falha de escrita**: isto corre dentro de eventos
        publicados por outras operações, e falhar a notificar não pode fazer
        falhar a operação que deu origem ao aviso.
    """
    chave = str(chave or "").strip()
    if not chave:
        raise ValueError("Uma notificação precisa de uma chave de texto.")

    if nivel not in NIVEIS:
        logger.warning("Nível desconhecido em notificação %r: %r.", chave, nivel)
        nivel = NIVEL_PADRAO

    quem = destinatario()
    try:
        with _conectar() as conexao:
            cursor = conexao.execute(
                "INSERT INTO notificacoes "
                "(destinatario, chave, parametros, nivel, origem, assunto, criada_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    quem,
                    chave,
                    json.dumps(parametros, ensure_ascii=False, default=str),
                    nivel,
                    str(origem or ""),
                    str(assunto or ""),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            novo = int(cursor.lastrowid)
    except Exception:
        logger.exception("Falha ao guardar a notificação %r.", chave)
        return None

    _aparar()
    logger.info("Notificação para %s: %s (%s)", quem, chave, nivel)
    return novo


def _aparar() -> None:
    """Descarta as lidas mais antigas acima de :data:`LIMITE_POR_PESSOA`."""
    try:
        with _conectar() as conexao:
            conexao.execute(
                "DELETE FROM notificacoes WHERE id IN ("
                "  SELECT id FROM notificacoes"
                "   WHERE destinatario = ? AND lida_em IS NOT NULL"
                "   ORDER BY id DESC LIMIT -1 OFFSET ?"
                ")",
                (destinatario(), LIMITE_POR_PESSOA),
            )
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha ao aparar a caixa de notificações.")


def marcar_lida(ident: int) -> bool:
    """Marca uma como lida. Só as da própria sessão."""
    agora = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE notificacoes SET lida_em = ? "
            "WHERE id = ? AND destinatario = ? AND lida_em IS NULL",
            (agora, int(ident), destinatario()),
        )
        return cursor.rowcount > 0


def marcar_todas_lidas() -> int:
    """Marca como lidas todas as por ler desta sessão. Devolve quantas."""
    agora = datetime.now().isoformat(timespec="seconds")
    with _conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE notificacoes SET lida_em = ? "
            "WHERE destinatario = ? AND lida_em IS NULL",
            (agora, destinatario()),
        )
        return cursor.rowcount


def limpar_lidas() -> int:
    """Apaga as já lidas desta sessão. Devolve quantas.

    Não toca nas que estão por ler: apagar um aviso que ninguém viu é a única
    coisa que esta caixa nunca pode fazer.
    """
    with _conectar() as conexao:
        cursor = conexao.execute(
            "DELETE FROM notificacoes WHERE destinatario = ? AND lida_em IS NOT NULL",
            (destinatario(),),
        )
        return cursor.rowcount


# --------------------------------------------------------------------- ler


def listar(limite: int = 50, apenas_por_ler: bool = False) -> List[Notificacao]:
    """As notificações desta sessão, da mais recente para a mais antiga."""
    condicao = "destinatario = ?"
    parametros: List[Any] = [destinatario()]
    if apenas_por_ler:
        condicao += " AND lida_em IS NULL"
    parametros.append(max(0, int(limite)))

    with _conectar() as conexao:
        linhas = conexao.execute(
            f"SELECT {_COLUNAS} FROM notificacoes WHERE {condicao} "
            "ORDER BY id DESC LIMIT ?",
            parametros,
        ).fetchall()
    return [_de(linha) for linha in linhas]


def por_ler() -> int:
    """Quantas estão por ler nesta sessão.

    É o número do sino. **Nunca levanta**: um sino que rebenta leva a barra de
    topo com ele, e a barra de topo é a aplicação inteira.
    """
    try:
        with _conectar() as conexao:
            return int(
                conexao.execute(
                    "SELECT COUNT(*) FROM notificacoes "
                    "WHERE destinatario = ? AND lida_em IS NULL",
                    (destinatario(),),
                ).fetchone()[0]
            )
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha ao contar as notificações por ler.")
        return 0


def ja_anunciado(assunto: str) -> bool:
    """Se já existe uma notificação desta sessão sobre este assunto.

    Para quem cria não repetir. A vigilância tem a sua própria memória e não
    precisa disto; um módulo que anuncie por sua conta precisa.
    """
    assunto = str(assunto or "").strip()
    if not assunto:
        return False
    with _conectar() as conexao:
        linha = conexao.execute(
            "SELECT 1 FROM notificacoes WHERE destinatario = ? AND assunto = ? LIMIT 1",
            (destinatario(), assunto),
        ).fetchone()
    return linha is not None


# ------------------------------------------------------------------- ligação


def ativar() -> None:
    """Passa a escrever na caixa o que a vigilância anunciar.

    Só ``analise.alerta``. ``analise.resolvido`` é deliberadamente ignorado —
    ver a nota no topo do módulo.
    """
    from core import eventos

    if ativa():
        return
    eventos.subscrever(eventos.ANALISE_ALERTA, _ao_alertar, dono="notificacoes")
    logger.info("Caixa de notificações ligada à vigilância.")


def desativar() -> None:
    """Desliga a caixa do barramento."""
    from core import eventos

    eventos.barramento().cancelar_por_dono("notificacoes")


def ativa() -> bool:
    """Se a caixa está ligada ao barramento agora."""
    from core import eventos

    return any(i.dono == "notificacoes" for i in eventos.barramento().inscricoes())


#: Campos do evento que identificam o alerta e não são parâmetros do texto.
_NAO_SAO_PARAMETROS = ("id", "nivel", "tipo")


def _ao_alertar(evento) -> None:
    """Guarda um ``analise.alerta`` na caixa de quem está em sessão."""
    try:
        dados = dict(evento.dados)
        chave = str(dados.get("id") or "").strip()
        if not chave:  # pragma: no cover - evento mal formado
            logger.warning("Alerta sem id; não é possível notificar.")
            return
        parametros = {k: v for k, v in dados.items() if k not in _NAO_SAO_PARAMETROS}
        criar(
            chave,
            nivel=str(dados.get("nivel") or NIVEL_PADRAO),
            origem="alertas",
            assunto=chave,
            **parametros,
        )
    except Exception:
        # A vigilância corre a partir de eventos de tarefas. Uma falha a
        # notificar não pode impedir alguém de criar uma tarefa.
        logger.exception("Falha ao notificar a partir de um alerta.")
