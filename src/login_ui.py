"""Início de sessão e criação do primeiro administrador.

Duas janelas modais, usadas antes de a aplicação abrir:

* :class:`JanelaLogin` — pedir credenciais;
* :class:`JanelaPrimeiroAdministrador` — no primeiro arranque, quando ainda
  não existe nenhuma conta.

Não há palavra-passe por omissão: uma instalação nova pede que se crie a conta
de administração. Palavras-passe pré-definidas são das formas mais fiáveis de
deixar um sistema aberto.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from tkinter import ttk
from typing import Optional

from core import seguranca, utilizadores
from core.log import obter_logger
from core.utilizadores import MotivoFalha, Utilizador
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_ERRO = cores()["mau"]
COR_NEUTRA = cores()["texto_suave"]


class _JanelaModal(tk.Toplevel):
    """Base: centrada, modal, fecha com Escape e submete com Enter."""

    def __init__(self, master: tk.Misc, titulo: str) -> None:
        super().__init__(master)
        self.title(titulo)
        self.resizable(False, False)
        self.resultado: Optional[Utilizador] = None

        self.protocol("WM_DELETE_WINDOW", self.cancelar)
        self.bind("<Escape>", lambda _: self.cancelar())
        self.bind("<Return>", lambda _: self.submeter())

    def centrar(self) -> None:
        """Põe a janela no meio do ecrã."""
        self.update_idletasks()
        largura, altura = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - largura) // 2
        y = (self.winfo_screenheight() - altura) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def tornar_modal(self) -> None:
        """Prende o foco a esta janela até ela fechar.

        ``transient`` só se usa se o dono estiver **visível**. No arranque não
        está: a janela principal só nasce depois de haver sessão, e até lá a
        raiz Tk está escondida. Uma janela transient de um dono escondido é
        escondida com ele pelo gestor de janelas — o programa ficava a correr,
        à espera de uma janela que ninguém via, e parecia não abrir.
        """
        if self.master is not None and self.master.winfo_viewable():
            self.transient(self.master)
        self.centrar()
        # Sem dono visível não há nada que traga esta janela para a frente.
        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(self._largar_primeiro_plano)
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:  # pragma: no cover - ambiente sem gestor de janelas
            pass

    def _largar_primeiro_plano(self) -> None:
        """Deixa de estar por cima de tudo, sem chatear quem já fechou.

        A janela — ou o interpretador inteiro — pode ter desaparecido entre o
        agendamento e a execução, e aí nem perguntar se existe é seguro. É o
        caso quando a sessão é imediata.
        """
        try:
            if self.winfo_exists():
                self.attributes("-topmost", False)
        except tk.TclError:  # pragma: no cover - a janela já foi
            pass

    def submeter(self) -> None:  # pragma: no cover - sobreposto
        raise NotImplementedError

    def cancelar(self) -> None:
        """Fecha sem autenticar."""
        self.resultado = None
        self.destroy()


class JanelaLogin(_JanelaModal):
    """Pede nome de utilizador e palavra-passe."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, carregar_texto("iniciar_sessao"))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            corpo, text=carregar_texto("titulo"), font=fonte("titulo", negrito=True)
        ).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(
            corpo, text=carregar_texto("iniciar_sessao"), foreground=COR_NEUTRA
        ).grid(row=1, column=0, columnspan=2, pady=(0, 14))

        ttk.Label(corpo, text=carregar_texto("utilizador")).grid(row=2, column=0, sticky=tk.W)
        self.entrada_utilizador = ttk.Entry(corpo, width=26)
        self.entrada_utilizador.grid(row=2, column=1, pady=4, padx=(10, 0))

        ttk.Label(corpo, text=carregar_texto("senha")).grid(row=3, column=0, sticky=tk.W)
        self.entrada_senha = ttk.Entry(corpo, width=26, show="•")
        self.entrada_senha.grid(row=3, column=1, pady=4, padx=(10, 0))

        self.mensagem = ttk.Label(corpo, foreground=COR_ERRO, wraplength=280)
        self.mensagem.grid(row=4, column=0, columnspan=2, pady=(8, 0))

        acoes = ttk.Frame(corpo)
        acoes.grid(row=5, column=0, columnspan=2, pady=(14, 0))
        self.botao_entrar = ttk.Button(
            acoes, text=carregar_texto("entrar"), command=self.submeter
        )
        self.botao_entrar.pack(side=tk.LEFT, padx=4)
        ttk.Button(acoes, text=carregar_texto("cancelar"), command=self.cancelar).pack(
            side=tk.LEFT, padx=4
        )

        self.tornar_modal()
        self.entrada_utilizador.focus_set()

    def submeter(self) -> None:
        """Tenta autenticar com o que está nos campos."""
        nome = self.entrada_utilizador.get().strip()
        senha = self.entrada_senha.get()
        self.mensagem.config(text="")

        resultado = utilizadores.autenticar(nome, senha)
        if resultado.sucesso and resultado.utilizador is not None:
            self.resultado = resultado.utilizador
            self.destroy()
            return

        self.entrada_senha.delete(0, tk.END)
        self.mensagem.config(text=self._texto_da_falha(resultado))
        self.entrada_senha.focus_set()

    @staticmethod
    def _texto_da_falha(resultado) -> str:
        if resultado.motivo == MotivoFalha.BLOQUEADO:
            return carregar_texto("conta_bloqueada", minutos=resultado.minutos_restantes)
        if resultado.motivo == MotivoFalha.INATIVO:
            return carregar_texto("conta_inativa")
        return carregar_texto("credenciais_invalidas")


