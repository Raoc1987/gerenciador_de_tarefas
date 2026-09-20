"""A concha da aplicação: barra lateral, barra de topo, e o conteúdo.

Substitui o ``ttk.Notebook`` da janela principal — e implementa os quatro
métodos que o resto da aplicação lhe chamava (``add``, ``forget``, ``tab``,
``select``). Foi de propósito: o contrato dos plugins passa por
``AnfitriaoGUI``, que chama ``notebook.add``, e **nenhum plugin instalado
precisa de mudar uma linha** para passar a aparecer na barra lateral.

Porque é que abas horizontais não chegam: uma fila de separadores é legível
até cerca de seis. Um produto com Tarefas, Projetos, Pessoas, Horas, Custos,
Estoque, Manutenção, Analytics, BI, Relatórios, Plugins e Administração tem
doze — e a partir daí a fila ou corta ou encolhe a ponto de deixar de se ler.
Uma barra lateral cresce para baixo, agrupa, e o ecrã tem mais altura do que
largura por onde sobrar.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from aparencia import ESPACO, cores, fonte
from core.log import obter_logger
from language_manager import carregar_texto
from navegacao import registo

logger = obter_logger(__name__)

#: Largura da barra lateral aberta e fechada.
#:
#: 224 é o que chega para "Business Intelligence" sem cortar; 56 é o que chega
#: para a marca e a área de clique continuar confortável.
LARGA = 224
ESTREITA = 56

#: O sino. Um caractere e não um ficheiro, pela mesma razão das marcas da
#: barra lateral: um ícone em ficheiro é uma dependência e um problema de
#: nitidez em cada resolução.
SINO = "🔔"


class Concha(ttk.Frame):
    """Barra lateral + barra de topo + área de conteúdo.

    A área de conteúdo é uma pilha: todos os painéis existem, só um está
    visível. Destruir e reconstruir ao mudar de secção perderia o estado — o
    filtro que a pessoa escolheu, a linha que tinha selecionada — e é o tipo
    de coisa que faz um produto parecer que se esquece.
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)

        self._paineis: Dict[Any, ttk.Frame] = {}
        self._titulos: Dict[Any, str] = {}
        self._ordem: List[Any] = []
        self._botoes: Dict[Any, ttk.Button] = {}
        self._atual: Optional[Any] = None
        self._aberta = True
        self._ao_pesquisar: Optional[Callable[[], None]] = None
        self._ao_comandos: Optional[Callable[[], None]] = None
        self._ao_notificacoes: Optional[Callable[[], None]] = None
        self._por_ler = 0
        self._ao_escolher_empresa: Optional[Callable[[Optional[int]], None]] = None
        self._empresas: List[tuple] = []

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self._construir_lateral()
        self._construir_topo()

        self._area = ttk.Frame(self)
        self._area.grid(row=1, column=1, sticky=tk.NSEW)

    # ------------------------------------------------------------ desenho

    def _construir_lateral(self) -> None:
        c = cores()
        self._lateral = ttk.Frame(self, style="Alta.TFrame", width=LARGA)
        self._lateral.grid(row=0, column=0, rowspan=2, sticky=tk.NS)
        self._lateral.grid_propagate(False)

        topo = ttk.Frame(self._lateral, style="Alta.TFrame",
                         padding=(ESPACO["largo"], ESPACO["confortavel"]))
        topo.pack(fill=tk.X)

        self._marca = ttk.Label(
            topo, text="◈", background=c["superficie_alta"],
            foreground=c["acento"], font=fonte("subtitulo", negrito=True),
        )
        self._marca.pack(side=tk.LEFT)
        self._nome = ttk.Label(
            topo, background=c["superficie_alta"], font=fonte("destaque", negrito=True),
        )
        self._nome.pack(side=tk.LEFT, padx=(ESPACO["normal"], 0))

        self._grupos = ttk.Frame(self._lateral, style="Alta.TFrame")
        self._grupos.pack(fill=tk.BOTH, expand=True)

        # Em baixo, mas dentro de uma moldura própria: solto no fundo da
        # lateral ficava cortado quando a lista de secções crescia.
        rodape = ttk.Frame(self._lateral, style="Alta.TFrame",
                           padding=(ESPACO["normal"], ESPACO["normal"]))
        rodape.pack(side=tk.BOTTOM, fill=tk.X)
        self._botao_recolher = ttk.Button(
            rodape, text="«", width=3, style="Lateral.TButton",
            command=self.alternar_lateral,
        )
        self._botao_recolher.pack(anchor=tk.W)

        ttk.Separator(self, orient=tk.VERTICAL).grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.E)

    def _construir_topo(self) -> None:
        c = cores()
        self._topo = ttk.Frame(self, style="Alta.TFrame",
                               padding=(ESPACO["seccao"], ESPACO["normal"]))
        self._topo.grid(row=0, column=1, sticky=tk.EW)

        self._titulo_pagina = ttk.Label(
            self._topo, background=c["superficie_alta"],
            font=fonte("subtitulo", negrito=True),
        )
        self._titulo_pagina.pack(side=tk.LEFT)

        # O seletor de empresa fica **à esquerda, ao pé do título da secção**,
        # e não no canto com os atalhos. Não é gosto: isto não é uma ação, é o
        # contexto em que tudo o resto se lê. Um número de vendas ao lado de um
        # seletor escondido no canto é um número que se lê mal. É onde o Azure
        # põe a subscrição e o SAP o mandante, pela mesma razão.
        self._empresa_var = tk.StringVar()
        self._seletor_empresa = ttk.Combobox(
            self._topo, textvariable=self._empresa_var, state="readonly", width=22
        )
        self._seletor_empresa.bind("<<ComboboxSelected>>", self._ao_mudar_empresa)

        self._sessao = ttk.Label(
            self._topo, style="Suave.TLabel", background=c["superficie_alta"]
        )
        self._sessao.pack(side=tk.RIGHT, padx=(ESPACO["confortavel"], 0))

        # Encostado à sessão, e não junto aos atalhos: é onde toda a gente já
        # aprendeu a procurar um sino — ao pé de quem está lá dentro, no canto
        # da barra. Um controlo que muda sozinho não é sítio para originalidade.
        # Empacotado antes dos atalhos porque a arrumação é da direita para a
        # esquerda: quem entra primeiro fica mais à direita.
        self._botao_sino = ttk.Button(
            self._topo, text=SINO, width=4, command=self._abrir_notificacoes
        )
        self._botao_sino.pack(side=tk.RIGHT, padx=(ESPACO["normal"], 0))

        # Os dois atalhos ficam à vista: um atalho que ninguém descobre é um
        # atalho que não existe.
        self._botao_comandos = ttk.Button(
            self._topo, text="⌘  Ctrl+K", command=self._abrir_comandos
        )
        self._botao_comandos.pack(side=tk.RIGHT, padx=(ESPACO["normal"], 0))
        self._botao_pesquisa = ttk.Button(
            self._topo, text="🔎  Ctrl+F", command=self._abrir_pesquisa
        )
        self._botao_pesquisa.pack(side=tk.RIGHT)

        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=0, column=1, sticky=tk.EW + tk.S)

    # ---------------------------------------------- compatível com Notebook
    #
    # "Substitui o Notebook" só é verdade se aceitar o que ele aceitava. Um
    # ``tab_id`` do Tk pode ser o widget, o índice, ou o nome do widget em
    # texto — e havia código a usar as três formas. Aceitar só uma tornava a
    # frase acima uma intenção em vez de um facto.

    def _resolver(self, tab_id: Any) -> Optional[Any]:
        """Um widget, um índice ou um nome, para o painel correspondente."""
        if tab_id in self._paineis:
            return tab_id
        if isinstance(tab_id, int):
            if 0 <= tab_id < len(self._ordem):
                return self._ordem[tab_id]
            return None
        texto = str(tab_id)
        for widget in self._ordem:
            if str(widget) == texto:
                return widget
        return None

    def index(self, tab_id: Any = "end") -> int:
        """Posição de um painel, ou quantos há quando ``tab_id`` é ``"end"``."""
        if tab_id == "end":
            return len(self._ordem)
        painel = self._resolver(tab_id)
        return self._ordem.index(painel) if painel is not None else -1


    def add(self, widget: Any, text: str = "", **kwargs) -> None:
        """Acrescenta um painel. Mesma assinatura de ``ttk.Notebook.add``.

        É por aqui que os plugins entram, sem saberem que a barra lateral
        existe: ``AnfitriaoGUI`` continua a chamar ``add`` como sempre chamou.
        """
        if widget in self._paineis:
            return
        self._paineis[widget] = widget
        self._titulos[widget] = text
        self._ordem.append(widget)
        self._redesenhar_lateral()
        if self._atual is None:
            self.select(widget)

    def forget(self, tab_id: Any) -> None:
        """Retira um painel — usado quando um plugin é desativado."""
        widget = self._resolver(tab_id)
        if widget is None:
            return
        self._paineis.pop(widget, None)
        self._titulos.pop(widget, None)
        if widget in self._ordem:
            self._ordem.remove(widget)
        try:
            widget.pack_forget()
        except tk.TclError:  # pragma: no cover - já destruído
            pass
        if self._atual is widget:
            self._atual = None
            if self._ordem:
                self.select(self._ordem[0])
        self._redesenhar_lateral()

    def tab(self, tab_id: Any, option: Optional[str] = None, **kwargs) -> Any:
        """Lê ou muda o título de um painel, como ``ttk.Notebook.tab``."""
        widget = self._resolver(tab_id)
        if widget is None:
            return None
        if "text" in kwargs:
            self._titulos[widget] = kwargs["text"]
            self._redesenhar_lateral()
            if self._atual is widget:
                self._titulo_pagina.configure(text=kwargs["text"])
            return None
        if option == "text":
            return self._titulos.get(widget, "")
        return {"text": self._titulos.get(widget, "")}

    def select(self, tab_id: Optional[Any] = None) -> Any:
        """Mostra um painel. Sem argumento, devolve o que está visível."""
        if tab_id is None:
            return self._atual
        widget = self._resolver(tab_id)
        if widget is None:
            return None
        if self._atual is not None and self._atual is not widget:
            try:
                self._atual.pack_forget()
            except tk.TclError:  # pragma: no cover
                pass
        self._atual = widget
        try:
            widget.pack(in_=self._area, fill=tk.BOTH, expand=True)
        except tk.TclError:  # pragma: no cover - painel já destruído
            logger.exception("Não foi possível mostrar o painel.")
            return None
        self._titulo_pagina.configure(text=self._titulos.get(widget, ""))
        self._marcar_botao_ativo()
        return widget

    def tabs(self) -> tuple:
        """Os nomes dos painéis, pela ordem em que entraram.

        Nomes e não widgets, como o ``ttk.Notebook``: há código que faz
        ``janela.nametowidget(notebook.tabs()[i])``, e devolver objetos
        rebentava-o de uma forma difícil de ler.
        """
        return tuple(str(w) for w in self._ordem)

    # ---------------------------------------------------------- lateral

    def _redesenhar_lateral(self) -> None:
        """Volta a construir a lista, agrupada pelo registo de destinos.

        O que não estiver declarado no registo cai em "principal". É o que
        mantém funcional um plugin escrito antes de os grupos existirem.
        """
        for filho in self._grupos.winfo_children():
            filho.destroy()
        self._botoes = {}

        declarados = {}
        for grupo, destinos in registo.por_grupo():
            for destino in destinos:
                declarados[destino.chave_titulo] = (grupo, destino)

        por_grupo: Dict[str, list] = {g: [] for g in registo.GRUPOS}
        for widget in self._ordem:
            titulo = self._titulos.get(widget, "")
            achado = declarados.get(titulo)
            grupo = achado[0] if achado else registo.GRUPO_PADRAO
            marca = achado[1].marca if achado else "•"
            por_grupo[grupo].append((widget, titulo, marca))

        c = cores()
        for grupo in registo.GRUPOS:
            itens = por_grupo[grupo]
            if not itens:
                continue
            if self._aberta:
                ttk.Label(
                    self._grupos,
                    text=carregar_texto(f"grupo_{grupo}", grupo.upper()).upper(),
                    style="Tenue.TLabel",
                    background=c["superficie_alta"],
                ).pack(anchor=tk.W, padx=ESPACO["largo"],
                       pady=(ESPACO["confortavel"], ESPACO["apertado"]))
            for widget, titulo, marca in itens:
                texto = f"{marca}   {titulo}" if self._aberta else marca
                botao = ttk.Button(
                    self._grupos,
                    text=texto,
                    style="Lateral.TButton",
                    command=lambda w=widget: self.select(w),
                )
                botao.pack(fill=tk.X, padx=ESPACO["normal"], pady=1)
                self._botoes[widget] = botao
        self._marcar_botao_ativo()

    def _marcar_botao_ativo(self) -> None:
        for widget, botao in self._botoes.items():
            estilo = "LateralAtivo.TButton" if widget is self._atual else "Lateral.TButton"
            try:
                botao.configure(style=estilo)
            except tk.TclError:  # pragma: no cover
                pass

    def alternar_lateral(self) -> bool:
        """Abre ou fecha a barra lateral. Devolve se ficou aberta."""
        self._aberta = not self._aberta
        self._lateral.configure(width=LARGA if self._aberta else ESTREITA)
        self._nome.pack_forget() if not self._aberta else self._nome.pack(
            side=tk.LEFT, padx=(ESPACO["normal"], 0)
        )
        self._botao_recolher.configure(text="«" if self._aberta else "»")
        self._redesenhar_lateral()
        return self._aberta

    # ------------------------------------------------------------ topo

    def topo(self) -> ttk.Frame:
        """A barra de topo, para quem precise de lá pôr um controlo próprio."""
        return self._topo

    def definir_produto(self, nome: str) -> None:
        self._nome.configure(text=nome)

    def definir_sessao(self, texto: str) -> None:
        self._sessao.configure(text=texto)

    def ligar_pesquisa(self, funcao: Callable[[], None]) -> None:
        self._ao_pesquisar = funcao

    def ligar_comandos(self, funcao: Callable[[], None]) -> None:
        self._ao_comandos = funcao

    def ligar_notificacoes(self, funcao: Callable[[], None]) -> None:
        self._ao_notificacoes = funcao

    def ligar_empresas(self, funcao: Callable[[Optional[int]], None]) -> None:
        self._ao_escolher_empresa = funcao

    def definir_empresas(
        self, empresas: List[tuple], escolhida: Optional[int] = None
    ) -> None:
        """Põe o seletor de empresa na barra. ``empresas`` é ``[(id, nome)]``.

        **Com menos de duas, o seletor não aparece.** Quem pertence a uma
        empresa já só vê a sua, e um seletor de uma entrada é um controlo que
        promete uma escolha que não existe.
        """
        self._empresas = list(empresas)
        if len(self._empresas) < 2:
            self._seletor_empresa.pack_forget()
            return

        rotulos = [self._rotulo_todas()] + [nome for _, nome in self._empresas]
        self._seletor_empresa.configure(values=rotulos)
        atual = next((n for i, n in self._empresas if i == escolhida), None)
        self._empresa_var.set(atual or self._rotulo_todas())
        if not self._seletor_empresa.winfo_ismapped():
            self._seletor_empresa.pack(side=tk.LEFT, padx=(ESPACO["seccao"], 0))

    def empresa_escolhida(self) -> Optional[int]:
        """O id que o seletor está a mostrar, ou ``None`` para "todas"."""
        escolhido = self._empresa_var.get()
        return next((i for i, n in self._empresas if n == escolhido), None)

    def _rotulo_todas(self) -> str:
        return carregar_texto("empresas_todas", "Todas as empresas")

    def _ao_mudar_empresa(self, _evento=None) -> None:
        if self._ao_escolher_empresa is None:
            return
        self._ao_escolher_empresa(self.empresa_escolhida())

    def definir_por_ler(self, quantas: int) -> None:
        """Põe o número por ler no sino. Zero mostra só o sino.

        Sem número quando não há nada: um "0" permanente é um contador que
        se aprende a ignorar, e o dia em que passar a 1 não se dá por ele.
        """
        self._por_ler = max(0, int(quantas))
        # Acima de noventa e nove o número deixa de informar e passa a
        # desalinhar a barra. "99+" diz a mesma coisa em largura fixa.
        contagem = "99+" if self._por_ler > 99 else str(self._por_ler)
        texto = f"{SINO} {contagem}" if self._por_ler else SINO
        try:
            self._botao_sino.configure(text=texto, width=4 if not self._por_ler else 7)
        except tk.TclError:  # pragma: no cover - janela já destruída
            pass

    def por_ler(self) -> int:
        """O número que o sino está a mostrar."""
        return self._por_ler

    def _abrir_pesquisa(self) -> None:
        if self._ao_pesquisar is not None:
            self._ao_pesquisar()

    def _abrir_comandos(self) -> None:
        if self._ao_comandos is not None:
            self._ao_comandos()

    def _abrir_notificacoes(self) -> None:
        if self._ao_notificacoes is not None:
            self._ao_notificacoes()

    def atualizar_traducoes(self) -> None:
        """Reaplica os textos da concha no idioma atual."""
        self._botao_pesquisa.configure(text=f"🔎  {carregar_texto('atalho_pesquisa', 'Ctrl+F')}")
        self._botao_comandos.configure(text=f"⌘  {carregar_texto('atalho_comandos', 'Ctrl+K')}")
        self.definir_por_ler(self._por_ler)
        self.definir_empresas(self._empresas, self.empresa_escolhida())
        self._redesenhar_lateral()
        if self._atual is not None:
            self._titulo_pagina.configure(text=self._titulos.get(self._atual, ""))
