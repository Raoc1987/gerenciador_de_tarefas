"""A paleta de comandos: escrever o que se quer, em vez de o procurar.

Num produto com doze secções e trinta ações, um menu é uma árvore que é
preciso conhecer para navegar. A paleta inverte isso: escreve-se o que se
quer fazer e a lista reduz-se. Quem não sabe onde está a coisa encontra-a à
mesma, e quem sabe chega lá mais depressa do que pelo rato.

Como tudo o resto neste produto, é um **registo**: a aplicação regista os
seus comandos, um plugin regista os dele, e a paleta não sabe o que nenhum
deles faz. Um comando que exija uma permissão que a sessão não tem não
aparece — oferecer para depois recusar é pior do que não oferecer.
"""

from __future__ import annotations

import tkinter as tk
import unicodedata
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from aparencia import ESPACO, cores, fonte
from core.log import obter_logger
from language_manager import carregar_texto

logger = obter_logger(__name__)

#: Quantos comandos mostrar de uma vez.
#:
#: Uma lista que enche o ecrã deixa de se ler de relance, e quem não vê o que
#: quer nos primeiros escreve mais uma letra em vez de percorrer a lista.
MOSTRAR = 12


def _simples(texto: str) -> str:
    """Sem acentos nem maiúsculas — quem escreve depressa não acentua."""
    sem = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in sem if not unicodedata.combining(c)).lower()


@dataclass(frozen=True)
class Comando:
    """Algo que se pode mandar fazer."""

    id: str
    #: Chave de tradução do que aparece na lista.
    chave_titulo: str
    executar: Callable[[], None]
    #: Chave de tradução do grupo, para a pessoa perceber de onde vem.
    chave_grupo: str = "comandos_geral"
    permissao: Optional[str] = None
    dono: str = ""

    def titulo(self) -> str:
        return carregar_texto(self.chave_titulo, self.chave_titulo)

    def grupo(self) -> str:
        return carregar_texto(self.chave_grupo, "")

    def visivel(self) -> bool:
        if self.permissao is None:
            return True
        from core import permissoes

        return permissoes.pode(self.permissao)


_COMANDOS: Dict[str, Comando] = {}


def registar(
    id: str,
    chave_titulo: str,
    executar: Callable[[], None],
    chave_grupo: str = "comandos_geral",
    permissao: Optional[str] = None,
    dono: str = "",
) -> Comando:
    """Põe um comando na paleta.

    Raises:
        ValueError: id vazio, função que não é chamável, ou — vindo de um
            módulo — id fora do espaço de nomes desse módulo.
    """
    id = (id or "").strip()
    if not id:
        raise ValueError("Um comando precisa de um id.")
    if not callable(executar):
        raise ValueError(f"O comando {id!r} precisa de algo para executar.")
    if dono and not id.startswith(f"{dono}."):
        raise ValueError(
            f"O módulo {dono!r} tem de prefixar os seus comandos com {dono + '.'!r}."
        )
    comando = Comando(id, chave_titulo, executar, chave_grupo, permissao, dono)
    _COMANDOS[id] = comando
    return comando


def esquecer_por_dono(dono: str) -> int:
    """Tira os comandos de um dono — usado quando um plugin sai."""
    if not dono:
        return 0
    saem = [id for id, c in _COMANDOS.items() if c.dono == dono]
    for id in saem:
        _COMANDOS.pop(id, None)
    return len(saem)


def limpar() -> None:
    """Esvazia o registo. Estado global: os testes têm de o repor."""
    _COMANDOS.clear()


def disponiveis() -> List[Comando]:
    """Os comandos que esta sessão pode usar, por título."""
    return sorted(
        (c for c in _COMANDOS.values() if c.visivel()), key=lambda c: c.titulo()
    )


def procurar(termo: str) -> List[Comando]:
    """Os comandos que casam com o termo, os que começam por ele à frente.

    Sem termo, devolve tudo: abrir a paleta e ver uma lista vazia não diz a
    ninguém o que pode escrever lá dentro.
    """
    todos = disponiveis()
    termo = _simples(termo).strip()
    if not termo:
        return todos

    comecam, contem = [], []
    for comando in todos:
        titulo = _simples(comando.titulo())
        if titulo.startswith(termo):
            comecam.append(comando)
        elif termo in titulo or termo in _simples(comando.grupo()):
            contem.append(comando)
    return comecam + contem


