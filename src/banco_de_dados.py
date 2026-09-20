"""Camada de persistência (SQLite) das tarefas.

O banco vive no diretório de dados do utilizador (ver :mod:`core.paths`) e
nunca em ``Program Files``, para que a aplicação funcione sem privilégios de
administrador e sobreviva a atualizações.

O schema é versionado através de ``PRAGMA user_version``; as migrações são
aplicadas em ordem e são aditivas (nunca destrutivas).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

from core import eventos
from core.log import obter_logger
from core.paths import caminho_banco

logger = obter_logger(__name__)

#: Quem assina os eventos deste módulo na trilha de auditoria.
#:
#: Diz ``"database"`` porque era esse o nome do módulo quando as primeiras
#: linhas foram escritas, e uma trilha de auditoria não se reescreve: as
#: linhas já gravadas não mudam, e mudar as novas partia o histórico em duas
#: metades que não se conseguem consultar juntas. O nome do ficheiro é
#: assunto nosso; o valor guardado é um facto sobre o passado.
ORIGEM_DOS_EVENTOS = "database"

# Cada entrada é aplicada quando ``PRAGMA user_version`` for menor que o índice+1.
_MIGRACOES: List[Sequence[str]] = [
    # v1 — tabela de tarefas
    (
        """
        CREATE TABLE IF NOT EXISTS tarefas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao        TEXT    NOT NULL,
            data_vencimento  TEXT,
            concluida        INTEGER NOT NULL DEFAULT 0,
            criada_em        TEXT    NOT NULL
        )
        """,
    ),
    # v2 — registo dos plugins instalados (aditiva: não toca em `tarefas`)
    (
        """
        CREATE TABLE IF NOT EXISTS plugins (
            id            TEXT    PRIMARY KEY,
            version       TEXT    NOT NULL,
            enabled       INTEGER NOT NULL DEFAULT 0,
            installed_at  TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        )
        """,
    ),
    # v3 — quando a tarefa foi concluída.
    #
    # Sem isto, "concluídas por dia" não existe: só se sabe que a tarefa está
    # concluída, não quando. As linhas antigas ficam com NULL — a análise
    # trata-as como "data desconhecida" em vez de inventar uma.
    (
        "ALTER TABLE tarefas ADD COLUMN concluida_em TEXT",
        "CREATE INDEX IF NOT EXISTS idx_tarefas_concluida_em ON tarefas (concluida_em)",
        "CREATE INDEX IF NOT EXISTS idx_tarefas_vencimento ON tarefas (data_vencimento)",
    ),
    # v4 — trilha de auditoria (aditiva; ver core/auditoria.py)
    (
        """
        CREATE TABLE IF NOT EXISTS auditoria (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            momento     TEXT NOT NULL,
            evento      TEXT NOT NULL,
            utilizador  TEXT NOT NULL DEFAULT '',
            alvo        TEXT NOT NULL DEFAULT '',
            detalhe     TEXT NOT NULL DEFAULT '',
            origem      TEXT NOT NULL DEFAULT ''
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_auditoria_momento ON auditoria (momento)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_evento ON auditoria (evento)",
    ),
    # v5 — contas de utilizador (ver core/utilizadores.py).
    #
    # COLLATE NOCASE no nome: "Ana" e "ana" são a mesma pessoa, e permitir as
    # duas contas seria um convite a enganos. A senha guardada é o resultado
    # de uma derivação lenta, nunca a palavra-passe.
    (
        """
        CREATE TABLE IF NOT EXISTS utilizadores (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_utilizador     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            nome                TEXT    NOT NULL DEFAULT '',
            senha_hash          TEXT    NOT NULL,
            papel               TEXT    NOT NULL,
            ativo               INTEGER NOT NULL DEFAULT 1,
            criado_em           TEXT    NOT NULL,
            ultimo_acesso       TEXT,
            tentativas_falhadas INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate       TEXT
        )
        """,
    ),
    # v6 — quem criou a tarefa.
    #
    # As linhas anteriores ficam com "" (sem dono conhecido): foram criadas
    # antes de existirem contas, e inventar-lhes um dono seria escrever no
    # banco uma coisa que nunca aconteceu.
    (
        "ALTER TABLE tarefas ADD COLUMN criada_por TEXT NOT NULL DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS idx_tarefas_criada_por ON tarefas (criada_por)",
    ),
    # v7 — estrutura da organização (ver core/organizacao.py).
    #
    # Uma árvore só, com `tipo` a dizer o que cada nó é, em vez de uma tabela
    # por nível. As empresas não são todas iguais — há divisões, regiões,
    # filiais — e com três tabelas cada formato novo seria uma migração. Aqui
    # é uma linha. A travessia também se escreve uma vez só.
    #
    # Aditiva e vazia: quem não usa estrutura nenhuma não nota diferença.
    (
        """
        CREATE TABLE IF NOT EXISTS unidades (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT    NOT NULL,
            tipo       TEXT    NOT NULL,
            pai_id     INTEGER REFERENCES unidades(id),
            ativa      INTEGER NOT NULL DEFAULT 1,
            criada_em  TEXT    NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_unidades_pai ON unidades (pai_id)",
    ),
    # v8 — a que unidade pertencem as contas e as tarefas.
    #
    # A unidade da tarefa é gravada quando ela é criada, e não deduzida do
    # departamento atual de quem a criou. Se alguém mudar de departamento, o
    # trabalho que fez continua a contar para onde foi feito — mudá-lo de
    # sítio retroativamente seria reescrever o passado.
    #
    # NULL em ambas é o estado normal de quem não usa estrutura nenhuma.
    (
        "ALTER TABLE utilizadores ADD COLUMN unidade_id INTEGER REFERENCES unidades(id)",
        "ALTER TABLE tarefas ADD COLUMN unidade_id INTEGER REFERENCES unidades(id)",
        "CREATE INDEX IF NOT EXISTS idx_tarefas_unidade ON tarefas (unidade_id)",
    ),
    # v9 — regras de automação (ver src/regras/).
    #
    # As condições e as ações ficam em JSON: são listas de tamanho variável e
    # de forma própria de cada ação, e normalizá-las em tabelas daria três
    # junções para ler uma regra que nunca se consulta por partes.
    #
    # Aditiva e vazia: quem não escrever regra nenhuma não nota.
    (
        """
        CREATE TABLE IF NOT EXISTS regras (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT    NOT NULL,
            evento     TEXT    NOT NULL,
            condicoes  TEXT    NOT NULL DEFAULT '[]',
            acoes      TEXT    NOT NULL DEFAULT '[]',
            ativa      INTEGER NOT NULL DEFAULT 1,
            criada_em  TEXT    NOT NULL,
            criada_por TEXT    NOT NULL DEFAULT ''
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_regras_evento ON regras (evento)",
    ),
    # v10 — o que a vigilância já avisou (ver src/alertas.py).
    #
    # Sem isto, cada arranque voltaria a anunciar as mesmas conclusões, e uma
    # regra ligada a elas criaria as mesmas tarefas outra vez. Um alerta que
    # se repete é um alerta que se deixa de ler.
    (
        """
        CREATE TABLE IF NOT EXISTS alertas_vistos (
            chave     TEXT PRIMARY KEY,
            nivel     TEXT NOT NULL,
            visto_em  TEXT NOT NULL
        )
        """,
    ),
    # v11 — o valor antes e depois de uma alteracao auditada.
    #
    # A trilha ja dizia que alguem mudou o papel de uma conta; nao dizia de
    # que papel para que papel. Numa auditoria a serio e essa a pergunta.
    #
    # JSON em vez de colunas: os campos mudam conforme o evento, e uma tabela
    # de pares seria uma juncao para ler uma linha que nunca se consulta por
    # partes. As linhas antigas ficam com objetos vazios, que e a verdade --
    # nao se sabe o que estava la antes.
    (
        "ALTER TABLE auditoria ADD COLUMN antes TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE auditoria ADD COLUMN depois TEXT NOT NULL DEFAULT '{}'",
    ),
    # v12 -- de quem e cada plugin instalado, e o que a aplicacao la pos.
    #
    # Sem isto nao ha maneira de distinguir "este plugin veio dentro da
    # aplicacao e esta por atualizar" de "o utilizador instalou esta versao e
    # nao quer outra" -- e a semeadura, na duvida, nao tocava em nada. O
    # resultado era um plugin embutido instalado uma vez e nunca mais
    # corrigido (ADR-0006).
    #
    # As linhas antigas ficam com '' nas duas colunas: e a verdade, nao se
    # sabe. A primeira semeadura depois da atualizacao adota-as.
    (
        "ALTER TABLE plugins ADD COLUMN proveniencia TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE plugins ADD COLUMN impressao TEXT NOT NULL DEFAULT ''",
    ),
    # v13 -- a caixa de notificacoes, e o destinatario do que a vigilancia ja
    # anunciou (ver src/notificacoes.py e ADR-0013).
    #
    # `alertas_vistos` era global: uma chave, uma linha. Com duas empresas isso
    # e um defeito medido, nao uma hipotese -- quem entrasse a seguir
    # encontrava a chave de outra pessoa em falta no seu proprio ambito,
    # anunciava `analise.resolvido` por um problema que continuava por
    # resolver, e apagava a memoria do primeiro. A memoria passa a ser de quem
    # foi avisado, que e o que ela sempre quis dizer.
    #
    # As linhas antigas ficam com destinatario '' -- nao se sabe a quem foram
    # anunciadas, e inventar um dono seria escrever no banco uma coisa que
    # nunca aconteceu. O efeito e o mesmo de `esquecer_tudo`, que ja esta
    # documentado: cada pessoa volta a ser avisada uma vez do que ainda for
    # verdade. Nao se apaga nada.
    (
        """
        CREATE TABLE IF NOT EXISTS notificacoes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            destinatario  TEXT    NOT NULL,
            chave         TEXT    NOT NULL,
            parametros    TEXT    NOT NULL DEFAULT '{}',
            nivel         TEXT    NOT NULL DEFAULT 'informacao',
            origem        TEXT    NOT NULL DEFAULT '',
            assunto       TEXT    NOT NULL DEFAULT '',
            criada_em     TEXT    NOT NULL,
            lida_em       TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_notificacoes_caixa "
        "ON notificacoes (destinatario, lida_em, id)",
        """
        CREATE TABLE IF NOT EXISTS alertas_vistos_v13 (
            destinatario  TEXT NOT NULL DEFAULT '',
            chave         TEXT NOT NULL,
            nivel         TEXT NOT NULL,
            visto_em      TEXT NOT NULL,
            PRIMARY KEY (destinatario, chave)
        )
        """,
        "INSERT INTO alertas_vistos_v13 (destinatario, chave, nivel, visto_em) "
        "SELECT '', chave, nivel, visto_em FROM alertas_vistos",
        "DROP TABLE alertas_vistos",
        "ALTER TABLE alertas_vistos_v13 RENAME TO alertas_vistos",
    ),
]

#: Colunas devolvidas por :func:`buscar_tarefas` — contrato estável de que a
#: interface e os plugins dependem. Campos novos entram em
#: :func:`buscar_tarefas_completas`, para não partir quem desempacota 5 valores.
COLUNAS_TAREFA = "id, descricao, data_vencimento, concluida, criada_em"
COLUNAS_TAREFA_COMPLETA = COLUNAS_TAREFA + ", concluida_em, criada_por"

#: Dono usado pelas tarefas criadas antes de existirem contas.
SEM_DONO = ""


def _clausula_de_dono(
    dono: Optional[str],
    unidades: Optional[Sequence[int]] = None,
    empresa: Optional[Sequence[int]] = None,
) -> tuple:
    """Condição SQL e parâmetros para o âmbito de quem está a ver.

    ``dono=None`` significa "não filtrar por dono". Quem pede as suas tarefas
    vê também as que não têm dono: são anteriores às contas e não pertencem a
    mais ninguém.

    ``unidades`` alarga o âmbito às tarefas dessas unidades — é assim que um
    chefe de departamento vê o trabalho da sua equipa além do seu. A relação
    é **OU**: as minhas *ou* as da minha unidade. Uma lista vazia não alarga
    nada, que é o que acontece a quem não tem lugar na estrutura.

    ``empresa`` **estreita**, e é a única aqui que o faz: limita o que se vê
    às unidades da empresa de quem está em sessão. Aplica-se a quem vê tudo,
    que é precisamente quem, sem isto, veria as tarefas de todas as empresas
    da instalação.

    As tarefas **sem unidade** ficam sempre dentro: são anteriores à
    estrutura e não pertencem a empresa nenhuma. Sem esta exceção, criar a
    segunda empresa fazia desaparecer o histórico inteiro do ecrã de toda a
    gente — o dado continuaria lá, mas ninguém acreditaria nisso.

    Quem decide o que vai aqui dentro é :mod:`tarefas_servico`; o
    armazenamento só sabe montar a condição.
    """
    partes: List[str] = []
    parametros: List = []

    if dono is not None:
        condicao = "(criada_por = ? OR criada_por = ?)"
        parametros.extend([dono, SEM_DONO])
        if unidades:
            marcadores = ", ".join("?" for _ in unidades)
            condicao = f"({condicao} OR unidade_id IN ({marcadores}))"
            parametros.extend(unidades)
        partes.append(condicao)

    if empresa:
        marcadores = ", ".join("?" for _ in empresa)
        partes.append(f"(unidade_id IN ({marcadores}) OR unidade_id IS NULL)")
        parametros.extend(empresa)

    if not partes:
        return "", []
    return " AND ".join(partes), parametros


def caminho_bd() -> Path:
    """Caminho do arquivo de banco de dados em uso."""
    return caminho_banco()


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Abre uma conexão com commit automático e fecho garantido."""
    conexao = sqlite3.connect(caminho_bd())
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _aplicar_migracoes(conexao: sqlite3.Connection) -> None:
    versao_atual = conexao.execute("PRAGMA user_version").fetchone()[0]
    for indice, comandos in enumerate(_MIGRACOES, start=1):
        if versao_atual >= indice:
            continue
        logger.info("Aplicando migração de banco v%d", indice)
        for comando in comandos:
            conexao.execute(comando)
        conexao.execute(f"PRAGMA user_version = {indice}")
    conexao.commit()


#: A versão de esquema que esta build sabe ler e escrever.
#:
#: Um banco com uma versão **maior** veio de uma aplicação mais recente e não
#: pode ser aberto aqui: as migrações só andam para a frente, e ler um esquema
#: do futuro é ler colunas que não se conhecem.
VERSAO_ESQUEMA = len(_MIGRACOES)


def versao_do_esquema(caminho: Optional[Path] = None) -> int:
    """Versão de esquema de um banco (``0`` se ainda não existir).

    Args:
        caminho: outro ficheiro que não o em uso — para inspecionar o banco
            que vem dentro de uma cópia de segurança antes de lhe tocar.
    """
    alvo = Path(caminho) if caminho is not None else caminho_bd()
    if not alvo.exists():
        return 0
    conexao = sqlite3.connect(alvo)
    try:
        return int(conexao.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conexao.close()


def copiar_para(destino: Path) -> Path:
    """Escreve uma cópia consistente do banco em ``destino``.

    Usa a API de cópia do próprio SQLite em vez de copiar o ficheiro: a cópia
    do ficheiro pode apanhar uma escrita a meio e produzir um banco que só dá
    erro no dia em que for preciso.
    """
    criar_tabela()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    origem = sqlite3.connect(caminho_bd())
    copia = sqlite3.connect(destino)
    try:
        with copia:
            origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    return destino


def criar_tabela() -> None:
    """Garante que o banco existe e está no schema mais recente."""
    with conectar() as conexao:
        _aplicar_migracoes(conexao)


def adicionar_tarefa(
    descricao: str,
    data_vencimento: Optional[str] = None,
    criada_por: str = SEM_DONO,
    unidade_id: Optional[int] = None,
) -> int:
    """Insere uma tarefa e devolve o seu ``id``.

    Args:
        criada_por: quem a criou. Quem decide isto é a camada de serviço
            (:mod:`tarefas_servico`), não o armazenamento.
        unidade_id: a unidade a que o trabalho pertence, no momento em que é
            criado. Fica gravada: se a pessoa mudar de departamento amanhã,
            isto continua a contar para onde foi feito.

    Raises:
        ValueError: se a descrição estiver vazia.
    """
    descricao = (descricao or "").strip()
    if not descricao:
        raise ValueError("A descrição da tarefa não pode estar vazia.")

    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, criada_em,"
            " criada_por, unidade_id) VALUES (?, ?, 0, ?, ?, ?)",
            (
                descricao,
                data_vencimento,
                datetime.now().isoformat(timespec="seconds"),
                criada_por or SEM_DONO,
                unidade_id,
            ),
        )
        tarefa_id = int(cursor.lastrowid)

    eventos.publicar(
        eventos.TAREFA_CRIADA,
        origem=ORIGEM_DOS_EVENTOS,
        id=tarefa_id,
        descricao=descricao,
        data_vencimento=data_vencimento,
        criada_por=criada_por or SEM_DONO,
    )
    return tarefa_id


def buscar_tarefas(
    incluir_concluidas: bool = True,
    de: Optional[str] = None,
    unidades: Optional[Sequence[int]] = None,
    empresa: Optional[Sequence[int]] = None,
) -> List[tuple]:
    """Tarefas como tuplas ``(id, descrição, vencimento, concluída, criada_em)``.

    O formato de cinco colunas é contrato da interface e dos plugins; campos
    novos entram em :func:`buscar_tarefas_completas`.

    Args:
        de: se indicado, só as tarefas desse dono (e as sem dono).
    """
    condicoes = []
    parametros: List = []
    if not incluir_concluidas:
        condicoes.append("concluida = 0")
    clausula, valores = _clausula_de_dono(de, unidades, empresa)
    if clausula:
        condicoes.append(clausula)
        parametros.extend(valores)

    consulta = f"SELECT {COLUNAS_TAREFA} FROM tarefas"
    if condicoes:
        consulta += " WHERE " + " AND ".join(condicoes)
    consulta += " ORDER BY concluida ASC, id ASC"
    with conectar() as conexao:
        return conexao.execute(consulta, parametros).fetchall()


def dono_de(tarefa_id: int) -> Optional[str]:
    """Quem criou a tarefa (``""`` se não se sabe), ou ``None`` se não existe."""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT criada_por FROM tarefas WHERE id = ?", (tarefa_id,)
        ).fetchone()
    return linha[0] if linha else None


def unidade_de(tarefa_id: int) -> Optional[int]:
    """A unidade a que a tarefa pertence, ou ``None``."""
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT unidade_id FROM tarefas WHERE id = ?", (tarefa_id,)
        ).fetchone()
    return linha[0] if linha else None


