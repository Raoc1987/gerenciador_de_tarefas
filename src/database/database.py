import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[2] / "tarefas.db"


def conectar(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conexao = sqlite3.connect(db_path)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabela(db_path: Path | str = DB_PATH) -> None:
    """Cria o esquema inicial sem alterar dados de instalações existentes."""
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS tarefas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    descricao TEXT DEFAULT '',
                    categoria TEXT DEFAULT 'Geral',
                    prioridade TEXT NOT NULL DEFAULT 'Media',
                    status TEXT NOT NULL DEFAULT 'Pendente',
                    data_limite TEXT,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    concluido_em TEXT
                )
                """
            )
            conexao.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_status ON tarefas(status)")
            conexao.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_data_limite ON tarefas(data_limite)")
            _garantir_colunas(conexao)
            _criar_catalogos(conexao)


def _garantir_colunas(conexao: sqlite3.Connection) -> None:
    """Aplica migrações pequenas sem apagar a base já existente."""
    colunas = {linha["name"] for linha in conexao.execute("PRAGMA table_info(tarefas)")}
    for nome, tipo in {
        "hora_limite": "TEXT",
        "lembrete_em": "TEXT",
        "lembrete_adiado_ate": "TEXT",
        "projeto_id": "INTEGER",
    }.items():
        if nome not in colunas:
            conexao.execute(f"ALTER TABLE tarefas ADD COLUMN {nome} {tipo}")


def _criar_catalogos(conexao: sqlite3.Connection) -> None:
    conexao.execute(
        """CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
        cor TEXT NOT NULL DEFAULT '#176BFF',
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conexao.execute(
        """CREATE TABLE IF NOT EXISTS projetos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
        descricao TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Ativo',
        cor TEXT NOT NULL DEFAULT '#176BFF',
        data_entrega TEXT,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conexao.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_projeto ON tarefas(projeto_id)")
    categorias_padrao = ("Geral", "Trabalho", "Estudo", "Pessoal", "Saude", "Financas")
    for nome in categorias_padrao:
        conexao.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (nome,))
    for linha in conexao.execute("SELECT DISTINCT categoria FROM tarefas WHERE TRIM(categoria) <> ''"):
        conexao.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (linha["categoria"],))


def adicionar_tarefa(titulo: str, descricao: str = "", categoria: str = "Geral", prioridade: str = "Media", data_limite: str | None = None, db_path: Path | str = DB_PATH, hora_limite: str | None = None, projeto_id: int | None = None) -> int:
    titulo_limpo = titulo.strip()
    if not titulo_limpo:
        raise ValueError("O título da tarefa é obrigatório.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            cursor = conexao.execute(
                """INSERT INTO tarefas (titulo, descricao, categoria, prioridade, data_limite, hora_limite, projeto_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (titulo_limpo, descricao.strip(), categoria.strip() or "Geral", prioridade, data_limite or None, hora_limite or None, projeto_id),
            )
            return int(cursor.lastrowid)


def buscar_tarefas(db_path: Path | str = DB_PATH, termo: str = "", status: str = "Todos", categoria: str = "Todas", data_inicio: str = "", data_fim: str = "", projeto_id: int | None = None) -> list[sqlite3.Row]:
    filtros: list[str] = []
    parametros: list[str] = []
    if termo:
        filtros.append("(LOWER(t.titulo) LIKE ? OR LOWER(t.categoria) LIKE ? OR LOWER(COALESCE(p.nome, '')) LIKE ?)")
        termo_like = f"%{termo.lower()}%"
        parametros.extend([termo_like, termo_like, termo_like])
    if status != "Todos":
        filtros.append("t.status = ?")
        parametros.append(status)
    if categoria != "Todas":
        filtros.append("t.categoria = ?")
        parametros.append(categoria)
    if data_inicio:
        filtros.append("t.data_limite IS NOT NULL AND date(t.data_limite) >= date(?)")
        parametros.append(data_inicio)
    if data_fim:
        filtros.append("t.data_limite IS NOT NULL AND date(t.data_limite) <= date(?)")
        parametros.append(data_fim)
    if projeto_id is not None:
        filtros.append("t.projeto_id = ?")
        parametros.append(projeto_id)
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    with closing(conectar(db_path)) as conexao:
        return list(conexao.execute(
            f"""SELECT t.id, t.titulo, t.descricao, t.categoria, t.prioridade, t.status,
            t.data_limite, t.hora_limite, t.projeto_id, p.nome AS projeto,
            t.criado_em, t.concluido_em, t.lembrete_em, t.lembrete_adiado_ate
            FROM tarefas t LEFT JOIN projetos p ON p.id = t.projeto_id {where}
            ORDER BY CASE t.status WHEN 'Pendente' THEN 0 ELSE 1 END,
            COALESCE(t.data_limite, '9999-12-31'), t.id DESC""", parametros))


def buscar_tarefa_por_id(tarefa_id: int, db_path: Path | str = DB_PATH) -> sqlite3.Row | None:
    with closing(conectar(db_path)) as conexao:
        return conexao.execute(
            """SELECT t.id, t.titulo, t.descricao, t.categoria, t.prioridade, t.status,
            t.data_limite, t.hora_limite, t.projeto_id, p.nome AS projeto,
            t.criado_em, t.concluido_em, t.lembrete_em, t.lembrete_adiado_ate
            FROM tarefas t LEFT JOIN projetos p ON p.id = t.projeto_id WHERE t.id = ?""", (tarefa_id,)).fetchone()


def atualizar_tarefa(tarefa_id: int, titulo: str, descricao: str = "", categoria: str = "Geral", prioridade: str = "Media", data_limite: str | None = None, db_path: Path | str = DB_PATH, hora_limite: str | None = None, projeto_id: int | None = None) -> None:
    titulo_limpo = titulo.strip()
    if not titulo_limpo:
        raise ValueError("O título da tarefa é obrigatório.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute(
                """UPDATE tarefas SET titulo = ?, descricao = ?, categoria = ?, prioridade = ?,
                data_limite = ?, hora_limite = ?, projeto_id = ?, lembrete_em = NULL, lembrete_adiado_ate = NULL WHERE id = ?""",
                (titulo_limpo, descricao.strip(), categoria.strip() or "Geral", prioridade, data_limite or None, hora_limite or None, projeto_id, tarefa_id))


def atualizar_status(tarefa_id: int, status: str, db_path: Path | str = DB_PATH) -> None:
    if status not in {"Pendente", "Concluida"}:
        raise ValueError("Status inválido.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute(
                """UPDATE tarefas SET status = ?, concluido_em =
                CASE WHEN ? = 'Concluida' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id = ?""", (status, status, tarefa_id))


def excluir_tarefa(tarefa_id: int, db_path: Path | str = DB_PATH) -> None:
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))


