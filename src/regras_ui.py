"""Tela *Configurações → Automações*.

Escrever uma regra é escolher três coisas: quando, se, e então. O formulário
segue essa ordem, porque é a ordem em que se pensa.

A lista dos eventos e das ações **vem do sistema**, não de uma caixa de texto:
um nome de evento escrito à mão que não existe dá uma regra que nunca dispara
e não diz porquê — o pior tipo de avaria, porque parece que está tudo bem.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

from core import eventos, permissoes
from core.log import obter_logger
from core.permissoes import Permissao
from language_manager import carregar_texto
from regras import acoes as registo_de_acoes
from regras import motor as motor_de_regras
from regras import repositorio
from regras.modelo import Acao, Condicao, Operador, Regra, RegraInvalidaError

logger = obter_logger(__name__)

COR_NEUTRA = "#7a8794"
COR_ERRO = "#c0392b"

#: Eventos que não fazem sentido numa regra: os do próprio motor (seriam um
#: ciclo) e o padrão que apanha tudo.
def eventos_disponiveis() -> List[str]:
    """Os eventos a que uma regra se pode ligar, mais as famílias."""
    concretos = [
        nome for nome in eventos.eventos_conhecidos() if not nome.startswith("workflow.")
    ]
    familias = sorted({f"{nome.split('.')[0]}.*" for nome in concretos})
    return familias + sorted(concretos)


class JanelaAutomacoes(tk.Toplevel):
    """Ver, criar, ligar, desligar e apagar regras."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("automacoes"))
        self.geometry("780x520")
        self.transient(master)
        self._regras: List[Regra] = []

        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill=tk.X, padx=12, pady=(12, 2))
        ttk.Label(
            cabecalho, text=carregar_texto("automacoes"), font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)
        self.botao_nova = ttk.Button(
            cabecalho, text="+ " + carregar_texto("nova_regra"), command=self.nova_regra
        )
        self.botao_nova.pack(side=tk.RIGHT)

        ttk.Label(
            self,
            text=carregar_texto("automacoes_ajuda"),
            foreground=COR_NEUTRA,
            wraplength=740,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        colunas = ("nome", "evento", "condicoes", "acoes", "estado")
        self.tabela = ttk.Treeview(self, columns=colunas, show="headings", height=12)
        larguras = {"nome": 190, "evento": 150, "condicoes": 170, "acoes": 150, "estado": 80}
        for coluna in colunas:
            self.tabela.heading(coluna, text=carregar_texto(f"coluna_{coluna}"), anchor=tk.W)
            self.tabela.column(coluna, width=larguras[coluna], anchor=tk.W)
        self.tabela.pack(fill=tk.BOTH, expand=True, padx=12)

        self.vazio = ttk.Label(
            self,
            text=carregar_texto("automacoes_vazio"),
            foreground=COR_NEUTRA,
            wraplength=740,
            justify=tk.LEFT,
        )

        self.mensagem = ttk.Label(self, wraplength=740, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, padx=12, pady=(6, 0))

        acoes_frame = ttk.Frame(self)
        acoes_frame.pack(fill=tk.X, padx=12, pady=10)
        self._botoes = {
            "estado": ttk.Button(
                acoes_frame, text=carregar_texto("ativar_desativar"), command=self.alternar
            ),
            "remover": ttk.Button(
                acoes_frame, text=carregar_texto("remover"), command=self.remover
            ),
        }
        for botao in self._botoes.values():
            botao.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(acoes_frame, text=carregar_texto("fechar"), command=self.destroy).pack(
            side=tk.RIGHT
        )

        self.recarregar()

    # ---------------------------------------------------------------- dados

    def regras(self) -> List[Regra]:
        """As regras mostradas."""
        return list(self._regras)

    def recarregar(self) -> None:
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)

        pode = permissoes.pode(Permissao.SISTEMA_ADMIN)
        self.botao_nova.state(["!disabled"] if pode else ["disabled"])
        for botao in self._botoes.values():
            botao.state(["!disabled"] if pode else ["disabled"])
        if not pode:
            self._regras = []
            self._dizer(carregar_texto("permissao_negada"), COR_ERRO)
            return

        self._regras = repositorio.listar()
        for regra in self._regras:
            self.tabela.insert(
                "",
                tk.END,
                iid=str(regra.id),
                values=(
                    regra.nome,
                    regra.evento,
                    self._resumir_condicoes(regra),
                    ", ".join(a.nome for a in regra.acoes),
                    carregar_texto("regra_ativa" if regra.ativa else "regra_inativa"),
                ),
            )

        if self._regras:
            self.vazio.pack_forget()
        else:
            self.vazio.pack(anchor=tk.W, padx=12, pady=(4, 0))

    @staticmethod
    def _resumir_condicoes(regra: Regra) -> str:
        if not regra.condicoes:
            return carregar_texto("sem_condicoes")
        return "; ".join(
            f"{c.campo} {carregar_texto('op_' + c.operador.value, c.operador.value)}"
            + ("" if c.operador in {Operador.EXISTE, Operador.VAZIO} else f" {c.valor}")
            for c in regra.condicoes
        )

    def selecionada(self) -> Optional[Regra]:
        selecao = self.tabela.selection()
        if not selecao:
            self._dizer(carregar_texto("selecione_regra"), COR_NEUTRA)
            return None
        return next((r for r in self._regras if str(r.id) == selecao[0]), None)

    def _dizer(self, texto: str, cor: str = "#2c7a3f") -> None:
        self.mensagem.configure(text=texto, foreground=cor)

    # ---------------------------------------------------------------- ações

    def nova_regra(self) -> Optional[Regra]:
        if not registo_de_acoes.disponiveis():
            # Sem ações registadas, uma regra não pode fazer nada. Dizê-lo é
            # melhor do que oferecer um formulário que não dá para submeter.
            self._dizer(carregar_texto("sem_acoes"), COR_ERRO)
            return None

        dialogo = DialogoRegra(self)
        self.wait_window(dialogo)
        if dialogo.resultado is not None:
            self.recarregar()
            self._dizer(carregar_texto("regra_criada", nome=dialogo.resultado.nome))
        return dialogo.resultado

    def alternar(self) -> None:
        regra = self.selecionada()
        if regra is None:
            return
        repositorio.definir_ativa(regra.id, not regra.ativa)
        self.recarregar()

    def remover(self) -> None:
        regra = self.selecionada()
        if regra is None:
            return
        if not messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("confirmar_remocao", item=regra.nome),
            parent=self,
        ):
            return
        repositorio.remover(regra.id)
        self.recarregar()


