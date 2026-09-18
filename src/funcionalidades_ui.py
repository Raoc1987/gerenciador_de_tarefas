"""Tela *Configurações → Funcionalidades*.

Cada linha diz o que a funcionalidade é e **o que se perde ao desligá-la**.
Uma lista de interruptores com nomes técnicos ao lado obriga a experimentar
para descobrir o que fazem, e experimentar em produção sai caro.

Desligar tem efeito na próxima abertura da aplicação: as abas e o menu são
construídos no arranque. Dizê-lo aqui é melhor do que deixar alguém a carregar
no interruptor à espera de ver alguma coisa mudar.
"""

from __future__ import annotations

from aparencia import cores, fonte
import tkinter as tk
from tkinter import ttk
from typing import Dict, List

from core import funcionalidades, permissoes
from core.funcionalidades import Estado
from core.log import obter_logger
from core.permissoes import Permissao, PermissaoNegadaError
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_NEUTRA = cores()["texto_suave"]
COR_AVISO = cores()["mau"]


class JanelaFuncionalidades(tk.Toplevel):
    """Ligar e desligar partes do produto nesta instalação."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("funcionalidades"))
        self.geometry("600x440")
        self.transient(master)
        self._variaveis: Dict[str, tk.BooleanVar] = {}
        self._estados: List[Estado] = []

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            corpo, text=carregar_texto("funcionalidades"), font=fonte("subtitulo", negrito=True)
        ).pack(anchor=tk.W)
        ttk.Label(
            corpo,
            text=carregar_texto("funcionalidades_ajuda"),
            wraplength=540,
            justify=tk.LEFT,
            foreground=COR_NEUTRA,
        ).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(corpo).pack(fill=tk.X, pady=12)

        self.lista = ttk.Frame(corpo)
        self.lista.pack(fill=tk.BOTH, expand=True)

        self.mensagem = ttk.Label(corpo, wraplength=540, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, pady=(10, 0))

        acoes = ttk.Frame(corpo)
        acoes.pack(fill=tk.X, pady=(10, 0))
        self.botao_repor = ttk.Button(
            acoes, text=carregar_texto("repor_origem"), command=self.repor
        )
        self.botao_repor.pack(side=tk.LEFT)
        ttk.Button(acoes, text=carregar_texto("fechar"), command=self.destroy).pack(
            side=tk.RIGHT
        )

        self.recarregar()

    # ---------------------------------------------------------------- dados

    def estados(self) -> List[Estado]:
        """As funcionalidades mostradas."""
        return list(self._estados)

    def recarregar(self) -> None:
        """Relê o estado e redesenha as linhas."""
        for filho in self.lista.winfo_children():
            filho.destroy()
        self._variaveis.clear()

        pode = permissoes.pode(Permissao.SISTEMA_ADMIN)
        self._estados = funcionalidades.listar()
        self.botao_repor.state(["!disabled"] if pode else ["disabled"])

        for estado in self._estados:
            self._desenhar(estado, pode)

        if not pode:
            self._dizer(carregar_texto("permissao_negada"), COR_AVISO)

    def _desenhar(self, estado: Estado, pode: bool) -> None:
        linha = ttk.Frame(self.lista)
        linha.pack(fill=tk.X, pady=(0, 10))

        variavel = tk.BooleanVar(value=estado.ativa)
        self._variaveis[estado.chave] = variavel

        interruptor = ttk.Checkbutton(
            linha,
            text=carregar_texto(estado.funcionalidade.chave_nome, estado.chave),
            variable=variavel,
            command=lambda chave=estado.chave: self.alternar(chave),
        )
        interruptor.pack(anchor=tk.W)
        # Uma essencial aparece ligada e travada, em vez de desaparecer: quem
        # procura a cópia de segurança nesta lista tem de perceber porque não
        # a pode desligar, não ficar a pensar que se esqueceram dela.
        if not pode or estado.funcionalidade.essencial:
            interruptor.state(["disabled"])

        texto = carregar_texto(estado.funcionalidade.chave_descricao, "")
        if estado.funcionalidade.essencial:
            texto = (texto + " " + carregar_texto("funcionalidade_essencial")).strip()
        if texto:
            ttk.Label(
                linha,
                text=texto,
                wraplength=520,
                justify=tk.LEFT,
                foreground=COR_NEUTRA,
            ).pack(anchor=tk.W, padx=(22, 0))

    def _dizer(self, texto: str, cor: str = cores()["bom"]) -> None:
        self.mensagem.configure(text=texto, foreground=cor)

    # ---------------------------------------------------------------- ações

    def alternar(self, chave: str) -> bool:
        """Aplica o que o interruptor passou a dizer."""
        variavel = self._variaveis[chave]
        pretendido = bool(variavel.get())
        try:
            funcionalidades.definir(chave, pretendido)
        except (PermissaoNegadaError, ValueError) as erro:
            logger.warning("Funcionalidade %s não alterada: %s", chave, erro)
            variavel.set(funcionalidades.ativa(chave))  # o interruptor não mente
            self._dizer(str(erro), COR_AVISO)
            return False

        self._dizer(carregar_texto("funcionalidades_reiniciar"))
        return True

    def repor(self) -> None:
        """Volta tudo aos valores de origem."""
        try:
            funcionalidades.repor()
        except PermissaoNegadaError as erro:
            self._dizer(str(erro), COR_AVISO)
            return
        self.recarregar()
        self._dizer(carregar_texto("funcionalidades_reiniciar"))