def listar_categorias(db_path: Path | str = DB_PATH) -> list[sqlite3.Row]:
    with closing(conectar(db_path)) as conexao:
        return list(conexao.execute(
            """SELECT c.id, c.nome, c.cor, COUNT(t.id) AS total_tarefas
            FROM categorias c LEFT JOIN tarefas t ON t.categoria = c.nome
            GROUP BY c.id, c.nome, c.cor ORDER BY c.nome COLLATE NOCASE"""))


def criar_categoria(nome: str, cor: str = "#176BFF", db_path: Path | str = DB_PATH) -> int:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome da categoria é obrigatório.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            try:
                cursor = conexao.execute("INSERT INTO categorias (nome, cor) VALUES (?, ?)", (nome_limpo, cor))
            except sqlite3.IntegrityError as erro:
                raise ValueError("Essa categoria já existe.") from erro
            return int(cursor.lastrowid)


def excluir_categoria(categoria_id: int, db_path: Path | str = DB_PATH) -> None:
    with closing(conectar(db_path)) as conexao:
        with conexao:
            categoria = conexao.execute("SELECT nome FROM categorias WHERE id = ?", (categoria_id,)).fetchone()
            if categoria is None:
                return
            em_uso = conexao.execute("SELECT COUNT(*) FROM tarefas WHERE categoria = ?", (categoria["nome"],)).fetchone()[0]
            if em_uso:
                raise ValueError("Não é possível excluir uma categoria que possui tarefas.")
            conexao.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))


def listar_projetos(db_path: Path | str = DB_PATH, apenas_ativos: bool = False) -> list[sqlite3.Row]:
    filtro = "WHERE p.status = 'Ativo'" if apenas_ativos else ""
    with closing(conectar(db_path)) as conexao:
        return list(conexao.execute(
            f"""SELECT p.id, p.nome, p.descricao, p.status, p.cor, p.data_entrega,
            p.criado_em, COUNT(t.id) AS total_tarefas,
            SUM(CASE WHEN t.status = 'Concluida' THEN 1 ELSE 0 END) AS tarefas_concluidas
            FROM projetos p LEFT JOIN tarefas t ON t.projeto_id = p.id
            {filtro}
            GROUP BY p.id, p.nome, p.descricao, p.status, p.cor, p.data_entrega, p.criado_em
            ORDER BY CASE p.status WHEN 'Ativo' THEN 0 WHEN 'Pausado' THEN 1 ELSE 2 END, p.nome COLLATE NOCASE"""))


