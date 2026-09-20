"""Estoque — o primeiro módulo de negócio, e por isso o teste da arquitetura.

Não é uma demonstração: guarda itens, regista entradas e saídas, calcula
saldos e avisa do que está abaixo do mínimo. O que interessa é **como** o faz.

* Os dados são dele: ``contexto.dados`` dá-lhe um SQLite próprio, com as suas
  migrações. Não toca no banco da aplicação nem no de outro módulo.
* A aplicação não sabe que ele existe. Não há um ``if estoque`` em lado nenhum
  do núcleo, nem uma tabela de estoque no esquema da aplicação.
* Tudo o que usa da plataforma chega pelo :class:`~core.plugin_api.ContextoPlugin`:
  a aba, a tradução, a configuração, os eventos.
* Publica os seus próprios eventos (``estoque.*``), para que a análise, um
  fluxo de trabalho ou outro módulo possam reagir sem que ele os conheça.

Se isto precisasse de uma exceção na plataforma para funcionar, a arquitetura
estaria errada. Precisou de uma — as permissões do próprio domínio — e essa
foi acrescentada ao contrato, não contornada.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional

from core.plugin_api import Plugin

from . import dominio
from .dominio import EstoqueError, Inventario, Item

COR_ALERTA = "#c0392b"
COR_NEUTRA = "#7a8794"


class PainelEstoque(ttk.Frame):
    """A lista do que existe, com as ações de quem trabalha com ela."""

    def __init__(self, master: tk.Misc, contexto, servico: "ServicoEstoque") -> None:
        super().__init__(master)
        self._contexto = contexto
        self._servico_estoque = servico

        topo = ttk.Frame(self)
        topo.pack(fill=tk.X, padx=10, pady=(10, 4))
        self._resumo = ttk.Label(topo, font=("Arial", 11, "bold"))
        self._resumo.pack(side=tk.LEFT)

        colunas = ("codigo", "nome", "quantidade", "minimo")
        self.tabela = ttk.Treeview(self, columns=colunas, show="headings", height=12)
        larguras = {"codigo": 110, "nome": 260, "quantidade": 110, "minimo": 90}
        for coluna in colunas:
            self.tabela.heading(coluna, text=self._t(f"coluna_{coluna}"), anchor=tk.W)
            self.tabela.column(coluna, width=larguras[coluna], anchor=tk.W)
        self.tabela.pack(fill=tk.BOTH, expand=True, padx=10)
        # Quem está abaixo do mínimo tem de saltar à vista sem ser preciso ler
        # os números um a um.
        self.tabela.tag_configure("em_falta", foreground=COR_ALERTA)

        self.mensagem = ttk.Label(self, wraplength=600, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, padx=10, pady=(6, 0))

        acoes = ttk.Frame(self)
        acoes.pack(fill=tk.X, padx=10, pady=10)
        self.botoes = {
            "novo": ttk.Button(acoes, text=self._t("novo_item"), command=self.novo_item),
            "entrada": ttk.Button(acoes, text=self._t("entrada"), command=self.entrada),
            "saida": ttk.Button(acoes, text=self._t("saida"), command=self.saida),
        }
        for botao in self.botoes.values():
            botao.pack(side=tk.LEFT, padx=(0, 6))

        self.recarregar()

    # ---------------------------------------------------------------- apoio

    def _t(self, chave: str, **formatacao) -> str:
        return self._contexto.traduzir(chave, chave, **formatacao)

    def _pode_escrever(self) -> bool:
        return self._contexto.pode(ESCREVER)

    def itens(self) -> List[Item]:
        """Os itens atualmente mostrados."""
        return list(self._itens)

    def recarregar(self) -> None:
        """Relê o inventário e redesenha a tabela."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        self._itens = self._servico_estoque.listar()
        for item in self._itens:
            self.tabela.insert(
                "",
                tk.END,
                iid=str(item.id),
                values=(item.codigo, item.nome, f"{item.quantidade} {item.unidade}", item.minimo),
                tags=("em_falta",) if item.abaixo_do_minimo else (),
            )

        em_falta = [i for i in self._itens if i.abaixo_do_minimo]
        if em_falta:
            self._resumo.configure(
                text=self._t("resumo_em_falta", total=len(self._itens), falta=len(em_falta)),
                foreground=COR_ALERTA,
            )
        else:
            self._resumo.configure(
                text=self._t("resumo", total=len(self._itens)), foreground=""
            )

        # Sem permissão para escrever, os botões ficam travados em vez de
        # falharem depois: perguntar é mais barato do que apanhar o erro.
        estado = ["!disabled"] if self._pode_escrever() else ["disabled"]
        for botao in self.botoes.values():
            botao.state(estado)

    def selecionado(self) -> Optional[Item]:
        selecao = self.tabela.selection()
        if not selecao:
            self._dizer(self._t("selecione_item"), COR_NEUTRA)
            return None
        return next((i for i in self._itens if str(i.id) == selecao[0]), None)

    def _dizer(self, texto: str, cor: str = "#2c7a3f") -> None:
        self.mensagem.configure(text=texto, foreground=cor)

    def _tentar(self, acao) -> bool:
        """Corre uma operação do domínio, mostrando o erro em vez de o deixar subir."""
        try:
            acao()
        except EstoqueError as erro:
            self._dizer(self._t(erro.chave_mensagem) + " " + str(erro), COR_ALERTA)
            return False
        except (ValueError, PermissionError) as erro:
            self._dizer(str(erro), COR_ALERTA)
            return False
        self.recarregar()
        return True

    # ---------------------------------------------------------------- ações

    def novo_item(self) -> None:
        codigo = simpledialog.askstring(
            self._t("novo_item"), self._t("pedir_codigo"), parent=self
        )
        if not codigo:
            return
        nome = simpledialog.askstring(
            self._t("novo_item"), self._t("pedir_nome"), parent=self
        )
        if not nome:
            return
        minimo = simpledialog.askinteger(
            self._t("novo_item"), self._t("pedir_minimo"), parent=self, initialvalue=0, minvalue=0
        )

        def criar():
            self._servico().criar_item(codigo, nome, minimo=minimo or 0)
            self._dizer(self._t("item_criado", nome=nome))

        self._tentar(criar)

    def entrada(self) -> None:
        self._movimentar("entrada")

    def saida(self) -> None:
        self._movimentar("saida")

    def _movimentar(self, tipo: str) -> None:
        item = self.selecionado()
        if item is None:
            return
        quantidade = simpledialog.askinteger(
            self._t(tipo), self._t("pedir_quantidade", item=item.nome), parent=self, minvalue=1
        )
        if not quantidade:
            return
        motivo = simpledialog.askstring(self._t(tipo), self._t("pedir_motivo"), parent=self)

        def mover():
            servico = self._servico()
            operacao = servico.entrada if tipo == "entrada" else servico.saida
            operacao(item.id, quantidade, motivo or "")
            self._dizer(self._t(f"{tipo}_registada", quantidade=quantidade, item=item.nome))

        self._tentar(mover)

    def _servico(self) -> "ServicoEstoque":
        """O inventário com as permissões aplicadas."""
        return self._servico_estoque


