"""Regras do inventário, sem interface e sem saber que é um plugin.

Separado de ``plugin.py`` de propósito: as regras de um domínio de negócio não
devem depender de Tkinter nem do ciclo de vida de plugins. Recebe um
armazenamento (:class:`~core.plugin_dados.ArmazenamentoPlugin`) e trabalha.

O que este módulo guarda:

* **itens** — o que existe, com a quantidade atual e o mínimo desejado;
* **movimentos** — o histórico de entradas e saídas.

A quantidade do item é derivada dos movimentos, não escrita à mão. Guardar um
total que alguém pode editar sem deixar rasto é como ter uma conta bancária
sem extrato: quando os números não batem certo, não há por onde começar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

#: Passos de esquema deste módulo. Correm uma vez e ficam aqui para sempre.
MIGRACOES = (
    (
        1,
        """
        CREATE TABLE itens (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            nome      TEXT    NOT NULL,
            unidade   TEXT    NOT NULL DEFAULT 'un',
            minimo    INTEGER NOT NULL DEFAULT 0,
            ativo     INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT    NOT NULL
        )
        """,
        """
        CREATE TABLE movimentos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id    INTEGER NOT NULL REFERENCES itens(id),
            tipo       TEXT    NOT NULL,
            quantidade INTEGER NOT NULL,
            motivo     TEXT    NOT NULL DEFAULT '',
            quem       TEXT    NOT NULL DEFAULT '',
            momento    TEXT    NOT NULL
        )
        """,
        "CREATE INDEX idx_movimentos_item ON movimentos (item_id)",
    ),
)

#: Passos que **substituem** uma tabela, e por isso correm em modo próprio.
#:
#: O ``UNIQUE (codigo)`` da v1 impedia duas empresas de terem um item com o
#: mesmo código — e num inventário isso é comum, porque os códigos vêm dos
#: fornecedores. Passa a ``UNIQUE (empresa, codigo)``.
#:
#: O SQLite não sabe tirar uma restrição: é preciso criar a tabela nova,
#: copiar, apagar a antiga e renomear. Com uma chave estrangeira a apontar
#: para ``itens``, isso só é possível com ``reconstroi_tabelas=True`` — ver
#: :meth:`core.plugin_dados.ArmazenamentoPlugin.migrar`.
#:
#: As linhas que já existiam ficam com ``empresa = NULL``: são anteriores à
#: estrutura e não pertencem a empresa nenhuma, por isso continuam visíveis a
#: toda a gente. É a mesma regra que as tarefas seguem.
RECONSTRUCOES = (
    (
        2,
        """
        CREATE TABLE itens_novo (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa   INTEGER,
            codigo    TEXT    NOT NULL COLLATE NOCASE,
            nome      TEXT    NOT NULL,
            unidade   TEXT    NOT NULL DEFAULT 'un',
            minimo    INTEGER NOT NULL DEFAULT 0,
            ativo     INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT    NOT NULL,
            UNIQUE (empresa, codigo)
        )
        """,
        """
        INSERT INTO itens_novo
            (id, empresa, codigo, nome, unidade, minimo, ativo, criado_em)
        SELECT id, NULL, codigo, nome, unidade, minimo, ativo, criado_em FROM itens
        """,
        "DROP TABLE itens",
        "ALTER TABLE itens_novo RENAME TO itens",
    ),
)


class EstoqueError(Exception):
    """Erro de negócio do inventário."""

    chave_mensagem = "estoque_erro"


class CodigoDuplicadoError(EstoqueError):
    """Já existe um item com esse código."""

    chave_mensagem = "estoque_codigo_duplicado"


class ItemNaoEncontradoError(EstoqueError):
    """O item indicado não existe."""

    chave_mensagem = "estoque_item_nao_encontrado"


class SaldoInsuficienteError(EstoqueError):
    """A saída pedida é maior do que o que existe."""

    chave_mensagem = "estoque_saldo_insuficiente"

    def __init__(self, disponivel: int, pedido: int) -> None:
        super().__init__(f"Existem {disponivel}, foram pedidos {pedido}.")
        self.disponivel = disponivel
        self.pedido = pedido


class Tipo(str, Enum):
    """Um movimento só pode ir num de dois sentidos."""

    ENTRADA = "entrada"
    SAIDA = "saida"


@dataclass(frozen=True)
class Item:
    """Uma coisa que se conta."""

    id: int
    codigo: str
    nome: str
    unidade: str
    minimo: int
    ativo: bool
    quantidade: int = 0

    @property
    def abaixo_do_minimo(self) -> bool:
        """Se já convém repor."""
        return self.minimo > 0 and self.quantidade < self.minimo


@dataclass(frozen=True)
class Movimento:
    """Uma entrada ou uma saída."""

    id: int
    item_id: int
    tipo: Tipo
    quantidade: int
    motivo: str
    quem: str
    momento: str

    @property
    def sinal(self) -> int:
        return 1 if self.tipo == Tipo.ENTRADA else -1


class Inventario:
    """O inventário, sobre um armazenamento que o módulo recebe."""

    def __init__(self, dados, empresa=None) -> None:
        """
        Args:
            empresa: função sem argumentos que devolve o id da empresa em
                sessão, ou ``None`` quando não há isolamento — normalmente
                ``contexto.empresa``. É uma função e não um valor porque a
                sessão muda enquanto o módulo está carregado, e um valor
                lido no arranque ficaria preso à primeira pessoa que entrou.

                Sem ela, o inventário comporta-se como sempre se comportou:
                vê tudo. É o que mantém os testes do módulo e qualquer uso
                fora da aplicação a funcionar como antes.
        """
        self._dados = dados
        self._empresa = empresa or (lambda: None)

    def preparar(self) -> None:
        """Cria o esquema deste módulo, uma vez."""
        for versao, *instrucoes in MIGRACOES:
            self._dados.migrar(versao, *instrucoes)
        for versao, *instrucoes in RECONSTRUCOES:
            self._dados.migrar(versao, *instrucoes, reconstroi_tabelas=True)

    # --------------------------------------------------------------- âmbito

    def _ambito(self, prefixo: str = "i.") -> tuple:
        """Condição e parâmetros que limitam o que se vê à empresa em sessão.

        Sem empresa, não há condição — e é assim que uma instalação com uma
        empresa só continua exatamente como estava.

        Os itens **sem empresa** ficam sempre dentro: são anteriores à
        estrutura e não pertencem a nenhuma. Escondê-los faria desaparecer o
        inventário inteiro no dia em que a segunda empresa fosse criada.
        """
        empresa = self._empresa()
        if empresa is None:
            return "", []
        return f"({prefixo}empresa = ? OR {prefixo}empresa IS NULL)", [empresa]

    # ------------------------------------------------------------- leitura

    _COLUNAS = "i.id, i.codigo, i.nome, i.unidade, i.minimo, i.ativo"

    _SALDO = (
        "COALESCE((SELECT SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade "
        "ELSE -m.quantidade END) FROM movimentos m WHERE m.item_id = i.id), 0)"
    )

    def _para_item(self, linha) -> Item:
        return Item(
            id=linha[0],
            codigo=linha[1],
            nome=linha[2],
            unidade=linha[3],
            minimo=linha[4],
            ativo=bool(linha[5]),
            quantidade=int(linha[6]),
        )

    def listar(self, incluir_inativos: bool = False) -> List[Item]:
        """Os itens, com a quantidade calculada a partir dos movimentos."""
        condicoes, parametros = [], []
        if not incluir_inativos:
            condicoes.append("i.ativo = 1")
        ambito, valores = self._ambito()
        if ambito:
            condicoes.append(ambito)
            parametros.extend(valores)

        consulta = f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i"
        if condicoes:
            consulta += " WHERE " + " AND ".join(condicoes)
        consulta += " ORDER BY i.nome COLLATE NOCASE"
        return [
            self._para_item(linha)
            for linha in self._dados.consultar(consulta, parametros)
        ]

    def obter(self, item_id: int) -> Optional[Item]:
        """Um item, se a sessão o puder ver.

        O âmbito aplica-se aqui de propósito: ``exigir`` passa por cá, e
        ``exigir`` é o que guarda a escrita. Sem isto, um id conhecido dava
        acesso ao item de outra empresa mesmo que ele não aparecesse na
        lista — que é a forma clássica de um isolamento ter buracos.
        """
        ambito, parametros = self._ambito()
        consulta = f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i WHERE i.id = ?"
        if ambito:
            consulta += f" AND {ambito}"
        linha = self._dados.consultar_um(consulta, [item_id, *parametros])
        return self._para_item(linha) if linha else None

    def exigir(self, item_id: int) -> Item:
        item = self.obter(item_id)
        if item is None:
            raise ItemNaoEncontradoError(f"O item {item_id} não existe.")
        return item

    def por_codigo(self, codigo: str) -> Optional[Item]:
        """O item com este código, dentro do âmbito.

        É o que faz duas empresas poderem ter "CX-01": a procura é a que
        decide se um código está livre, e ela deixou de olhar para a
        instalação inteira.
        """
        ambito, parametros = self._ambito()
        consulta = (
            f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i "
            "WHERE i.codigo = ? COLLATE NOCASE"
        )
        if ambito:
            consulta += f" AND {ambito}"
        linha = self._dados.consultar_um(consulta, [(codigo or "").strip(), *parametros])
        return self._para_item(linha) if linha else None

    def em_falta(self) -> List[Item]:
        """Os itens abaixo do mínimo — o número que interessa a quem compra."""
        return [item for item in self.listar() if item.abaixo_do_minimo]

    def movimentos(self, item_id: Optional[int] = None, limite: int = 100) -> List[Movimento]:
        """O histórico, do mais recente para trás."""
        consulta = (
            "SELECT id, item_id, tipo, quantidade, motivo, quem, momento FROM movimentos"
        )
        condicoes, parametros = [], []
        if item_id is not None:
            condicoes.append("item_id = ?")
            parametros.append(item_id)
        # Um movimento pertence ao item, e o item à empresa. Sem esta
        # restrição, o histórico mostrava linhas de itens que a lista não
        # mostra — e dava a ver códigos e quantidades de outra empresa.
        ambito, valores = self._ambito(prefixo="")
        if ambito:
            condicoes.append(
                f"item_id IN (SELECT id FROM itens WHERE {ambito})"
            )
            parametros.extend(valores)
        if condicoes:
            consulta += " WHERE " + " AND ".join(condicoes)
        consulta += " ORDER BY id DESC LIMIT ?"
        parametros.append(int(limite))

        return [
            Movimento(
                id=l[0],
                item_id=l[1],
                tipo=Tipo(l[2]),
                quantidade=l[3],
                motivo=l[4],
                quem=l[5],
                momento=l[6],
            )
            for l in self._dados.consultar(consulta, parametros)
        ]

    # ------------------------------------------------------------- escrita

    def criar_item(
        self, codigo: str, nome: str, unidade: str = "un", minimo: int = 0
    ) -> Item:
        """Regista uma coisa nova para contar.

        Raises:
            ValueError: código ou nome vazios, ou mínimo negativo.
            CodigoDuplicadoError: já existe um item com esse código.
        """
        codigo = (codigo or "").strip()
        nome = (nome or "").strip()
        if not codigo:
            raise ValueError("O item precisa de um código.")
        if not nome:
            raise ValueError("O item precisa de um nome.")
        if int(minimo) < 0:
            raise ValueError("O mínimo não pode ser negativo.")

        if self.por_codigo(codigo) is not None:
            raise CodigoDuplicadoError(f"Já existe um item com o código {codigo!r}.")

        novo = self._dados.executar(
            "INSERT INTO itens (empresa, codigo, nome, unidade, minimo, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (
                self._empresa(),
                codigo,
                nome,
                (unidade or "un").strip() or "un",
                int(minimo),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return self.exigir(novo)

    def _mover(
        self, item_id: int, tipo: Tipo, quantidade: int, motivo: str, quem: str
    ) -> Movimento:
        item = self.exigir(item_id)
        quantidade = int(quantidade)
        if quantidade <= 0:
            raise ValueError("A quantidade tem de ser maior do que zero.")

        if tipo == Tipo.SAIDA and quantidade > item.quantidade:
            # Sair mais do que existe deixaria um saldo negativo, que não
            # descreve nada no mundo real — é sempre um engano ou um registo
            # em falta, e recusar aqui é o que obriga a corrigir a origem.
            raise SaldoInsuficienteError(item.quantidade, quantidade)

        momento = datetime.now().isoformat(timespec="seconds")
        novo = self._dados.executar(
            "INSERT INTO movimentos (item_id, tipo, quantidade, motivo, quem, momento) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, tipo.value, quantidade, (motivo or "").strip(), quem, momento),
        )
        return Movimento(novo, item_id, tipo, quantidade, motivo, quem, momento)

    def entrada(
        self, item_id: int, quantidade: int, motivo: str = "", quem: str = ""
    ) -> Movimento:
        """Regista que entrou alguma coisa."""
        return self._mover(item_id, Tipo.ENTRADA, quantidade, motivo, quem)

    def saida(
        self, item_id: int, quantidade: int, motivo: str = "", quem: str = ""
    ) -> Movimento:
        """Regista que saiu alguma coisa.

        Raises:
            SaldoInsuficienteError: se não houver quantidade que chegue.
        """
        return self._mover(item_id, Tipo.SAIDA, quantidade, motivo, quem)

    def definir_ativo(self, item_id: int, ativo: bool = True) -> Item:
        """Tira um item de circulação sem apagar o histórico dele."""
        self.exigir(item_id)
        self._dados.executar(
            "UPDATE itens SET ativo = ? WHERE id = ?", (1 if ativo else 0, item_id)
        )
        return self.exigir(item_id)
