"""Tela *Configurações → Utilizadores*.

Gestão de contas para quem tem a permissão ``utilizadores.gerir``: criar,
mudar papel, ativar, desativar, redefinir palavra-passe e remover.

A aplicação nunca mostra uma palavra-passe — nem sequer as que acabou de
definir. Redefinir é escrever uma nova.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional

from core import organizacao, permissoes, seguranca, utilizadores
from core.log import obter_logger
from core.permissoes import PAPEIS, Permissao
from core.utilizadores import Utilizador
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_NEUTRA = cores()["texto_suave"]


def nome_do_papel(papel: str) -> str:
    """Nome traduzido de um papel."""
    return carregar_texto(f"papel_{papel}", papel)


class DialogoConta(tk.Toplevel):
    """Formulário de criação de conta."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("novo_utilizador"))
        self.resizable(False, False)
        self.resultado: Optional[Utilizador] = None

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(corpo, text=carregar_texto("nome_completo")).grid(row=0, column=0, sticky=tk.W)
        self.entrada_nome = ttk.Entry(corpo, width=26)
        self.entrada_nome.grid(row=0, column=1, pady=4, padx=(10, 0))

        ttk.Label(corpo, text=carregar_texto("utilizador")).grid(row=1, column=0, sticky=tk.W)
        self.entrada_utilizador = ttk.Entry(corpo, width=26)
        self.entrada_utilizador.grid(row=1, column=1, pady=4, padx=(10, 0))

        ttk.Label(corpo, text=carregar_texto("senha")).grid(row=2, column=0, sticky=tk.W)
        self.entrada_senha = ttk.Entry(corpo, width=26, show="•")
        self.entrada_senha.grid(row=2, column=1, pady=4, padx=(10, 0))

        ttk.Label(corpo, text=carregar_texto("papel")).grid(row=3, column=0, sticky=tk.W)
        self.papel_var = tk.StringVar(value="colaborador")
        self.seletor_papel = ttk.Combobox(
            corpo,
            textvariable=self.papel_var,
            state="readonly",
            width=24,
            values=[nome_do_papel(p) for p in PAPEIS],
        )
        self.seletor_papel.grid(row=3, column=1, pady=4, padx=(10, 0))
        self.seletor_papel.set(nome_do_papel("colaborador"))

        ttk.Label(
            corpo,
            text=carregar_texto("senha_requisitos", minimo=seguranca.COMPRIMENTO_MINIMO),
            foreground=COR_NEUTRA,
            wraplength=300,
            justify=tk.LEFT,
        ).grid(row=4, column=0, columnspan=2, pady=(8, 0))

        self.mensagem = ttk.Label(corpo, foreground=cores()["mau"], wraplength=300, justify=tk.LEFT)
        self.mensagem.grid(row=5, column=0, columnspan=2, pady=(6, 0))

        acoes = ttk.Frame(corpo)
        acoes.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(acoes, text=carregar_texto("criar_conta"), command=self.submeter).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(acoes, text=carregar_texto("cancelar"), command=self.destroy).pack(
            side=tk.LEFT, padx=4
        )

        self.transient(master)
        self.bind("<Return>", lambda _: self.submeter())
        self.bind("<Escape>", lambda _: self.destroy())
        try:
            self.grab_set()
        except tk.TclError:  # pragma: no cover
            pass
        self.entrada_nome.focus_set()

    def papel_escolhido(self) -> str:
        """Identificador do papel selecionado."""
        escolhido = self.papel_var.get()
        for papel in PAPEIS:
            if nome_do_papel(papel) == escolhido:
                return papel
        return "colaborador"

    def submeter(self) -> None:
        """Cria a conta com o que está no formulário."""
        self.mensagem.config(text="")
        try:
            self.resultado = utilizadores.criar(
                self.entrada_utilizador.get(),
                self.entrada_senha.get(),
                self.papel_escolhido(),
                self.entrada_nome.get(),
            )
        except seguranca.SenhaInvalidaError as erro:
            self.mensagem.config(text="\n".join(carregar_texto(c) for c in erro.problemas))
            return
        except utilizadores.UtilizadorError as erro:
            self.mensagem.config(text=carregar_texto(erro.chave_mensagem))
            return
        self.destroy()


