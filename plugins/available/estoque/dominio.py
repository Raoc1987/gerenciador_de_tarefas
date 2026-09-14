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

    def __init__(self, dados) -> None:
        self._dados = dados

    def preparar(self) -> None:
        """Cria o esquema deste módulo, uma vez."""
        for versao, *instrucoes in MIGRACOES:
            self._dados.migrar(versao, *instrucoes)

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
        consulta = f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i"
        if not incluir_inativos:
            consulta += " WHERE i.ativo = 1"
        consulta += " ORDER BY i.nome COLLATE NOCASE"
        return [self._para_item(linha) for linha in self._dados.consultar(consulta)]

    def obter(self, item_id: int) -> Optional[Item]:
        linha = self._dados.consultar_um(
            f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i WHERE i.id = ?",
            (item_id,),
        )
        return self._para_item(linha) if linha else None

    def exigir(self, item_id: int) -> Item:
        item = self.obter(item_id)
        if item is None:
            raise ItemNaoEncontradoError(f"O item {item_id} não existe.")
        return item

    def por_codigo(self, codigo: str) -> Optional[Item]:
        linha = self._dados.consultar_um(
            f"SELECT {self._COLUNAS}, {self._SALDO} FROM itens i "
            "WHERE i.codigo = ? COLLATE NOCASE",
            ((codigo or "").strip(),),
        )
        return self._para_item(linha) if linha else None

    def em_falta(self) -> List[Item]:
        """Os itens abaixo do mínimo — o número que interessa a quem compra."""
        return [item for item in self.listar() if item.abaixo_do_minimo]

    def movimentos(self, item_id: Optional[int] = None, limite: int = 100) -> List[Movimento]:
        """O histórico, do mais recente para trás."""
        consulta = (
            "SELECT id, item_id, tipo, quantidade, motivo, quem, momento FROM movimentos"
        )
        parametros: List = []
        if item_id is not None:
            consulta += " WHERE item_id = ?"
            parametros.append(item_id)
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
            "INSERT INTO itens (codigo, nome, unidade, minimo, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (
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