def criar_projeto(nome: str, descricao: str = "", data_entrega: str | None = None, cor: str = "#176BFF", db_path: Path | str = DB_PATH) -> int:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome do projeto é obrigatório.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            try:
                cursor = conexao.execute(
                    "INSERT INTO projetos (nome, descricao, data_entrega, cor) VALUES (?, ?, ?, ?)",
                    (nome_limpo, descricao.strip(), data_entrega or None, cor),
                )
            except sqlite3.IntegrityError as erro:
                raise ValueError("Esse projeto já existe.") from erro
            return int(cursor.lastrowid)


def atualizar_projeto(projeto_id: int, nome: str, descricao: str, status: str, data_entrega: str | None, cor: str = "#176BFF", db_path: Path | str = DB_PATH) -> None:
    if status not in {"Ativo", "Pausado", "Concluido"}:
        raise ValueError("Status de projeto inválido.")
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome do projeto é obrigatório.")
    with closing(conectar(db_path)) as conexao:
        with conexao:
            try:
                conexao.execute(
                    """UPDATE projetos SET nome = ?, descricao = ?, status = ?, data_entrega = ?, cor = ?
                    WHERE id = ?""", (nome_limpo, descricao.strip(), status, data_entrega or None, cor, projeto_id))
            except sqlite3.IntegrityError as erro:
                raise ValueError("Esse projeto já existe.") from erro


def excluir_projeto(projeto_id: int, db_path: Path | str = DB_PATH) -> None:
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute("UPDATE tarefas SET projeto_id = NULL WHERE projeto_id = ?", (projeto_id,))
            conexao.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))


def listar_lembretes_devidos(agora: str, db_path: Path | str = DB_PATH) -> list[sqlite3.Row]:
    """Retorna tarefas pendentes cujo horário chegou e ainda não foram dispensadas."""
    with closing(conectar(db_path)) as conexao:
        return list(conexao.execute(
            """SELECT id, titulo, descricao, categoria, prioridade, status, data_limite, hora_limite
            FROM tarefas
            WHERE status = 'Pendente' AND data_limite IS NOT NULL AND hora_limite IS NOT NULL
              AND lembrete_em IS NULL
              AND (lembrete_adiado_ate IS NULL OR datetime(lembrete_adiado_ate) <= datetime(?))
              AND datetime(data_limite || ' ' || hora_limite) <= datetime(?)
            ORDER BY data_limite, hora_limite, id""", (agora, agora)))


def adiar_lembrete(tarefa_id: int, ate: str, db_path: Path | str = DB_PATH) -> None:
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute("UPDATE tarefas SET lembrete_adiado_ate = ? WHERE id = ?", (ate, tarefa_id))


def dispensar_lembrete(tarefa_id: int, quando: str, db_path: Path | str = DB_PATH) -> None:
    with closing(conectar(db_path)) as conexao:
        with conexao:
            conexao.execute("UPDATE tarefas SET lembrete_em = ?, lembrete_adiado_ate = NULL WHERE id = ?", (quando, tarefa_id))


def calcular_metricas(db_path: Path | str = DB_PATH) -> dict[str, int | float]:
    with closing(conectar(db_path)) as conexao:
        total = conexao.execute("SELECT COUNT(*) FROM tarefas").fetchone()[0]
        concluidas = conexao.execute("SELECT COUNT(*) FROM tarefas WHERE status = 'Concluida'").fetchone()[0]
        pendentes = conexao.execute("SELECT COUNT(*) FROM tarefas WHERE status = 'Pendente'").fetchone()[0]
        atrasadas = conexao.execute("""SELECT COUNT(*) FROM tarefas WHERE status = 'Pendente'
            AND data_limite IS NOT NULL AND date(data_limite) < date('now')""").fetchone()[0]
    taxa = round((concluidas / total) * 100, 1) if total else 0.0
    return {"total": total, "pendentes": pendentes, "concluidas": concluidas, "atrasadas": atrasadas, "taxa_conclusao": taxa}


def tarefas_por_categoria(db_path: Path | str = DB_PATH) -> list[tuple[str, int]]:
    with closing(conectar(db_path)) as conexao:
        linhas = conexao.execute("""SELECT categoria, COUNT(*) AS total FROM tarefas
            GROUP BY categoria ORDER BY total DESC, categoria""").fetchall()
    return [(linha["categoria"], linha["total"]) for linha in linhas]


def produtividade_semanal(db_path: Path | str = DB_PATH) -> list[tuple[str, int]]:
    with closing(conectar(db_path)) as conexao:
        linhas = conexao.execute("""SELECT strftime('%Y-W%W', concluido_em) AS semana, COUNT(*) AS total
            FROM tarefas WHERE status = 'Concluida' AND concluido_em IS NOT NULL
            GROUP BY semana ORDER BY semana DESC LIMIT 8""").fetchall()
    return [(linha["semana"], linha["total"]) for linha in reversed(linhas)]
