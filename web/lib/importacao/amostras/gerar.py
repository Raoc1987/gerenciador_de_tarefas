"""Gera as bases de amostra com o código do PRÓPRIO desktop (src/).

As amostras não são escritas à mão: passam pelas migrações reais de
banco_de_dados.py, por isso têm o esquema exato que um utilizador tem no
disco. Correr a partir da raiz do repositório:

    python web/lib/importacao/amostras/gerar.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(RAIZ / "src"))


def base_nova(nome: str):
    pasta = Path(tempfile.mkdtemp())
    os.environ["GDT_DATA_DIR"] = str(pasta)
    import importlib
    import core.paths
    importlib.reload(core.paths)
    import banco_de_dados
    importlib.reload(banco_de_dados)
    banco_de_dados.criar_tabela()
    return banco_de_dados, Path(banco_de_dados.caminho_bd()), AQUI / nome


def pequena():
    bd, caminho, destino = base_nova("desktop-pequena.db")
    a = bd.adicionar_tarefa("Ligar ao fornecedor", "2026-09-28", criada_por="ana")
    bd.adicionar_tarefa("Preparar proposta para o cliente Norte — com acentuação: ç, ã, é", "2026-10-15", criada_por="bruno")
    c = bd.adicionar_tarefa("Fechar o mês", None, criada_por="ana")
    bd.adicionar_tarefa("Tarefa sem dono", "2026-10-02")
    bd.concluir_tarefa(c, True)
    with sqlite3.connect(caminho) as cx:
        cx.execute("INSERT INTO utilizadores (nome_utilizador, nome, senha_hash, papel, criado_em) "
                   "VALUES ('ana', 'Ana Silva', 'x', 'administrador', '2026-01-01T00:00:00')")
        cx.execute("INSERT INTO utilizadores (nome_utilizador, nome, senha_hash, papel, criado_em) "
                   "VALUES ('bruno', 'Bruno Costa', 'x', 'colaborador', '2026-01-01T00:00:00')")
        # Datas fixas, para os testes não dependerem do dia em que a amostra foi gerada.
        cx.execute("UPDATE tarefas SET criada_em = '2026-09-01T09:30:00'")
        cx.execute("UPDATE tarefas SET concluida_em = '2026-09-20T17:00:00' WHERE id = ?", (c,))
    destino.write_bytes(caminho.read_bytes())


def grande():
    """3000 tarefas e descrições longas: árvore B com vários níveis e overflow."""
    bd, caminho, destino = base_nova("desktop-grande.db")
    with sqlite3.connect(caminho) as cx:
        linhas = []
        for i in range(1, 3001):
            texto = f"Tarefa {i}"
            if i % 500 == 0:
                texto += " " + ("longa " * 2000)  # ~12 KB: passa por páginas de overflow
            linhas.append((texto, f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}", i % 3 == 0,
                           "2026-01-01T08:00:00", "2026-02-01T08:00:00" if i % 3 == 0 else None,
                           ["ana", "bruno", ""][i % 3]))
        cx.executemany(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, criada_em, concluida_em, criada_por)"
            " VALUES (?, ?, ?, ?, ?, ?)", linhas)
        cx.execute("DELETE FROM tarefas WHERE id = 7")  # um buraco, como na vida real
    destino.write_bytes(caminho.read_bytes())


if __name__ == "__main__":
    pequena()
    grande()
    for f in sorted(AQUI.glob("*.db")):
        print(f.name, f.stat().st_size, "bytes")