class JanelaUtilizadores(tk.Toplevel):
    """Lista de contas com as ações de gestão."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("utilizadores"))
        self.geometry("720x420")
        self.transient(master)
        self._contas: List[Utilizador] = []

        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(
            cabecalho, text=carregar_texto("utilizadores"), font=fonte("subtitulo", negrito=True)
        ).pack(side=tk.LEFT)
        ttk.Button(
            cabecalho, text="+ " + carregar_texto("novo_utilizador"), command=self.nova_conta
        ).pack(side=tk.RIGHT)

        colunas = ("utilizador", "nome", "papel", "unidade", "estado", "ultimo_acesso")
        self.tabela = ttk.Treeview(self, columns=colunas, show="headings", height=12)
        larguras = {"utilizador": 120, "nome": 150, "papel": 110, "unidade": 170, "estado": 80, "ultimo_acesso": 140}
        for coluna in colunas:
            self.tabela.heading(
                coluna, text=carregar_texto(f"coluna_{coluna}"), anchor=tk.W
            )
            self.tabela.column(coluna, width=larguras[coluna], anchor=tk.W)
        self.tabela.pack(fill=tk.BOTH, expand=True, padx=12)

        acoes = ttk.Frame(self)
        acoes.pack(fill=tk.X, padx=12, pady=10)
        self._botoes = {
            "papel": ttk.Button(acoes, text=carregar_texto("alterar_papel"), command=self.alterar_papel),
            "unidade": ttk.Button(acoes, text=carregar_texto("definir_unidade"), command=self.definir_unidade),
            "estado": ttk.Button(acoes, text=carregar_texto("ativar_desativar"), command=self.alternar_estado),
            "senha": ttk.Button(acoes, text=carregar_texto("redefinir_senha"), command=self.redefinir_senha),
            "remover": ttk.Button(acoes, text=carregar_texto("remover"), command=self.remover),
        }
        for botao in self._botoes.values():
            botao.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(acoes, text=carregar_texto("fechar"), command=self.destroy).pack(side=tk.RIGHT)

        self.recarregar()

    # ---------------------------------------------------------------- dados

    def contas(self) -> List[Utilizador]:
        """As contas atualmente listadas."""
        return self._contas

    def recarregar(self) -> None:
        """Relê as contas do banco."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        if not permissoes.pode(Permissao.UTILIZADORES_GERIR):
            self._contas = []
            for botao in self._botoes.values():
                botao.state(["disabled"])
            return

        self._contas = utilizadores.listar()
        for conta in self._contas:
            self.tabela.insert(
                "",
                tk.END,
                iid=conta.nome_utilizador,
                values=(
                    conta.nome_utilizador,
                    conta.nome,
                    nome_do_papel(conta.papel_nome),
                    organizacao.caminho(conta.unidade_id) if conta.unidade_id else "",
                    carregar_texto("conta_ativa" if conta.ativo else "conta_inativa_estado"),
                    (conta.ultimo_acesso or "").replace("T", " "),
                ),
            )

    def selecionada(self) -> Optional[Utilizador]:
        """A conta selecionada, avisando se não houver nenhuma."""
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo(
                carregar_texto("informacao"), carregar_texto("selecione_conta"), parent=self
            )
            return None
        return next((c for c in self._contas if c.nome_utilizador == selecao[0]), None)

    # ---------------------------------------------------------------- ações

    def nova_conta(self) -> None:
        """Abre o formulário de criação."""
        dialogo = DialogoConta(self)
        self.wait_window(dialogo)
        if dialogo.resultado is not None:
            self.recarregar()

    def definir_unidade(self) -> None:
        """Põe a conta selecionada num lugar da estrutura, ou tira-a de lá."""
        conta = self.selecionada()
        if conta is None:
            return

        unidades = organizacao.listar()
        if not unidades:
            messagebox.showinfo(
                carregar_texto("informacao"),
                carregar_texto("estrutura_vazia"),
                parent=self,
            )
            return

        # A opção de não pertencer a lado nenhum tem de estar na lista: sem
        # ela, uma pessoa posta numa unidade por engano ficava lá presa.
        sem = carregar_texto("sem_unidade")
        por_caminho = {organizacao.caminho(u.id): u.id for u in unidades}
        escolhido = simpledialog.askstring(
            carregar_texto("definir_unidade"),
            carregar_texto("escolher_unidade", utilizador=conta.apresentacao)
            + "\n"
            + ", ".join([sem] + sorted(por_caminho)),
            initialvalue=(
                organizacao.caminho(conta.unidade_id) if conta.unidade_id else sem
            ),
            parent=self,
        )
        if escolhido is None:
            return

        escolhido = escolhido.strip()
        if escolhido and escolhido != sem and escolhido not in por_caminho:
            messagebox.showerror(
                carregar_texto("erro"),
                carregar_texto("unidade_nao_encontrada"),
                parent=self,
            )
            return

        utilizadores.definir_unidade(
            conta.nome_utilizador,
            None if not escolhido or escolhido == sem else por_caminho[escolhido],
        )
        self.recarregar()

    def alterar_papel(self) -> None:
        """Pede um papel novo para a conta selecionada."""
        conta = self.selecionada()
        if conta is None:
            return
        escolhido = simpledialog.askstring(
            carregar_texto("alterar_papel"),
            carregar_texto("escolher_papel", opcoes=", ".join(PAPEIS)),
            initialvalue=conta.papel_nome,
            parent=self,
        )
        if not escolhido:
            return
        self._executar(lambda: utilizadores.definir_papel(conta.nome_utilizador, escolhido.strip()))

    def alternar_estado(self) -> None:
        """Ativa ou desativa a conta selecionada."""
        conta = self.selecionada()
        if conta is None:
            return
        self._executar(lambda: utilizadores.definir_ativo(conta.nome_utilizador, not conta.ativo))

    def redefinir_senha(self) -> None:
        """Define uma palavra-passe nova para a conta selecionada."""
        conta = self.selecionada()
        if conta is None:
            return
        nova = simpledialog.askstring(
            carregar_texto("redefinir_senha"),
            carregar_texto("nova_senha_para", utilizador=conta.nome_utilizador),
            show="•",
            parent=self,
        )
        if not nova:
            return
        self._executar(lambda: utilizadores.alterar_senha(conta.nome_utilizador, nova))

    def remover(self) -> None:
        """Remove a conta selecionada, com confirmação."""
        conta = self.selecionada()
        if conta is None:
            return
        if not messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("confirmar_remocao", item=conta.nome_utilizador),
            parent=self,
        ):
            return
        self._executar(lambda: utilizadores.remover(conta.nome_utilizador))

    def _executar(self, acao) -> None:
        """Corre uma operação de gestão, traduzindo a recusa se houver."""
        try:
            acao()
        except seguranca.SenhaInvalidaError as erro:
            messagebox.showerror(
                carregar_texto("erro"),
                "\n".join(carregar_texto(c) for c in erro.problemas),
                parent=self,
            )
        except utilizadores.UtilizadorError as erro:
            messagebox.showerror(
                carregar_texto("erro"), carregar_texto(erro.chave_mensagem), parent=self
            )
        self.recarregar()
