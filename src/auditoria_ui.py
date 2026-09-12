"""Tela *Configurações → Auditoria*.

Mostra a trilha do que aconteceu, com filtros por tipo de evento. É só
leitura: nada nesta janela apaga registos.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

from core import auditoria, permissoes
from core.auditoria import RegistoAuditoria
from core.log import obter_logger
from core.permissoes import Permissao
from language_manager import carregar_texto

logger = obter_logger(__name__)

#: Filtros oferecidos: (chave de tradução, padrão de evento).
FILTROS = (
    ("auditoria_filtro_tudo", "*"),
    ("tarefas", "tarefa.*"),
    ("plugins", "plugin.*"),
    ("auditoria_filtro_aplicacao", "app.*"),
)

LIMITES = (100, 500, 2000)


class JanelaAuditoria(tk.Toplevel):
    """Lista os registos de auditoria, do mais recente para o mais antigo."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("auditoria"))
        self.geometry("760x460")
        self.transient(master)

        self._filtro_var = tk.StringVar()
        self._limite_var = tk.StringVar(value=str(LIMITES[0]))

        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(
            cabecalho, text=carregar_texto("auditoria"), font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)

        ttk.Button(cabecalho, text=carregar_texto("atualizar_lista"), command=self.recarregar).pack(
            side=tk.RIGHT
        )
        self._seletor_limite = ttk.Combobox(
            cabecalho,
            textvariable=self._limite_var,
            state="readonly",
            width=6,
            values=[str(l) for l in LIMITES],
        )
        self._seletor_limite.pack(side=tk.RIGHT, padx=6)
        self._seletor_limite.bind("<<ComboboxSelected>>", lambda _: self.recarregar())

        self._seletor_filtro = ttk.Combobox(
            cabecalho,
            textvariable=self._filtro_var,
            state="readonly",
            width=18,
            values=[carregar_texto(chave) for chave, _ in FILTROS],
        )
        self._seletor_filtro.current(0)
        self._seletor_filtro.pack(side=tk.RIGHT, padx=6)
        self._seletor_filtro.bind("<<ComboboxSelected>>", lambda _: self.recarregar())

        moldura = ttk.Frame(self)
        moldura.pack(fill=tk.BOTH, expand=True, padx=12)

        colunas = ("momento", "evento", "utilizador", "alvo", "detalhe")
        self.tabela = ttk.Treeview(moldura, columns=colunas, show="headings", height=16)
        larguras = {"momento": 140, "evento": 150, "utilizador": 90, "alvo": 70, "detalhe": 260}
        for coluna in colunas:
            self.tabela.heading(
                coluna, text=carregar_texto(f"auditoria_coluna_{coluna}"), anchor=tk.W
            )
            self.tabela.column(coluna, width=larguras[coluna], anchor=tk.W)

        barra = ttk.Scrollbar(moldura, orient=tk.VERTICAL, command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra.pack(side=tk.RIGHT, fill=tk.Y)

        rodape = ttk.Frame(self)
        rodape.pack(fill=tk.X, padx=12, pady=8)
        self._resumo = ttk.Label(rodape, foreground="#7a8794")
        self._resumo.pack(side=tk.LEFT)
        ttk.Button(rodape, text=carregar_texto("fechar"), command=self.destroy).pack(side=tk.RIGHT)

        self.recarregar()

    # ---------------------------------------------------------------- dados

    def registos(self) -> List[RegistoAuditoria]:
        """Os registos atualmente mostrados."""
        return self._registos

    def recarregar(self) -> None:
        """Relê a trilha com os filtros escolhidos."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        if not permissoes.pode(Permissao.SISTEMA_ADMIN):
            self._registos = []
            self._resumo.config(text=carregar_texto("permissao_negada"))
            return

        padrao = self._padrao_escolhido()
        limite = int(self._limite_var.get() or LIMITES[0])
        self._registos = auditoria.consultar(limite=limite, evento=padrao)

        for registo in self._registos:
            self.tabela.insert(
                "",
                tk.END,
                values=(
                    registo.momento.replace("T", " "),
                    registo.evento,
                    registo.utilizador,
                    registo.alvo,
                    registo.detalhe,
                ),
            )

        self._resumo.config(
            text=carregar_texto(
                "auditoria_resumo", mostrados=len(self._registos), total=auditoria.contar()
            )
        )

    def _padrao_escolhido(self) -> str:
        escolhido = self._filtro_var.get()
        for chave, padrao in FILTROS:
            if carregar_texto(chave) == escolhido:
                return "" if padrao == "*" else padrao
        return ""
