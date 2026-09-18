"""Tela *Configurações → Estrutura*.

Onde se desenha a empresa: empresas, departamentos e equipas, e quem está sob
quem. É de quem administra a instalação — mexer aqui muda o que as outras
pessoas veem.

A árvore é mostrada como árvore. Uma lista com o caminho escrito em cada linha
ocupa mais e diz menos: o que interessa a quem organiza é o desenho.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional

from core import organizacao, permissoes
from core.log import obter_logger
from core.organizacao import OrganizacaoError, TipoUnidade, Unidade
from core.permissoes import Permissao
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_NEUTRA = cores()["texto_suave"]


def nome_do_tipo(tipo: TipoUnidade) -> str:
    """Nome traduzido de um tipo de unidade."""
    return carregar_texto(f"tipo_{tipo.value}", tipo.value)


def rotulo(unidade: Unidade) -> str:
    """Como a unidade aparece na árvore."""
    texto = unidade.nome
    if not unidade.ativa:
        texto += "  (" + carregar_texto("unidade_inativa") + ")"
    return texto


class JanelaOrganizacao(tk.Toplevel):
    """Estrutura da organização, com as ações de edição."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("estrutura"))
        self.geometry("620x460")
        self.transient(master)
        self._unidades: Dict[int, Unidade] = {}

        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(
            cabecalho, text=carregar_texto("estrutura"), font=fonte("subtitulo", negrito=True)
        ).pack(side=tk.LEFT)
        ttk.Button(
            cabecalho,
            text="+ " + carregar_texto("nova_empresa"),
            command=self.nova_empresa,
        ).pack(side=tk.RIGHT)

        self.arvore = ttk.Treeview(self, columns=("tipo",), height=14)
        self.arvore.heading("#0", text=carregar_texto("unidade"), anchor=tk.W)
        self.arvore.heading("tipo", text=carregar_texto("coluna_tipo"), anchor=tk.W)
        self.arvore.column("#0", width=380, anchor=tk.W)
        self.arvore.column("tipo", width=150, anchor=tk.W)
        self.arvore.pack(fill=tk.BOTH, expand=True, padx=12)

        self.vazio = ttk.Label(
            self,
            text=carregar_texto("estrutura_vazia"),
            foreground=COR_NEUTRA,
            wraplength=560,
            justify=tk.LEFT,
        )

        acoes = ttk.Frame(self)
        acoes.pack(fill=tk.X, padx=12, pady=10)
        self._botoes = {
            "sub": ttk.Button(
                acoes, text=carregar_texto("nova_subunidade"), command=self.nova_subunidade
            ),
            "renomear": ttk.Button(
                acoes, text=carregar_texto("renomear"), command=self.renomear
            ),
            "mover": ttk.Button(acoes, text=carregar_texto("mover"), command=self.mover),
            "estado": ttk.Button(
                acoes, text=carregar_texto("ativar_desativar"), command=self.alternar_estado
            ),
            "remover": ttk.Button(
                acoes, text=carregar_texto("remover"), command=self.remover
            ),
        }
        for botao in self._botoes.values():
            botao.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(acoes, text=carregar_texto("fechar"), command=self.destroy).pack(
            side=tk.RIGHT
        )

        self.recarregar()

    # ---------------------------------------------------------------- dados

    def unidades(self) -> List[Unidade]:
        """As unidades atualmente mostradas."""
        return list(self._unidades.values())

    def recarregar(self) -> None:
        """Relê a estrutura e redesenha a árvore."""
        for linha in self.arvore.get_children():
            self.arvore.delete(linha)

        if not permissoes.pode(Permissao.SISTEMA_ADMIN):
            self._unidades = {}
            for botao in self._botoes.values():
                botao.state(["disabled"])
            return

        # Inativas incluídas: escondê-las aqui era esconder a quem organiza
        # a razão de uma equipa ter desaparecido das listas.
        todas = organizacao.listar(incluir_inativas=True)
        self._unidades = {u.id: u for u in todas}

        for unidade in todas:
            pai = "" if unidade.pai_id is None else str(unidade.pai_id)
            if pai and not self.arvore.exists(pai):
                pai = ""  # pragma: no cover - defensivo
            self.arvore.insert(
                pai,
                tk.END,
                iid=str(unidade.id),
                text=rotulo(unidade),
                values=(nome_do_tipo(unidade.tipo),),
                open=True,
            )

        if todas:
            self.vazio.pack_forget()
        else:
            self.vazio.pack(padx=12, pady=(4, 0), anchor=tk.W)

    def selecionada(self) -> Optional[Unidade]:
        """A unidade selecionada, avisando se não houver nenhuma."""
        selecao = self.arvore.selection()
        if not selecao:
            messagebox.showinfo(
                carregar_texto("informacao"),
                carregar_texto("selecione_unidade"),
                parent=self,
            )
            return None
        return self._unidades.get(int(selecao[0]))

    def _tentar(self, acao) -> None:
        """Corre uma operação, mostrando o erro em vez de o deixar subir."""
        try:
            acao()
        except OrganizacaoError as erro:
            messagebox.showerror(
                carregar_texto("erro"),
                carregar_texto(erro.chave_mensagem, str(erro)),
                parent=self,
            )
        except ValueError as erro:
            messagebox.showerror(carregar_texto("erro"), str(erro), parent=self)
        else:
            self.recarregar()

    # ---------------------------------------------------------------- ações

    def nova_empresa(self) -> None:
        """Cria uma unidade de topo."""
        nome = simpledialog.askstring(
            carregar_texto("nova_empresa"), carregar_texto("nome"), parent=self
        )
        if not nome:
            return
        self._tentar(lambda: organizacao.criar(nome, TipoUnidade.EMPRESA))

    def nova_subunidade(self) -> None:
        """Cria uma unidade dentro da selecionada."""
        pai = self.selecionada()
        if pai is None:
            return
        nome = simpledialog.askstring(
            carregar_texto("nova_subunidade"),
            carregar_texto("nome_dentro_de", pai=organizacao.caminho(pai.id)),
            parent=self,
        )
        if not nome:
            return

        # Uma empresa tem departamentos; um departamento tem equipas. É só o
        # arranque sensato: o tipo muda-se, e a estrutura não depende dele.
        tipo = (
            TipoUnidade.DEPARTAMENTO
            if pai.tipo == TipoUnidade.EMPRESA
            else TipoUnidade.EQUIPA
        )
        self._tentar(lambda: organizacao.criar(nome, tipo, pai.id))

    def renomear(self) -> None:
        unidade = self.selecionada()
        if unidade is None:
            return
        nome = simpledialog.askstring(
            carregar_texto("renomear"),
            carregar_texto("nome"),
            initialvalue=unidade.nome,
            parent=self,
        )
        if not nome:
            return
        self._tentar(lambda: organizacao.renomear(unidade.id, nome))

    def mover(self) -> None:
        """Muda a unidade de lugar, com tudo o que está debaixo dela."""
        unidade = self.selecionada()
        if unidade is None:
            return

        destinos = self._destinos_para(unidade)
        if not destinos:
            messagebox.showinfo(
                carregar_texto("informacao"),
                carregar_texto("sem_destinos"),
                parent=self,
            )
            return

        dialogo = DialogoMover(self, unidade, destinos)
        self.wait_window(dialogo)
        if dialogo.escolhido is None:
            return
        self._tentar(lambda: organizacao.mover(unidade.id, dialogo.escolhido))

    def _destinos_para(self, unidade: Unidade) -> List[Unidade]:
        """Para onde esta unidade pode ir.

        Uma empresa é raiz e não vai para lado nenhum. As restantes podem ir
        para qualquer sítio fora da sua própria sub-árvore — oferecer o resto
        seria oferecer um erro.
        """
        if unidade.tipo == TipoUnidade.EMPRESA:
            return []
        proibidos = {u.id for u in organizacao.descendentes(unidade.id, incluir_inativas=True)}
        return [
            candidata
            for candidata in self._unidades.values()
            if candidata.id not in proibidos and candidata.id != unidade.pai_id
        ]

    def alternar_estado(self) -> None:
        unidade = self.selecionada()
        if unidade is None:
            return
        self._tentar(lambda: organizacao.definir_ativa(unidade.id, not unidade.ativa))

    def remover(self) -> None:
        unidade = self.selecionada()
        if unidade is None:
            return
        if not messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("confirmar_remocao", item=unidade.nome),
            parent=self,
        ):
            return
        self._tentar(lambda: organizacao.remover(unidade.id))


