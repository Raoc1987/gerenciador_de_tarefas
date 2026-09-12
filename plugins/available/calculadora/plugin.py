"""Calculadora — simples, científica, conversões e financeira.

Classificação (ADR-0004): **Plugin**. Não é Core (nenhum módulo precisa dela),
não é Module (não tem domínio de negócio nem dados de ninguém), não é Agent
(calcula, não decide). É uma ferramenta opcional, e desinstala-se sem deixar
nada para trás.

Não pede **nenhuma** permissão e não traz nenhuma: não lê tarefas, não escreve
no inventário, não toca em contas. A única coisa que guarda é a preferência de
ângulo, na sua própria configuração.

As contas vivem em :mod:`calculo`, :mod:`conversoes` e :mod:`financeiro`, que
não sabem o que é uma janela. Isto aqui é só a janela.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from core.plugin_api import Plugin

from . import conversoes, financeiro
from .calculo import Angulo, Calculadora, ErroDeCalculo

COR_ERRO = "#c0392b"
COR_NEUTRA = "#7a8794"
CHAVE_ANGULO = "angulo"


class _Painel(ttk.Frame):
    """Base: acesso à tradução e uma linha de mensagem."""

    def __init__(self, master: tk.Misc, contexto) -> None:
        super().__init__(master, padding=12)
        self._contexto = contexto

    def _t(self, chave: str, **formatacao) -> str:
        return self._contexto.traduzir(chave, chave, **formatacao)

    def _erro(self, erro: Exception) -> str:
        """Mensagem traduzida do erro, com o detalhe por baixo."""
        chave = getattr(erro, "chave_mensagem", "calc_erro")
        return f"{self._t(chave)} {erro}".strip()


class PainelSimples(_Painel):
    """As quatro operações, com teclado no ecrã e a memória clássica."""

    TECLAS = [
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "%", "+"],
    ]

    def __init__(self, master: tk.Misc, contexto, calculadora: Calculadora) -> None:
        super().__init__(master, contexto)
        self._calculadora = calculadora
        self.memoria = 0.0

        self.entrada = ttk.Entry(self, font=("Consolas", 20), justify=tk.RIGHT)
        self.entrada.pack(fill=tk.X)
        self.entrada.bind("<Return>", lambda _: self.calcular())

        self.mensagem = ttk.Label(self, wraplength=460, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, pady=(6, 8))

        grelha = ttk.Frame(self)
        grelha.pack()
        for linha, teclas in enumerate(self.TECLAS):
            for coluna, tecla in enumerate(teclas):
                ttk.Button(
                    grelha, text=tecla, width=5, command=lambda t=tecla: self.escrever(t)
                ).grid(row=linha, column=coluna, padx=2, pady=2)

        extras = ttk.Frame(self)
        extras.pack(pady=(8, 0))
        for rotulo, acao in (
            ("=", self.calcular),
            ("C", self.limpar),
            ("←", self.apagar),
            ("M+", self.guardar_memoria),
            ("MR", self.usar_memoria),
        ):
            ttk.Button(extras, text=rotulo, width=5, command=acao).pack(side=tk.LEFT, padx=2)

    # ------------------------------------------------------------- ações

    def escrever(self, texto: str) -> None:
        self.entrada.insert(tk.END, texto)

    def limpar(self) -> None:
        self.entrada.delete(0, tk.END)
        self.mensagem.configure(text="")

    def apagar(self) -> None:
        self.entrada.delete(len(self.entrada.get()) - 1, tk.END)

    def calcular(self) -> Optional[float]:
        """Calcula o que está escrito e põe o resultado no lugar."""
        expressao = self.entrada.get().strip()
        if not expressao:
            return None
        try:
            resultado = self._calculadora.avaliar(expressao)
        except ErroDeCalculo as erro:
            self.mensagem.configure(text=self._erro(erro), foreground=COR_ERRO)
            return None

        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, formatar(resultado))
        self.mensagem.configure(text=f"{expressao} =", foreground=COR_NEUTRA)
        return resultado

    def guardar_memoria(self) -> None:
        resultado = self.calcular()
        if resultado is not None:
            self.memoria = resultado
            self.mensagem.configure(
                text=self._t("memoria_guardada", valor=formatar(resultado)),
                foreground=COR_NEUTRA,
            )

    def usar_memoria(self) -> None:
        self.escrever(formatar(self.memoria))


class PainelCientifico(_Painel):
    """Expressão escrita por extenso, com as funções à mão e histórico."""

    FUNCOES = [
        ["sin(", "cos(", "tan(", "pi"],
        ["asin(", "acos(", "atan(", "e"],
        ["ln(", "log(", "exp(", "^"],
        ["raiz(", "fact(", "abs(", "%"],
    ]

    def __init__(self, master: tk.Misc, contexto, calculadora: Calculadora) -> None:
        super().__init__(master, contexto)
        self._calculadora = calculadora
        self.historico: List[str] = []

        self.entrada = ttk.Entry(self, font=("Consolas", 16))
        self.entrada.pack(fill=tk.X)
        self.entrada.bind("<Return>", lambda _: self.calcular())

        opcoes = ttk.Frame(self)
        opcoes.pack(fill=tk.X, pady=(8, 0))
        self.angulo_var = tk.StringVar(value=calculadora.angulo.value)
        for modo in (Angulo.GRAUS, Angulo.RADIANOS):
            ttk.Radiobutton(
                opcoes,
                text=self._t(f"angulo_{modo.value}"),
                value=modo.value,
                variable=self.angulo_var,
                command=self.mudar_angulo,
            ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(opcoes, text="=", width=5, command=self.calcular).pack(side=tk.RIGHT)

        grelha = ttk.Frame(self)
        grelha.pack(pady=8)
        for linha, teclas in enumerate(self.FUNCOES):
            for coluna, tecla in enumerate(teclas):
                ttk.Button(
                    grelha, text=tecla.rstrip("("), width=7,
                    command=lambda t=tecla: self.entrada.insert(tk.END, t),
                ).grid(row=linha, column=coluna, padx=2, pady=2)

        self.mensagem = ttk.Label(self, wraplength=460, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W)

        ttk.Label(self, text=self._t("historico"), foreground=COR_NEUTRA).pack(
            anchor=tk.W, pady=(8, 2)
        )
        self.lista = tk.Listbox(self, height=6, font=("Consolas", 10))
        self.lista.pack(fill=tk.BOTH, expand=True)
        self.lista.bind("<Double-Button-1>", lambda _: self.reutilizar())

    def mudar_angulo(self) -> None:
        """Guarda a preferência: é a única coisa que este plugin persiste."""
        self._calculadora.angulo = Angulo(self.angulo_var.get())
        config = self._contexto.config()
        config[CHAVE_ANGULO] = self._calculadora.angulo.value
        self._contexto.guardar_config(config)

    def calcular(self) -> Optional[float]:
        expressao = self.entrada.get().strip()
        if not expressao:
            return None
        try:
            resultado = self._calculadora.avaliar(expressao)
        except ErroDeCalculo as erro:
            self.mensagem.configure(text=self._erro(erro), foreground=COR_ERRO)
            return None

        texto = f"{expressao} = {formatar(resultado)}"
        self.historico.append(texto)
        self.lista.insert(0, texto)
        self.mensagem.configure(text=formatar(resultado), foreground="")
        return resultado

    def reutilizar(self) -> None:
        """Traz de volta uma conta anterior, para a continuar."""
        selecao = self.lista.curselection()
        if not selecao:
            return
        anterior = self.lista.get(selecao[0]).split(" = ")[-1]
        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, anterior)


class PainelConversoes(_Painel):
    """Um valor visto em todas as unidades da mesma família."""

    def __init__(self, master: tk.Misc, contexto) -> None:
        super().__init__(master, contexto)

        formulario = ttk.Frame(self)
        formulario.pack(fill=tk.X)

        ttk.Label(formulario, text=self._t("familia")).grid(row=0, column=0, sticky=tk.W)
        self.familia_var = tk.StringVar(value="comprimento")
        self.seletor_familia = ttk.Combobox(
            formulario, textvariable=self.familia_var, state="readonly", width=18,
            values=conversoes.familias(),
        )
        self.seletor_familia.grid(row=0, column=1, padx=(8, 0), pady=4)
        self.seletor_familia.bind("<<ComboboxSelected>>", lambda _: self.mudar_familia())

        ttk.Label(formulario, text=self._t("valor")).grid(row=1, column=0, sticky=tk.W)
        self.entrada = ttk.Entry(formulario, width=20)
        self.entrada.grid(row=1, column=1, padx=(8, 0), pady=4)
        self.entrada.insert(0, "1")
        self.entrada.bind("<Return>", lambda _: self.converter())

        ttk.Label(formulario, text=self._t("unidade")).grid(row=2, column=0, sticky=tk.W)
        self.unidade_var = tk.StringVar()
        self.seletor_unidade = ttk.Combobox(
            formulario, textvariable=self.unidade_var, state="readonly", width=18
        )
        self.seletor_unidade.grid(row=2, column=1, padx=(8, 0), pady=4)

        ttk.Button(formulario, text=self._t("converter"), command=self.converter).grid(
            row=3, column=1, sticky=tk.W, padx=(8, 0), pady=(6, 0)
        )

        self.mensagem = ttk.Label(self, wraplength=460, justify=tk.LEFT)
        self.mensagem.pack(anchor=tk.W, pady=(8, 4))

        self.tabela = ttk.Treeview(
            self, columns=("unidade", "valor"), show="headings", height=9
        )
        self.tabela.heading("unidade", text=self._t("unidade"), anchor=tk.W)
        self.tabela.heading("valor", text=self._t("valor"), anchor=tk.W)
        self.tabela.column("unidade", width=140)
        self.tabela.column("valor", width=220)
        self.tabela.pack(fill=tk.BOTH, expand=True)

        self.mudar_familia()

    def mudar_familia(self) -> None:
        unidades = conversoes.unidades_de(self.familia_var.get())
        self.seletor_unidade.configure(values=unidades)
        self.unidade_var.set(unidades[0])
        self.converter()

    def converter(self) -> bool:
        """Mostra o valor em todas as unidades da família escolhida."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)
        try:
            valor = float(self.entrada.get().strip().replace(",", "."))
        except ValueError:
            self.mensagem.configure(text=self._t("calc_valor_invalido"), foreground=COR_ERRO)
            return False

        try:
            linhas = conversoes.tabela(valor, self.unidade_var.get(), self.familia_var.get())
        except conversoes.ConversaoError as erro:
            self.mensagem.configure(text=self._erro(erro), foreground=COR_ERRO)
            return False

        for unidade, convertido in linhas:
            self.tabela.insert("", tk.END, values=(unidade, formatar(convertido)))
        self.mensagem.configure(text="", foreground="")
        return True