#: Permissões próprias deste módulo, declaradas no ``plugin.json``.
LER = "estoque.ler"
ESCREVER = "estoque.escrever"


class ServicoEstoque:
    """O inventário, com a permissão verificada antes de cada operação.

    A separação é a mesma que a aplicação faz entre ``banco_de_dados`` e
    ``tarefas_servico``: o domínio não sabe quem está a usá-lo, e a política
    vive num sítio só.
    """

    def __init__(self, inventario: Inventario, contexto) -> None:
        self._inventario = inventario
        self._contexto = contexto

    def _exigir(self, permissao: str) -> None:
        self._contexto.exigir(permissao)

    def listar(self, incluir_inativos: bool = False) -> List[Item]:
        self._exigir(LER)
        return self._inventario.listar(incluir_inativos)

    def em_falta(self) -> List[Item]:
        self._exigir(LER)
        return self._inventario.em_falta()

    def movimentos(self, item_id: Optional[int] = None, limite: int = 100):
        self._exigir(LER)
        return self._inventario.movimentos(item_id, limite)

    def criar_item(self, codigo: str, nome: str, unidade: str = "un", minimo: int = 0) -> Item:
        self._exigir(ESCREVER)
        item = self._inventario.criar_item(codigo, nome, unidade, minimo)
        self._contexto.publicar("estoque.item_criado", id=item.id, codigo=item.codigo)
        return item

    def entrada(self, item_id: int, quantidade: int, motivo: str = ""):
        return self._movimentar("entrada", item_id, quantidade, motivo)

    def saida(self, item_id: int, quantidade: int, motivo: str = ""):
        return self._movimentar("saida", item_id, quantidade, motivo)

    def _movimentar(self, tipo: str, item_id: int, quantidade: int, motivo: str):
        self._exigir(ESCREVER)
        operacao = getattr(self._inventario, tipo)
        movimento = operacao(item_id, quantidade, motivo, quem=self._contexto.utilizador())
        item = self._inventario.exigir(item_id)
        # Um evento por movimento, e outro só quando o item passa a estar em
        # falta: quem quiser encomendar não tem de recalcular nada.
        self._contexto.publicar(
            f"estoque.{tipo}", id=item_id, quantidade=quantidade, saldo=item.quantidade
        )
        if item.abaixo_do_minimo:
            self._contexto.publicar(
                "estoque.em_falta", id=item_id, saldo=item.quantidade, minimo=item.minimo
            )
        return movimento