class DialogoMover(tk.Toplevel):
    """Escolha do novo lugar de uma unidade."""

    def __init__(self, master: tk.Misc, unidade: Unidade, destinos: List[Unidade]) -> None:
        super().__init__(master)
        self.title(carregar_texto("mover"))
        self.resizable(False, False)
        self.transient(master)
        self.escolhido: Optional[int] = None
        self._destinos = destinos

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            corpo, text=carregar_texto("mover_para", unidade=unidade.nome)
        ).pack(anchor=tk.W)

        self._rotulos = {organizacao.caminho(d.id): d.id for d in destinos}
        self.var = tk.StringVar()
        self.seletor = ttk.Combobox(
            corpo,
            textvariable=self.var,
            state="readonly",
            width=40,
            values=sorted(self._rotulos),
        )
        self.seletor.pack(pady=(8, 0))

        acoes = ttk.Frame(corpo)
        acoes.pack(pady=(14, 0))
        ttk.Button(acoes, text=carregar_texto("confirmar"), command=self.confirmar).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(acoes, text=carregar_texto("cancelar"), command=self.destroy).pack(
            side=tk.LEFT
        )

    def confirmar(self) -> None:
        escolha = self.var.get()
        if escolha in self._rotulos:
            self.escolhido = self._rotulos[escolha]
            self.destroy()