class DialogoRegra(tk.Toplevel):
    """Quando, se, então — pela ordem em que se pensa."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title(carregar_texto("nova_regra"))
        self.resizable(False, False)
        self.transient(master)
        self.resultado: Optional[Regra] = None

        corpo = ttk.Frame(self, padding=16)
        corpo.pack(fill=tk.BOTH, expand=True)

        ttk.Label(corpo, text=carregar_texto("nome")).grid(row=0, column=0, sticky=tk.W)
        self.entrada_nome = ttk.Entry(corpo, width=38)
        self.entrada_nome.grid(row=0, column=1, pady=4, padx=(8, 0))

        # --- quando
        ttk.Label(corpo, text=carregar_texto("quando"), font=("Arial", 10, "bold")).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 2)
        )
        self.evento_var = tk.StringVar()
        self.seletor_evento = ttk.Combobox(
            corpo, textvariable=self.evento_var, state="readonly", width=36,
            values=eventos_disponiveis(),
        )
        self.seletor_evento.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)
        if self.seletor_evento["values"]:
            self.seletor_evento.current(0)

        # --- se (opcional)
        ttk.Label(corpo, text=carregar_texto("se"), font=("Arial", 10, "bold")).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 2)
        )
        condicao = ttk.Frame(corpo)
        condicao.grid(row=4, column=0, columnspan=2, sticky=tk.W)
        self.entrada_campo = ttk.Entry(condicao, width=14)
        self.entrada_campo.pack(side=tk.LEFT)
        self.operador_var = tk.StringVar(value=Operador.EXISTE.value)
        ttk.Combobox(
            condicao, textvariable=self.operador_var, state="readonly", width=14,
            values=[o.value for o in Operador],
        ).pack(side=tk.LEFT, padx=4)
        self.entrada_valor = ttk.Entry(condicao, width=12)
        self.entrada_valor.pack(side=tk.LEFT)
        ttk.Label(
            corpo, text=carregar_texto("se_ajuda"), foreground=COR_NEUTRA, wraplength=360,
            justify=tk.LEFT,
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W)

        # --- então
        ttk.Label(corpo, text=carregar_texto("entao"), font=("Arial", 10, "bold")).grid(
            row=6, column=0, columnspan=2, sticky=tk.W, pady=(10, 2)
        )
        self.acao_var = tk.StringVar()
        disponiveis = [a.nome for a in registo_de_acoes.disponiveis()]
        self.seletor_acao = ttk.Combobox(
            corpo, textvariable=self.acao_var, state="readonly", width=36, values=disponiveis
        )
        self.seletor_acao.grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=2)
        if disponiveis:
            self.seletor_acao.current(0)

        ttk.Label(corpo, text=carregar_texto("texto_da_acao")).grid(
            row=8, column=0, sticky=tk.W, pady=(6, 0)
        )
        self.entrada_texto = ttk.Entry(corpo, width=38)
        self.entrada_texto.grid(row=8, column=1, pady=(6, 0), padx=(8, 0))
        ttk.Label(
            corpo, text=carregar_texto("texto_da_acao_ajuda"), foreground=COR_NEUTRA,
            wraplength=360, justify=tk.LEFT,
        ).grid(row=9, column=0, columnspan=2, sticky=tk.W)

        self.mensagem = ttk.Label(corpo, foreground=COR_ERRO, wraplength=360, justify=tk.LEFT)
        self.mensagem.grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        botoes = ttk.Frame(corpo)
        botoes.grid(row=11, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(botoes, text=carregar_texto("guardar"), command=self.guardar).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(botoes, text=carregar_texto("cancelar"), command=self.destroy).pack(
            side=tk.LEFT
        )

    def guardar(self) -> Optional[Regra]:
        """Valida e guarda. O erro fica na janela, não numa exceção."""
        campo = self.entrada_campo.get().strip()
        condicoes = []
        if campo:
            condicoes.append(
                Condicao(campo, Operador(self.operador_var.get()), self.entrada_valor.get().strip())
            )

        argumentos = {}
        texto = self.entrada_texto.get().strip()
        if texto:
            # As duas ações incluídas usam nomes diferentes para o mesmo campo;
            # enviar ambos evita obrigar quem escreve a saber qual é qual.
            argumentos = {"descricao": texto, "texto": texto}

        try:
            self.resultado = repositorio.criar(
                self.entrada_nome.get(),
                self.evento_var.get(),
                condicoes=condicoes,
                acoes=[Acao(self.acao_var.get(), argumentos)],
                criada_por=permissoes.sessao().utilizador,
            )
        except RegraInvalidaError as erro:
            self.mensagem.configure(text=str(erro))
            return None

        self.destroy()
        return self.resultado