class PaletaDeComandos(tk.Toplevel):
    """A janela da paleta: uma caixa de texto e uma lista que encolhe."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.withdraw()
        self.title(carregar_texto("comandos_titulo", "Comandos"))
        self.transient(master)
        self.resizable(False, False)

        c = cores()
        corpo = ttk.Frame(self, padding=ESPACO["confortavel"])
        corpo.pack(fill=tk.BOTH, expand=True)

        self._termo = tk.StringVar()
        self._caixa = ttk.Entry(corpo, textvariable=self._termo, width=52,
                                font=fonte("destaque"))
        self._caixa.pack(fill=tk.X)
        self._termo.trace_add("write", lambda *_: self._filtrar())

        self._lista = tk.Listbox(
            corpo,
            height=MOSTRAR,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            background=c["superficie"],
            foreground=c["texto"],
            selectbackground=c["acento_suave"],
            selectforeground=c["texto"],
            font=fonte("corpo"),
        )
        self._lista.pack(fill=tk.BOTH, expand=True, pady=(ESPACO["normal"], 0))

        self._vazio = ttk.Label(corpo, style="Suave.TLabel")
        self._achados: List[Comando] = []

        # O teclado manda: a paleta existe para não ser preciso o rato.
        self._caixa.bind("<Down>", self._descer)
        self._caixa.bind("<Up>", self._subir)
        self._caixa.bind("<Return>", self._executar)
        self._caixa.bind("<Escape>", lambda _: self.destroy())
        self._lista.bind("<Return>", self._executar)
        self._lista.bind("<Double-Button-1>", self._executar)
        self._lista.bind("<Escape>", lambda _: self.destroy())

        self._filtrar()
        self._centrar()
        self.deiconify()
        self._caixa.focus_set()
        self.grab_set()

    def _centrar(self) -> None:
        self.update_idletasks()
        pai = self.master
        try:
            x = pai.winfo_rootx() + (pai.winfo_width() - self.winfo_width()) // 2
            # Um terço a contar de cima: é onde o olho já está, e deixa a
            # lista crescer para baixo sem sair do ecrã.
            y = pai.winfo_rooty() + pai.winfo_height() // 4
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:  # pragma: no cover - sem pai visível
            pass

    def _filtrar(self) -> None:
        self._achados = procurar(self._termo.get())
        self._lista.delete(0, tk.END)
        for comando in self._achados[:MOSTRAR]:
            grupo = comando.grupo()
            sufixo = f"    {grupo}" if grupo else ""
            self._lista.insert(tk.END, f"{comando.titulo()}{sufixo}")
        if self._achados:
            self._lista.selection_clear(0, tk.END)
            self._lista.selection_set(0)
            self._vazio.pack_forget()
        else:
            self._vazio.configure(
                text=carregar_texto("comandos_sem_resultado", "Nada com esse nome.")
            )
            self._vazio.pack(anchor=tk.W, pady=(ESPACO["normal"], 0))

    def _mover(self, passo: int) -> None:
        if not self._achados:
            return
        atual = self._lista.curselection()
        indice = (atual[0] if atual else 0) + passo
        indice = max(0, min(indice, min(len(self._achados), MOSTRAR) - 1))
        self._lista.selection_clear(0, tk.END)
        self._lista.selection_set(indice)
        self._lista.see(indice)

    def _descer(self, _=None) -> str:
        self._mover(1)
        return "break"

    def _subir(self, _=None) -> str:
        self._mover(-1)
        return "break"

    def _executar(self, _=None) -> str:
        """Corre o comando escolhido e fecha.

        Fecha **antes** de executar: um comando que abra outra janela deixaria
        a paleta por baixo dela, e o ``grab`` da paleta impedia o clique na
        janela nova.
        """
        escolha = self._lista.curselection()
        if not escolha or not self._achados:
            return "break"
        comando = self._achados[escolha[0]]
        self.destroy()
        try:
            comando.executar()
        except Exception:
            # Um comando partido não pode levar a aplicação com ele — é a
            # mesma regra dos plugins, e a paleta vai acabar por correr
            # comandos deles.
            logger.exception("O comando %s falhou.", comando.id)
        return "break"


def abrir(master: tk.Misc) -> PaletaDeComandos:
    """Abre a paleta sobre a janela indicada."""
    return PaletaDeComandos(master)
