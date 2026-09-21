"""Um contentor que se desloca na vertical quando o que tem lá dentro não cabe.

Existe por causa de uma medição, não de uma ideia: a 940×620 — que era o
**mínimo que a própria aplicação declarava** — a caixa "Análise" ficava
abaixo da dobra e não havia como lá chegar. O dado estava calculado, estava
desenhado, e era inalcançável. É o pior tipo de defeito de interface, porque
não dá erro nenhum.

Três regras, todas com uma razão:

**A barra só aparece quando é precisa.** Uma barra permanentemente
desativada é ruído a dizer "isto podia deslocar-se" num ecrã onde não se
desloca.

**A largura de dentro segue a de fora.** Sem isto, a grelha lá dentro nunca
recebia a largura real e ficava sempre com quatro colunas, mesmo numa janela
estreita — o contrário do que a grelha existe para fazer.

**O teclado desloca, não só a roda.** Um ecrã que só se percorre com rato é
um ecrã que metade da acessibilidade não tem. ``Up``, ``Down``, ``Prior`` e
``Next`` fazem o mesmo que a roda.

E uma coisa que só se descobriu a medir: **quem muda o conteúdo tem de dizer**,
com :meth:`Rolo.sincronizar`. Os ``<Configure>`` chegam sozinhos na maioria
dos casos, mas não quando o conteúdo que desapareceu estava *fora da vista* —
o Tk não reporta geometria de widgets que ninguém está a ver. O resultado era
uma barra a dizer que havia mais para baixo num painel que já cabia todo.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from aparencia import cores
from core.log import obter_logger

logger = obter_logger(__name__)

#: Quantas "linhas" de deslocamento vale um estalo da roda do rato.
#:
#: O Windows manda ``delta`` em múltiplos de 120; dividir por isso dá o
#: número de estalos, e cada estalo vale isto.
LINHAS_POR_ESTALO = 3


class Rolo(ttk.Frame):
    """Um painel com deslocamento vertical. O conteúdo vai em :attr:`interior`.

    Uso::

        rolo = Rolo(pai)
        rolo.pack(fill=tk.BOTH, expand=True)
        grelha = Grelha(rolo.interior)
        grelha.pack(fill=tk.BOTH, expand=True)
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)

        # `highlightthickness=0` e `borderwidth=0`: o Canvas traz uma moldura
        # que não pertence a desenho nenhum do produto, e que se via como uma
        # linha cinzenta a toda a volta do painel.
        #
        # E o fundo é posto à mão porque um Canvas não é um widget ttk e não
        # recebe o tema. Sem isto, tudo o que sobrasse por baixo do conteúdo
        # ficava com o cinzento de origem do Tk — uma faixa de outra cor no
        # fundo do painel, tanto mais visível quanto mais espaço sobrasse.
        self._tela = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                               background=cores()["superficie"])
        self._barra = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                    command=self._tela.yview)
        self._tela.configure(yscrollcommand=self._ao_deslocar)

        self._tela.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._barra_visivel = False

        self.interior = ttk.Frame(self._tela)
        self._janela = self._tela.create_window(
            (0, 0), window=self.interior, anchor=tk.NW
        )

        self.interior.bind("<Configure>", self._pedir_sincronia)
        self._tela.bind("<Configure>", self._pedir_sincronia)
        self._sincronia_pedida = False

        # A roda só conta quando o ponteiro está por cima: `bind_all` numa
        # janela com dois painéis deslocáveis fazia os dois andarem ao mesmo
        # tempo.
        self._tela.bind("<Enter>", self._ligar_roda)
        self._tela.bind("<Leave>", self._desligar_roda)

        for tecla, passo in (("<Up>", -1), ("<Down>", 1)):
            self._tela.bind(tecla, lambda _e, p=passo: self._unidades(p))
        self._tela.bind("<Prior>", lambda _e: self._paginas(-1))
        self._tela.bind("<Next>", lambda _e: self._paginas(1))
        # Sem isto o Canvas não recebe foco e as teclas acima nunca chegam.
        self._tela.configure(takefocus=True)

    # ------------------------------------------------------------- tamanho

    def _pedir_sincronia(self, _evento=None) -> None:
        """Marca uma sincronização para o próximo momento livre.

        Agrupada de propósito: arrastar a janela produz dezenas de
        ``<Configure>`` por segundo, e refazer a região a cada um deles dá um
        redimensionamento aos solavancos.
        """
        if self._sincronia_pedida:
            return
        self._sincronia_pedida = True
        try:
            self.after_idle(self.sincronizar)
        except tk.TclError:  # pragma: no cover - já destruído
            self._sincronia_pedida = False

    def sincronizar(self) -> None:
        """Põe de acordo o tamanho do item, a região e a barra.

        **Uma medida só manda**: a altura que o conteúdo pede. A primeira
        versão tinha duas — ``reqheight`` decidia a barra e ``bbox`` decidia a
        região — e discordavam: ao apagar conteúdo, a barra desaparecia e a
        região continuava a dizer 3400 píxeis, deixando a vista parada a 5% de
        um painel que já cabia todo.

        **E arruma antes de medir.** Era daí que vinha a discórdia: apagar
        conteúdo não muda logo o que o interior pede -- ``winfo_reqheight``
        continua a responder 3400 até o gestor de geometria correr. Medido:
        logo a seguir a apagar, 3400; depois de ``update_idletasks``, 51.

        A **altura do item não se toca**: o Canvas ajusta-a ao que o widget
        pede, a crescer e a encolher. Fixá-la à mão tranca-a no primeiro valor
        — que é 1, antes de haver conteúdo — e a partir daí nada mais cresce.
        """
        self._sincronia_pedida = False
        try:
            # Deixa o gestor de geometria acabar o que tem para fazer. Sem
            # isto, quem apaga conteúdo e avisa a seguir é atendido com as
            # medidas de antes de apagar.
            self.update_idletasks()
            largura = self._tela.winfo_width()
            self._tela.itemconfigure(self._janela, width=largura)
            # Reler **depois** de mexer na largura. Mudá-la volta a arrumar o
            # interior e pode mudar-lhe a altura -- é um texto que passa a
            # caber numa linha em vez de duas. Ler antes dava a altura da
            # arrumação anterior, e a região ficava a dizer 3400 píxeis de um
            # painel que ja só tinha 51.
            altura = self.interior.winfo_reqheight()
            self._tela.configure(scrollregion=(0, 0, largura, altura))
        except tk.TclError:  # pragma: no cover - já destruído
            return
        self._decidir_a_barra(altura)
        self._confirmar(altura)

    def _confirmar(self, altura: int) -> None:
        """Volta a passar se o tamanho mudou por causa desta própria passagem.

        Converge em vez de assumir: mexer na largura pode mudar a altura, e
        essa segunda mudança chega por um ``<Configure>`` que pode ou não
        vir a tempo. Uma passagem a mais custa nada; uma barra a dizer o
        contrário do que está no ecrã custa a confiança toda.
        """
        try:
            if self.interior.winfo_reqheight() != altura:
                self._pedir_sincronia()
        except tk.TclError:  # pragma: no cover - já destruído
            pass

    def altura_do_conteudo(self) -> int:
        """A altura que o conteúdo pede — a medida que manda em tudo isto."""
        try:
            return int(self.interior.winfo_reqheight())
        except tk.TclError:  # pragma: no cover - já destruído
            return 0

    def precisa_de_barra(self) -> bool:
        """Se o conteúdo é mais alto do que o espaço que há para o mostrar."""
        try:
            return self.altura_do_conteudo() > self._tela.winfo_height()
        except tk.TclError:  # pragma: no cover - já destruído
            return False

    def _decidir_a_barra(self, altura: int) -> None:
        try:
            precisa = altura > self._tela.winfo_height()
        except tk.TclError:  # pragma: no cover - já destruído
            return
        if precisa == self._barra_visivel:
            return
        self._barra_visivel = precisa
        if precisa:
            self._barra.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self._barra.pack_forget()
            # Volta ao topo: deixar a vista a meio de um conteúdo que agora
            # cabe todo mostrava uma faixa em branco por baixo dele.
            self._tela.yview_moveto(0)

    def _ao_deslocar(self, inicio: str, fim: str) -> None:
        self._barra.set(inicio, fim)

    # -------------------------------------------------------- deslocamento

    def _unidades(self, quantas: int) -> str:
        if self._barra_visivel:
            self._tela.yview_scroll(quantas, "units")
        return "break"

    def _paginas(self, quantas: int) -> str:
        if self._barra_visivel:
            self._tela.yview_scroll(quantas, "pages")
        return "break"

    def _ligar_roda(self, _evento=None) -> None:
        self._tela.bind_all("<MouseWheel>", self._ao_rodar)
        # X11 manda a roda como botões 4 e 5 em vez de <MouseWheel>.
        self._tela.bind_all("<Button-4>", lambda _e: self._unidades(-LINHAS_POR_ESTALO))
        self._tela.bind_all("<Button-5>", lambda _e: self._unidades(LINHAS_POR_ESTALO))

    def _desligar_roda(self, _evento=None) -> None:
        for sequencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                self._tela.unbind_all(sequencia)
            except tk.TclError:  # pragma: no cover
                pass

    def _ao_rodar(self, evento) -> str:
        estalos = -int(evento.delta / 120) if evento.delta else 0
        return self._unidades(estalos * LINHAS_POR_ESTALO)