class PainelFinanceiro(_Painel):
    """Empréstimos e juros — os dois cálculos que se fazem antes de assinar."""

    def __init__(self, master: tk.Misc, contexto) -> None:
        super().__init__(master, contexto)

        formulario = ttk.Frame(self)
        formulario.pack(fill=tk.X)

        self.campos = {}
        for linha, (chave, inicial) in enumerate(
            (("capital", "100000"), ("taxa_anual", "6"), ("meses", "360"))
        ):
            ttk.Label(formulario, text=self._t(chave)).grid(row=linha, column=0, sticky=tk.W)
            entrada = ttk.Entry(formulario, width=18)
            entrada.grid(row=linha, column=1, padx=(8, 0), pady=4)
            entrada.insert(0, inicial)
            self.campos[chave] = entrada

        # A taxa anual pode virar mensal de duas maneiras diferentes, e a
        # escolha muda o resultado. Quem calcula é que decide, não o programa.
        ttk.Label(formulario, text=self._t("conversao_taxa")).grid(row=3, column=0, sticky=tk.W)
        self.modo_taxa = tk.StringVar(value="nominal")
        modos = ttk.Frame(formulario)
        modos.grid(row=3, column=1, sticky=tk.W, padx=(8, 0))
        for valor in ("nominal", "equivalente"):
            ttk.Radiobutton(
                modos, text=self._t(f"taxa_{valor}"), value=valor, variable=self.modo_taxa
            ).pack(side=tk.LEFT, padx=(0, 8))

        acoes = ttk.Frame(self)
        acoes.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(acoes, text=self._t("calcular_emprestimo"), command=self.emprestimo).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(acoes, text=self._t("calcular_poupanca"), command=self.poupanca).pack(
            side=tk.LEFT
        )

        self.resumo = ttk.Label(self, wraplength=460, justify=tk.LEFT, font=("Arial", 10, "bold"))
        self.resumo.pack(anchor=tk.W, pady=(10, 4))

        self.tabela = ttk.Treeview(
            self,
            columns=("n", "prestacao", "juros", "amortizacao", "saldo"),
            show="headings",
            height=9,
        )
        for coluna, largura in (
            ("n", 50), ("prestacao", 110), ("juros", 110), ("amortizacao", 120), ("saldo", 120)
        ):
            self.tabela.heading(coluna, text=self._t(f"coluna_{coluna}"), anchor=tk.W)
            self.tabela.column(coluna, width=largura, anchor=tk.W)
        self.tabela.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------- ações

    def _valores(self):
        return (
            self.campos["capital"].get().strip().replace(",", "."),
            self.campos["taxa_anual"].get().strip().replace(",", "."),
            self.campos["meses"].get().strip(),
        )

    def _taxa_do_periodo(self, taxa_anual: str):
        anual = financeiro.Decimal(str(taxa_anual)) / financeiro.Decimal(100)
        if self.modo_taxa.get() == "equivalente":
            return financeiro.taxa_equivalente(anual)
        return financeiro.taxa_nominal_para_periodo(anual)

    def emprestimo(self) -> bool:
        """Prestação, total pago e a tabela mês a mês."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)
        capital, taxa_anual, meses = self._valores()

        try:
            taxa = self._taxa_do_periodo(taxa_anual)
            parcelas = financeiro.amortizacao(capital, taxa, meses)
        except (financeiro.FinanceiroError, ArithmeticError) as erro:
            self.resumo.configure(text=self._erro(erro), foreground=COR_ERRO)
            return False

        for parcela in parcelas:
            self.tabela.insert(
                "",
                tk.END,
                values=(
                    parcela.numero,
                    f"{parcela.prestacao}",
                    f"{parcela.juros}",
                    f"{parcela.amortizacao}",
                    f"{parcela.saldo}",
                ),
            )
        self.resumo.configure(
            text=self._t(
                "resumo_emprestimo",
                prestacao=parcelas[0].prestacao,
                total=financeiro.total_pago(parcelas),
                juros=financeiro.total_juros(parcelas),
            ),
            foreground="",
        )
        return True

    def poupanca(self) -> bool:
        """O mesmo dinheiro visto ao contrário: quanto rende se for aplicado."""
        for linha in self.tabela.get_children():
            self.tabela.delete(linha)
        capital, taxa_anual, meses = self._valores()
        try:
            taxa = self._taxa_do_periodo(taxa_anual)
            futuro = financeiro.juros_compostos(capital, taxa, meses)
        except (financeiro.FinanceiroError, ArithmeticError) as erro:
            self.resumo.configure(text=self._erro(erro), foreground=COR_ERRO)
            return False

        rendimento = futuro - financeiro.dinheiro(capital)
        self.resumo.configure(
            text=self._t("resumo_poupanca", futuro=futuro, juros=rendimento),
            foreground="",
        )
        return True


def formatar(valor) -> str:
    """Número legível: sem casas a mais, e sem notação científica à toa."""
    numero = float(valor)
    if numero == int(numero) and abs(numero) < 1e15:
        return str(int(numero))
    texto = f"{numero:.10g}"
    return texto


class PainelCalculadora(ttk.Frame):
    """As quatro modalidades, em abas."""

    def __init__(self, master: tk.Misc, contexto) -> None:
        super().__init__(master)
        angulo = contexto.config().get(CHAVE_ANGULO, Angulo.GRAUS.value)
        try:
            self.calculadora = Calculadora(Angulo(angulo))
        except ValueError:  # configuração editada à mão
            self.calculadora = Calculadora()

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill=tk.BOTH, expand=True)

        self.simples = PainelSimples(self.abas, contexto, self.calculadora)
        self.cientifico = PainelCientifico(self.abas, contexto, self.calculadora)
        self.conversoes = PainelConversoes(self.abas, contexto)
        self.financeiro = PainelFinanceiro(self.abas, contexto)

        for painel, chave in (
            (self.simples, "modo_simples"),
            (self.cientifico, "modo_cientifico"),
            (self.conversoes, "modo_conversoes"),
            (self.financeiro, "modo_financeiro"),
        ):
            self.abas.add(painel, text=contexto.traduzir(chave, chave))


class CalculadoraPlugin(Plugin):
    """Ciclo de vida. Não pede permissões porque não toca em dados de ninguém."""

    def __init__(self, contexto) -> None:
        super().__init__(contexto)
        self._painel: Optional[PainelCalculadora] = None

    def ativar(self) -> None:
        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba", "Calculadora"),
            self._construir,
        )

    def _construir(self, pai) -> ttk.Frame:
        self._painel = PainelCalculadora(pai, self.contexto)
        return self._painel

    def desativar(self) -> None:
        self._painel = None


PLUGIN_CLASS = CalculadoraPlugin
