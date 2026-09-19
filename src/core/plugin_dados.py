"""Armazenamento privado de um plugin.

Um módulo de negócio — Estoque, RH, Financeiro — precisa de tabelas próprias.
Dar-lhe acesso ao banco da aplicação seria voltar ao monólito: bastava um
``DROP TABLE`` mal escrito, ou uma migração de um plugin de terceiros, para
levar as tarefas de alguém.

Por isso **cada plugin tem o seu ficheiro SQLite**, na sua área de dados:

* não alcança os dados da aplicação nem os de outro plugin — é outro ficheiro,
  outra ligação, e o caminho é derivado do id, não recebido;
* remover o plugin com os dados remove-o inteiro, sem deixar tabelas órfãs no
  banco principal;
* o esquema do plugin evolui ao ritmo dele, com o seu próprio
  ``PRAGMA user_version``;
* um plugin que nunca guarda nada nunca cria ficheiro nenhum.

Isto não é uma permissão a pedir: são os dados do próprio plugin.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, List, Sequence, Tuple

from core.log import obter_logger

logger = obter_logger(__name__)

NOME_FICHEIRO = "dados.sqlite3"


class EsquemaInconsistenteError(Exception):
    """Uma migração que reconstrói tabelas deixou referências penduradas."""

    chave_mensagem = "plugin_esquema_inconsistente"


class ArmazenamentoPlugin:
    """Banco privado de um plugin.

    Obtido em :attr:`~core.plugin_api.ContextoPlugin.dados`; um plugin não o
    constrói nem escolhe onde fica.

    Example:
        >>> dados = contexto.dados
        >>> dados.migrar(1, "CREATE TABLE itens (id INTEGER PRIMARY KEY, nome TEXT)")
        >>> dados.executar("INSERT INTO itens (nome) VALUES (?)", ("Parafuso",))
        >>> dados.consultar("SELECT nome FROM itens")
        [('Parafuso',)]
    """

    def __init__(self, plugin_id: str, diretorio: Path) -> None:
        self._plugin_id = plugin_id
        self._caminho = Path(diretorio) / NOME_FICHEIRO

    @property
    def caminho(self) -> Path:
        """Onde o ficheiro fica. Pode ainda não existir."""
        return self._caminho

    @property
    def existe(self) -> bool:
        """Se o plugin já guardou alguma coisa."""
        return self._caminho.exists()

    @contextmanager
    def conectar(self, chaves: bool = True) -> Iterator[sqlite3.Connection]:
        """Ligação com commit automático e rollback em caso de erro.

        Para quando várias escritas têm de acontecer juntas ou nenhuma.

        A transação é aberta **explicitamente**. O ``sqlite3`` do Python, por
        omissão, só abre uma para INSERT/UPDATE/DELETE: um ``CREATE TABLE`` ou
        ``ALTER TABLE`` corria fora dela e sobrevivia ao rollback. Numa
        migração de plugin isso é grave — o esquema ficava meio aplicado com a
        versão para trás, e o passo voltava a correr, a falhar, para sempre.
        O SQLite suporta DDL transacional; é só preciso pedir-lho.

        Args:
            chaves: se as chaves estrangeiras ficam ligadas. Desligá-las só
                faz sentido para reconstruir uma tabela — ver
                :meth:`migrar`. O ``PRAGMA`` é dado **antes** do ``BEGIN``,
                porque dentro de uma transação é ignorado sem se queixar.
        """
        conexao = sqlite3.connect(self._caminho, isolation_level=None)
        conexao.execute(f"PRAGMA foreign_keys = {'ON' if chaves else 'OFF'}")
        conexao.execute("BEGIN")
        try:
            yield conexao
            conexao.execute("COMMIT")
        except Exception:
            conexao.execute("ROLLBACK")
            raise
        finally:
            if not chaves:
                # A ligação vai fechar a seguir, mas deixá-la como se
                # encontrou é o hábito que evita a surpresa no dia em que
                # alguém a reutilizar.
                try:
                    conexao.execute("PRAGMA foreign_keys = ON")
                except sqlite3.Error:  # pragma: no cover - ligação já morta
                    pass
            conexao.close()

    # ------------------------------------------------------------- esquema

    def versao(self) -> int:
        """Versão do esquema deste plugin (``0`` se ainda não há nada)."""
        if not self.existe:
            return 0
        with self.conectar() as conexao:
            return int(conexao.execute("PRAGMA user_version").fetchone()[0])

    def migrar(
        self, versao: int, *instrucoes: str, reconstroi_tabelas: bool = False
    ) -> bool:
        """Aplica um passo de esquema, uma única vez.

        Chame-o em :meth:`~core.plugin_api.Plugin.inicializar`, uma vez por
        versão e sempre por ordem crescente — tal como a aplicação faz com o
        seu próprio esquema. Um passo já aplicado é ignorado, por isso pode
        ficar no código para sempre.

        As instruções de um passo correm todas ou nenhuma.

        Args:
            versao: número do passo, a partir de 1.
            instrucoes: os comandos SQL desse passo.
            reconstroi_tabelas: ver abaixo. Só para quem **substitui** uma
                tabela; um passo normal não precisa disto e não o deve pedir.

        Returns:
            ``True`` se o passo foi aplicado agora, ``False`` se já o estava.

        Raises:
            ValueError: se ``versao`` não for um inteiro positivo.
            EsquemaInconsistenteError: se um passo com
                ``reconstroi_tabelas`` deixar referências penduradas. Nesse
                caso **nada é gravado**.

        **Porque é que reconstruir precisa de um modo próprio.**

        O SQLite não sabe tirar uma restrição de uma tabela: para mudar um
        ``UNIQUE`` é preciso criar a tabela nova, copiar as linhas, apagar a
        antiga e renomear. Com chaves estrangeiras ligadas, apagar uma tabela
        que tem filhos falha — e ``PRAGMA foreign_keys = OFF`` **é ignorado
        em silêncio dentro de uma transação**, que é onde uma migração corre.

        Foi medido, não suposto: sem este modo, um plugin cujo esquema tenha
        uma chave estrangeira **não consegue mudar uma tabela pai**. E não é
        um caso raro — é o que acontece à primeira vez que um módulo precisa
        de acrescentar uma coluna a uma chave única.

        O que este modo faz é o procedimento que a documentação do SQLite
        recomenda: desliga as chaves **antes** de abrir a transação, corre o
        passo, e **verifica** com ``PRAGMA foreign_key_check`` antes de
        gravar. Se ficou alguma referência pendurada, desfaz tudo — um
        esquema partido é pior do que uma migração que não correu.
        """
        if not isinstance(versao, int) or versao < 1:
            raise ValueError("A versão do esquema começa em 1.")

        with self.conectar(chaves=not reconstroi_tabelas) as conexao:
            atual = int(conexao.execute("PRAGMA user_version").fetchone()[0])
            if atual >= versao:
                return False
            for instrucao in instrucoes:
                conexao.execute(instrucao)

            if reconstroi_tabelas:
                penduradas = conexao.execute("PRAGMA foreign_key_check").fetchall()
                if penduradas:
                    # O ``raise`` faz o ``conectar`` desfazer tudo.
                    raise EsquemaInconsistenteError(
                        f"O passo {versao} do plugin {self._plugin_id} deixou "
                        f"{len(penduradas)} referência(s) pendurada(s); nada foi gravado."
                    )

            conexao.execute(f"PRAGMA user_version = {int(versao)}")
        logger.info(
            "Plugin %s: esquema na versão %d%s",
            self._plugin_id,
            versao,
            " (tabelas reconstruídas)" if reconstroi_tabelas else "",
        )
        return True

    # -------------------------------------------------------------- acesso

    def executar(self, sql: str, parametros: Sequence[Any] = ()) -> int:
        """Escreve. Devolve o ``rowid`` do INSERT, ou as linhas afetadas."""
        with self.conectar() as conexao:
            cursor = conexao.execute(sql, tuple(parametros))
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def executar_muitos(self, sql: str, linhas: Sequence[Sequence[Any]]) -> int:
        """A mesma instrução para várias linhas, tudo ou nada."""
        with self.conectar() as conexao:
            return conexao.executemany(sql, [tuple(l) for l in linhas]).rowcount

    def consultar(self, sql: str, parametros: Sequence[Any] = ()) -> List[Tuple]:
        """Lê. Devolve lista vazia enquanto o plugin não tiver guardado nada."""
        if not self.existe:
            return []
        with self.conectar() as conexao:
            return conexao.execute(sql, tuple(parametros)).fetchall()

    def consultar_um(self, sql: str, parametros: Sequence[Any] = ()) -> Any:
        """A primeira linha, ou ``None``."""
        linhas = self.consultar(sql, parametros)
        return linhas[0] if linhas else None

    def __repr__(self) -> str:  # pragma: no cover - apoio a depuração
        return f"<ArmazenamentoPlugin {self._plugin_id} em {self._caminho}>"