def obter_tarefa(tarefa_id: int) -> Optional[tuple]:
    """Devolve uma tarefa pelo ``id``, ou ``None`` se não existir."""
    with conectar() as conexao:
        return conexao.execute(
            "SELECT id, descricao, data_vencimento, concluida, criada_em"
            " FROM tarefas WHERE id = ?",
            (tarefa_id,),
        ).fetchone()


def concluir_tarefa(tarefa_id: int, concluida: bool = True) -> bool:
    """Marca (ou desmarca) uma tarefa como concluída. Devolve se algo mudou."""
    momento = datetime.now().isoformat(timespec="seconds") if concluida else None
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE tarefas SET concluida = ?, concluida_em = ? WHERE id = ?",
            (1 if concluida else 0, momento, tarefa_id),
        )
        mudou = cursor.rowcount > 0

    if mudou:
        eventos.publicar(
            eventos.TAREFA_CONCLUIDA if concluida else eventos.TAREFA_REABERTA,
            origem=ORIGEM_DOS_EVENTOS,
            id=tarefa_id,
        )
    return mudou


def remover_tarefa(tarefa_id: int) -> bool:
    """Remove uma tarefa. Devolve ``True`` se a tarefa existia."""
    with conectar() as conexao:
        cursor = conexao.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))
        removida = cursor.rowcount > 0

    if removida:
        eventos.publicar(eventos.TAREFA_REMOVIDA, origem=ORIGEM_DOS_EVENTOS, id=tarefa_id)
    return removida