class EstoquePlugin(Plugin):
    """Ciclo de vida do módulo."""

    def __init__(self, contexto) -> None:
        super().__init__(contexto)
        self.inventario: Optional[Inventario] = None
        self.servico: Optional[ServicoEstoque] = None
        self._painel: Optional[PainelEstoque] = None

    def inicializar(self) -> None:
        """Prepara o esquema próprio. Nada na aplicação é tocado."""
        # A empresa vai como função: a sessão muda enquanto o módulo está
        # carregado, e um valor lido aqui ficava preso à primeira pessoa
        # que entrou.
        self.inventario = Inventario(self.contexto.dados, self.contexto.empresa)
        self.inventario.preparar()
        self.servico = ServicoEstoque(self.inventario, self.contexto)
        self._declarar_indicadores()
        self._declarar_importacao()
        self.contexto.logger.info("Estoque pronto.")

    def _declarar_importacao(self) -> None:
        """Permite carregar o inventário inicial de uma folha de cálculo.

        É como se começa a usar um módulo destes: ninguém digita trezentos
        artigos à mão para experimentar.
        """
        from importacao.motor import Campo

        def validar(dados) -> list:
            problemas = []
            codigo = (dados.get("codigo") or "").strip()
            if not codigo:
                problemas.append("O código está vazio.")
            elif self.inventario.por_codigo(codigo) is not None:
                # Importar duas vezes o mesmo ficheiro não pode duplicar o
                # inventário em silêncio.
                problemas.append(f"Já existe um item com o código {codigo!r}.")
            if not (dados.get("nome") or "").strip():
                problemas.append("O nome está vazio.")

            minimo = (dados.get("minimo") or "").strip()
            if minimo:
                try:
                    if int(float(minimo.replace(",", "."))) < 0:
                        problemas.append("O mínimo não pode ser negativo.")
                except ValueError:
                    problemas.append(f"Mínimo inválido: {minimo!r}")
            return problemas

        def criar(dados) -> None:
            minimo = (dados.get("minimo") or "").strip()
            self.servico.criar_item(
                dados["codigo"],
                dados["nome"],
                unidade=(dados.get("unidade") or "un").strip() or "un",
                minimo=int(float(minimo.replace(",", "."))) if minimo else 0,
            )

        self.contexto.registar_destino_de_importacao(
            "itens",
            campos=[
                Campo("codigo", "campo_codigo", obrigatorio=True, exemplo="PAR-01", chave=True),
                Campo("nome", "campo_nome", obrigatorio=True, exemplo="Parafuso M6"),
                Campo("unidade", "campo_unidade", exemplo="un"),
                Campo("minimo", "campo_minimo", exemplo="10"),
            ],
            validar=validar,
            criar=criar,
            chave_titulo="destino_estoque_itens",
            permissao=ESCREVER,
        )

    def _declarar_indicadores(self) -> None:
        """Põe dois números deste módulo no painel da aplicação.

        O painel não sabe o que é um item de inventário. Declarar é tudo o
        que este módulo faz — e sai do painel quando for desinstalado.
        """
        from indicadores import Valor

        def em_inventario() -> Valor:
            return Valor(len(self.servico.listar()), sufixo=" un")

        def em_falta() -> Valor:
            return Valor(len(self.servico.em_falta()))

        self.contexto.registar_indicador(
            "itens", em_inventario, "indicador_estoque_itens", permissao=LER
        )
        self.contexto.registar_indicador(
            "em_falta",
            em_falta,
            "indicador_estoque_em_falta",
            subir_e_bom=False,
            permissao=LER,
        )

    def ativar(self) -> None:
        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba", "Estoque"),
            self._construir_painel,
        )

    def _construir_painel(self, pai) -> ttk.Frame:
        self._painel = PainelEstoque(pai, self.contexto, self.servico)
        return self._painel

    def desativar(self) -> None:
        self._painel = None

    def finalizar(self) -> None:
        self.inventario = None
        self.servico = None


PLUGIN_CLASS = EstoquePlugin
