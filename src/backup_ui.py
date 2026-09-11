"""Tela *Configurações → Cópia de segurança*.

Guardar é um botão. Restaurar é uma conversa: mostra-se de quando é a cópia e
de que versão veio, diz-se em voz clara o que vai ser substituído, e só depois
se pergunta. Uma pergunta de sim/não sobre um ficheiro que o utilizador não
consegue ver por dentro não é uma escolha informada.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from core import backup, permissoes
from core.backup import BackupError, Manifesto
from core.log import obter_logger
from core.permissoes import Permissao
from language_manager import carregar_texto

logger = obter_logger(__name__)

COR_NEUTRA = "#7a8794"
COR_AVISO = "#c0392b"

TIPOS = [("ZIP", "*.zip")]


def descrever(manifesto: Manifesto) -> str:
    """O que a cópia é, em texto que se lê antes de decidir."""
    linhas = [
        carregar_texto("backup_de_quando", data=manifesto.data_legivel),
        carregar_texto("backup_da_versao", versao=manifesto.app_version),
    ]
    if manifesto.plugins:
        nomes = ", ".join(sorted(i for i, _ in manifesto.plugins))
        linhas.append(carregar_texto("backup_plugins_registados", plugins=nomes))
    return "\n".join(linhas)


class JanelaBackup(tk.Toplevel):
    """Criar e restaurar cópias de segurança."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("backup"))
        self.geometry("560x360")
        self.resizable(False, False)
        self.transient(master)

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            corpo, text=carregar_texto("backup"), font=("Arial", 14, "bold")
        ).pack(anchor=tk.W)

        ttk.Label(
            corpo,
            text=carregar_texto("backup_o_que_leva"),
            wraplength=500,
            justify=tk.LEFT,
            foreground=COR_NEUTRA,
        ).pack(anchor=tk.W, pady=(8, 0))

        ttk.Separator(corpo).pack(fill=tk.X, pady=14)

        self.botao_criar = ttk.Button(
            corpo, text=carregar_texto("backup_criar"), command=self.criar
        )
        self.botao_criar.pack(anchor=tk.W)
        ttk.Label(
            corpo,
            text=carregar_texto("backup_criar_ajuda"),
            wraplength=500,
            justify=tk.LEFT,
            foreground=COR_NEUTRA,
        ).pack(anchor=tk.W, pady=(2, 0))

        ttk.Separator(corpo).pack(fill=tk.X, pady=14)

        self.botao_restaurar = ttk.Button(
            corpo, text=carregar_texto("backup_restaurar"), command=self.restaurar
        )
        self.botao_restaurar.pack(anchor=tk.W)
        ttk.Label(
            corpo,
            text=carregar_texto("backup_restaurar_ajuda"),
            wraplength=500,
            justify=tk.LEFT,
            foreground=COR_NEUTRA,
        ).pack(anchor=tk.W, pady=(2, 0))

        self.mensagem = ttk.Label(corpo, wraplength=500, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, pady=(14, 0))

        ttk.Button(corpo, text=carregar_texto("fechar"), command=self.destroy).pack(
            anchor=tk.E, pady=(10, 0)
        )

        if not permissoes.pode(Permissao.SISTEMA_ADMIN):
            self.botao_criar.state(["disabled"])
            self.botao_restaurar.state(["disabled"])
            self._dizer(carregar_texto("permissao_negada"), COR_AVISO)

    # ------------------------------------------------------------- apoio

    def _dizer(self, texto: str, cor: str = "#2c7a3f") -> None:
        self.mensagem.configure(text=texto, foreground=cor)

    # ------------------------------------------------------------- ações

    def criar(self) -> Optional[str]:
        """Pede onde guardar e escreve a cópia."""
        destino = filedialog.asksaveasfilename(
            parent=self,
            title=carregar_texto("backup_criar"),
            defaultextension=".zip",
            initialfile=backup.nome_sugerido(),
            filetypes=TIPOS,
        )
        if not destino:
            return None

        try:
            caminho = backup.criar(destino)
        except (BackupError, OSError) as erro:
            logger.exception("Falha ao criar a cópia de segurança.")
            self._dizer(carregar_texto("backup_falhou", erro=str(erro)), COR_AVISO)
            return None

        self._dizer(carregar_texto("backup_criado", caminho=str(caminho)))
        return str(caminho)

    def restaurar(self) -> bool:
        """Lê a cópia, mostra o que é, confirma e repõe."""
        origem = filedialog.askopenfilename(
            parent=self, title=carregar_texto("backup_restaurar"), filetypes=TIPOS
        )
        if not origem:
            return False

        # Inspecionar antes de perguntar: um ficheiro inválido é recusado aqui,
        # sem chegar a assustar ninguém com uma pergunta sobre substituir dados.
        try:
            manifesto = backup.inspecionar(origem)
            backup.verificar_compatibilidade(manifesto)
        except BackupError as erro:
            self._dizer(
                carregar_texto(erro.chave_mensagem, str(erro)) + "\n" + str(erro),
                COR_AVISO,
            )
            return False

        pergunta = (
            descrever(manifesto)
            + "\n\n"
            + carregar_texto("backup_restaurar_aviso")
        )
        if not messagebox.askyesno(
            carregar_texto("backup_restaurar"), pergunta, parent=self
        ):
            return False

        try:
            emergencia = backup.restaurar(origem)
        except (BackupError, OSError) as erro:
            logger.exception("Falha ao restaurar a cópia de segurança.")
            self._dizer(carregar_texto("backup_falhou", erro=str(erro)), COR_AVISO)
            return False

        self._dizer(carregar_texto("backup_restaurado", caminho=str(emergencia)))
        messagebox.showinfo(
            carregar_texto("backup_restaurar"),
            carregar_texto("backup_reiniciar"),
            parent=self,
        )
        return True