def buscar_tarefas_completas(
    de: Optional[str] = None,
    unidades: Optional[Sequence[int]] = None,
    empresa: Optional[Sequence[int]] = None,
) -> List[tuple]:
    """Tarefas com todas as colunas, incluindo ``concluida_em`` e ``criada_por``.

    Usada pela camada de analitica. :func:`buscar_tarefas` mantém o formato de
    cinco colunas de que a interface e os plugins dependem.
    """
    consulta = f"SELECT {COLUNAS_TAREFA_COMPLETA} FROM tarefas"
    clausula, parametros = _clausula_de_dono(de, unidades, empresa)
    if clausula:
        consulta += " WHERE " + clausula
    consulta += " ORDER BY id ASC"
    with conectar() as conexao:
        return conexao.execute(consulta, parametros).fetchall()


def tarefas_por_data(
    data_iso: str,
    de: Optional[str] = None,
    unidades: Optional[Sequence[int]] = None,
    empresa: Optional[Sequence[int]] = None,
) -> List[tuple]:
    """Tarefas cujo vencimento é exatamente ``data_iso`` (``AAAA-MM-DD``)."""
    consulta = f"SELECT {COLUNAS_TAREFA} FROM tarefas WHERE data_vencimento = ?"
    parametros: List = [data_iso]
    clausula, valores = _clausula_de_dono(de, unidades, empresa)
    if clausula:
        consulta += " AND " + clausula
        parametros.extend(valores)
    consulta += " ORDER BY concluida ASC, id ASC"
    with conectar() as conexao:
        return conexao.execute(consulta, parametros).fetchall()