class JanelaPrimeiroAdministrador(_JanelaModal):
    """Primeiro arranque: criar a conta que administra a instalação."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, carregar_texto("primeiro_administrador"))

        corpo = ttk.Frame(self, padding=20)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            corpo, text=carregar_texto("primeiro_administrador"), font=fonte("subtitulo", negrito=True)
        ).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(
            corpo,
            text=carregar_texto("primeiro_administrador_texto"),
            foreground=COR_NEUTRA,
            wraplength=330,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, pady=(0, 14))

        campos = (
            ("nome_completo", "entrada_nome", False),
            ("utilizador", "entrada_utilizador", False),
            ("senha", "entrada_senha", True),
            ("confirmar_senha", "entrada_confirmacao", True),
        )
        for indice, (chave, atributo, oculto) in enumerate(campos, start=2):
            ttk.Label(corpo, text=carregar_texto(chave)).grid(row=indice, column=0, sticky=tk.W)
            entrada = ttk.Entry(corpo, width=26, show="•" if oculto else "")
            entrada.grid(row=indice, column=1, pady=4, padx=(10, 0))
            setattr(self, atributo, entrada)

        ttk.Label(
            corpo,
            text=carregar_texto("senha_requisitos", minimo=seguranca.COMPRIMENTO_MINIMO),
            foreground=COR_NEUTRA,
            wraplength=330,
            justify=tk.LEFT,
        ).grid(row=6, column=0, columnspan=2, pady=(6, 0))

        self.mensagem = ttk.Label(corpo, foreground=COR_ERRO, wraplength=330, justify=tk.LEFT)
        self.mensagem.grid(row=7, column=0, columnspan=2, pady=(6, 0))

        acoes = ttk.Frame(corpo)
        acoes.grid(row=8, column=0, columnspan=2, pady=(14, 0))
        self.botao_criar = ttk.Button(
            acoes, text=carregar_texto("criar_conta"), command=self.submeter
        )
        self.botao_criar.pack(side=tk.LEFT, padx=4)
        ttk.Button(acoes, text=carregar_texto("cancelar"), command=self.cancelar).pack(
            side=tk.LEFT, padx=4
        )

        self.tornar_modal()
        self.entrada_nome.focus_set()

    def submeter(self) -> None:
        """Valida e cria a conta de administração."""
        nome = self.entrada_nome.get().strip()
        utilizador = self.entrada_utilizador.get().strip()
        senha = self.entrada_senha.get()
        confirmacao = self.entrada_confirmacao.get()
        self.mensagem.config(text="")

        if senha != confirmacao:
            self.mensagem.config(text=carregar_texto("senhas_nao_coincidem"))
            return

        try:
            criado = utilizadores.criar(utilizador, senha, "administrador", nome)
        except seguranca.SenhaInvalidaError as erro:
            self.mensagem.config(
                text="\n".join(carregar_texto(chave) for chave in erro.problemas)
            )
            return
        except utilizadores.UtilizadorError as erro:
            self.mensagem.config(text=carregar_texto(erro.chave_mensagem))
            logger.info("Criação da primeira conta recusada: %s", erro)
            return

        self.resultado = criado
        self.destroy()


def autenticar(raiz: tk.Misc, ao_abrir=None) -> Optional[Utilizador]:
    """Garante uma sessão iniciada, criando a primeira conta se for preciso.

    Args:
        ao_abrir: chamado com a janela assim que ela existe, antes de se
            esperar por ela. É por aqui que o autoteste percorre o arranque
            verdadeiro em vez de um caminho parecido — e só se descobre que
            uma janela não aparece quem a tenta ver.

    Returns:
        O utilizador autenticado, ou ``None`` se desistiu.
    """
    classe = JanelaLogin if utilizadores.existe_algum() else JanelaPrimeiroAdministrador
    janela = classe(raiz)
    if ao_abrir is not None:
        ao_abrir(janela)
    # A janela pode já ter sido fechada pelo gancho. Esperar por uma janela
    # que não existe é um erro de Tcl, não uma espera.
    if janela.winfo_exists():
        raiz.wait_window(janela)
    utilizador = janela.resultado

    if utilizador is not None:
        utilizadores.iniciar_sessao(utilizador)
    return utilizador
