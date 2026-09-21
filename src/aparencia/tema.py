"""Aplica a paleta ao ttk, uma vez, na janela de raiz.

O ttk trabalha por **classes de estilo**: configurar ``TButton`` aqui muda
todos os botões da aplicação — e também os dos plugins, sem que nenhum deles
saiba que isto existe. É o que torna a aparência uma decisão de um sítio só,
em vez de um trabalho repetido em doze ficheiros.

O tema base é o ``clam``, e não por gosto: é o único dos que vêm com o Tk que
respeita cores e contornos em todos os elementos. O ``vista`` do Windows
desenha os controlos com imagens do sistema operativo e ignora quase tudo o
que se lhe pede — é adequado quando se quer parecer o Windows de 2007, e
intocável quando não se quer.

Três decisões explicam a diferença de aspeto:

* **Relevo nenhum.** O ar de aplicação antiga vem dos biséis: o ``sunken`` das
  caixas de texto, o ``raised`` dos botões. Tudo plano, e a separação feita
  por uma linha de 1px.
* **Ar.** Preenchimentos vindos da escala, e linhas de tabela a 30px em vez
  dos 20 de origem.
* **Uma cor de ênfase, usada pouco.** O azul aparece no que está selecionado,
  no foco e no botão principal de cada ecrã. Quando tudo é colorido, nada se
  destaca.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Dict, Optional

from aparencia import paleta
from core.log import obter_logger

logger = obter_logger(__name__)

_modo: str = "claro"
_familia: Optional[str] = None

#: Onde a escolha de modo fica guardada, entre arranques.
CHAVE_CONFIG = "aparencia_modo"


def modo() -> str:
    """O modo em vigor."""
    return _modo


def modo_guardado() -> str:
    """O modo escolhido da última vez, ou o claro se ninguém escolheu.

    Um valor inválido no ficheiro de configuração — editado à mão, ou vindo de
    uma versão futura — cai no claro em vez de impedir a aplicação de abrir.
    Uma preferência de aspeto nunca pode ser motivo para não arrancar.
    """
    from core import config

    escolhido = str(config.obter(CHAVE_CONFIG, "claro"))
    if escolhido not in paleta.MODOS:
        logger.warning("Modo de aparência desconhecido em config: %r.", escolhido)
        return "claro"
    return escolhido


def guardar_modo(novo_modo: str) -> None:
    """Guarda a escolha de modo.

    Raises:
        ValueError: modo desconhecido.
    """
    from core import config

    paleta.cores(novo_modo)  # valida
    try:
        config.definir(CHAVE_CONFIG, novo_modo)
    except OSError:  # pragma: no cover - disco cheio ou sem permissões
        logger.warning("Não foi possível guardar o modo de aparência.")


def cores() -> Dict[str, str]:
    """As cores do modo em vigor."""
    return paleta.cores(_modo)


def series() -> tuple:
    """As cores das séries dos gráficos, no modo em vigor."""
    return paleta.series(_modo)


def familia(raiz: Optional[tk.Misc] = None) -> str:
    """A primeira família de letra da lista que esteja instalada.

    Sem raiz — ou sem ecrã — devolve a primeira da lista. Não é para mostrar:
    é para os testes poderem perguntar sem abrir uma janela.
    """
    global _familia
    if _familia is not None:
        return _familia
    if raiz is None:
        return paleta.FAMILIAS[0]
    try:
        instaladas = {nome.lower() for nome in tkfont.families(raiz)}
    except tk.TclError:  # pragma: no cover - sem ecrã
        return paleta.FAMILIAS[0]
    for nome in paleta.FAMILIAS:
        if nome.lower() in instaladas:
            _familia = nome
            return nome
    # Nenhuma instalada: a do sistema serve, e é melhor do que impor uma que o
    # Tk vai substituir por outra qualquer sem dizer qual.
    _familia = tkfont.nametofont("TkDefaultFont").actual("family")
    return _familia


#: Pixeis por ponto a 96 DPI, que é o que o Windows chama 100%.
#:
#: O ``tk scaling`` não é uma percentagem: é esta razão multiplicada pela
#: escala do sistema. Confundir as duas dá 133% onde se queria 100%.
ESCALA_BASE = 96 / 72


def escala(raiz: Optional[tk.Misc] = None) -> float:
    """Quantas vezes maior está tudo por causa do DPI. ``1.0`` é 100%.

    É a resposta à pergunta "quantos pixeis vale um ponto aqui" — a mesma
    que decide o tamanho da letra. Quem trabalha em pixeis (um tamanho
    mínimo de janela, uma largura de coluna) tem de a multiplicar, senão
    fixa uma medida física que encolhe à medida que os ecrãs melhoram.

    Sem raiz — ou sem ecrã — devolve ``1.0``, como :func:`familia` devolve a
    primeira da lista: é o que permite a quem pergunta fora da interface
    receber um número em vez de uma exceção.
    """
    if raiz is None:
        return 1.0
    try:
        return float(raiz.tk.call("tk", "scaling")) / ESCALA_BASE
    except (tk.TclError, ValueError, AttributeError):  # pragma: no cover
        return 1.0


def em_pixeis(valor: int, raiz: Optional[tk.Misc] = None) -> int:
    """Um tamanho pensado a 100%, convertido para a escala em vigor."""
    return int(round(valor * escala(raiz)))


def cabe_no_ecra(largura: int, altura: int, raiz: tk.Misc) -> tuple:
    """O par pedido, encolhido até caber no ecrã desta janela.

    Um mínimo que não cabe no ecrã é pior do que um mínimo errado: a janela
    deixa de se poder encolher até ao que existe, e a pessoa fica com partes
    de fora sem nada que possa fazer. Escalar um mínimo com o DPI sem esta
    trava dá exatamente isso — 940×620 a 150% pede 1410×930, e um portátil
    de 1366×768 não tem lá isso.

    Deixa uma margem para a barra de tarefas e para a moldura da janela, que
    o Tk não desconta de ``winfo_screenheight``.
    """
    try:
        do_ecra = (raiz.winfo_screenwidth(), raiz.winfo_screenheight())
    except tk.TclError:  # pragma: no cover - sem ecrã
        return largura, altura
    margem = em_pixeis(MARGEM_DO_SISTEMA, raiz)
    return (min(largura, do_ecra[0]), min(altura, do_ecra[1] - margem))


#: Quanto se desconta à altura do ecrã para a barra de tarefas e a moldura,
#: a 100%. Medido numa instalação normal do Windows 11: 48 da barra e uns
#: 32 da moldura e do título.
MARGEM_DO_SISTEMA = 80


def fonte(tamanho: str = "corpo", negrito: bool = False, raiz: Optional[tk.Misc] = None) -> tuple:
    """Uma fonte da escala: ``fonte("titulo", negrito=True)``.

    Raises:
        ValueError: um tamanho fora da escala. É de propósito — a escala
            fechada é o que faz os ecrãs parecerem o mesmo produto, e aceitar
            um número solto em silêncio era abrir a porta outra vez.
    """
    if tamanho not in paleta.TAMANHO:
        raise ValueError(
            f"Tamanho {tamanho!r} fora da escala. Use um de: "
            f"{', '.join(sorted(paleta.TAMANHO))}."
        )
    pontos = paleta.TAMANHO[tamanho]
    return (familia(raiz), pontos, "bold") if negrito else (familia(raiz), pontos)


def _superficies(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int], destaque: tuple) -> None:
    estilo.configure("TFrame", background=c["superficie"])
    estilo.configure("Alta.TFrame", background=c["superficie_alta"])
    estilo.configure(
        "Cartao.TFrame",
        background=c["superficie_alta"],
        borderwidth=1,
        relief="solid",
        bordercolor=c["contorno_subtil"],
    )
    estilo.configure(
        "TLabelframe",
        background=c["superficie"],
        borderwidth=1,
        relief="solid",
        bordercolor=c["contorno_subtil"],
        padding=e["confortavel"],
    )
    estilo.configure(
        "TLabelframe.Label",
        background=c["superficie"],
        foreground=c["texto_suave"],
        font=destaque,
    )
    estilo.configure("TSeparator", background=c["contorno_subtil"])
    estilo.configure("TPanedwindow", background=c["superficie"])


def _texto(estilo: ttk.Style, c: Dict[str, str], raiz: tk.Misc, pequeno: tuple, destaque: tuple) -> None:
    estilo.configure("TLabel", background=c["superficie"], foreground=c["texto"])
    estilo.configure("Suave.TLabel", foreground=c["texto_suave"], font=pequeno)
    estilo.configure("Tenue.TLabel", foreground=c["texto_tenue"], font=pequeno)
    estilo.configure("Destaque.TLabel", font=destaque)
    estilo.configure("Subtitulo.TLabel", font=fonte("subtitulo", negrito=True, raiz=raiz))
    estilo.configure("Titulo.TLabel", font=fonte("titulo", negrito=True, raiz=raiz))
    estilo.configure("Display.TLabel", font=fonte("display", negrito=True, raiz=raiz))
    estilo.configure("Bom.TLabel", foreground=c["bom"])
    estilo.configure("Aviso.TLabel", foreground=c["aviso"])
    estilo.configure("Mau.TLabel", foreground=c["mau"])
    for nome in ("Suave", "Tenue", "Destaque", "Subtitulo", "Titulo", "Display",
                 "Bom", "Aviso", "Mau"):
        estilo.configure(f"{nome}.TLabel", background=c["superficie"])


def _botoes(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int]) -> None:
    estilo.configure(
        "TButton",
        background=c["superficie_alta"],
        foreground=c["texto"],
        bordercolor=c["contorno_controlo"],
        borderwidth=1,
        relief="solid",
        padding=(e["confortavel"], e["apertado"] + 2),
        anchor="center",
    )
    estilo.map(
        "TButton",
        background=[("pressed", c["superficie_baixa"]), ("active", c["superficie_baixa"]),
                    ("disabled", c["superficie_alta"])],
        foreground=[("disabled", c["texto_tenue"])],
        bordercolor=[("focus", c["foco"]), ("active", c["contorno_controlo"])],
    )
    # O botão principal de cada ecrã, e só esse: se tudo for azul, nada é.
    estilo.configure(
        "Destaque.TButton",
        background=c["acento"],
        foreground=c["sobre_acento"],
        bordercolor=c["acento"],
    )
    estilo.map(
        "Destaque.TButton",
        background=[("pressed", c["acento_forte"]), ("active", c["acento_forte"]),
                    ("disabled", c["superficie_baixa"])],
        foreground=[("disabled", c["texto_tenue"])],
        bordercolor=[("pressed", c["acento_forte"]), ("active", c["acento_forte"]),
                     ("disabled", c["contorno"])],
    )


def _lateral(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int], corpo: tuple) -> None:
    """Os itens da barra lateral.

    São botões, e não etiquetas com um clique agarrado: um botão já traz o
    foco por teclado, o Espaço e o Enter, e o estado desativado. Refazer isso
    à mão dá quase sempre uma coisa que o rato usa e o teclado não.

    Sem contorno e sem fundo até o rato lá passar: uma lista de doze caixas
    pesa mais do que a página que elas abrem.
    """
    estilo.configure(
        "Lateral.TButton",
        background=c["superficie_alta"],
        foreground=c["texto_suave"],
        bordercolor=c["superficie_alta"],
        borderwidth=0,
        relief="flat",
        anchor="w",
        padding=(e["confortavel"], e["normal"] - 1),
        font=corpo,
    )
    estilo.map(
        "Lateral.TButton",
        background=[("active", c["superficie_baixa"]), ("pressed", c["superficie_baixa"])],
        foreground=[("active", c["texto"])],
        bordercolor=[("focus", c["foco"])],
    )
    # O que está aberto: fundo com a tinta do acento, texto com o acento.
    # Nem tudo colorido, nem indistinguível do resto.
    estilo.configure(
        "LateralAtivo.TButton",
        background=c["acento_suave"],
        foreground=c["acento"],
        bordercolor=c["acento_suave"],
        borderwidth=0,
        relief="flat",
        anchor="w",
        padding=(e["confortavel"], e["normal"] - 1),
        font=corpo,
    )
    estilo.map(
        "LateralAtivo.TButton",
        background=[("active", c["acento_suave"]), ("pressed", c["acento_suave"])],
        foreground=[("active", c["acento"])],
        bordercolor=[("focus", c["foco"])],
    )


def _entradas(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int]) -> None:
    for classe in ("TEntry", "TCombobox", "TSpinbox"):
        estilo.configure(
            classe,
            fieldbackground=c["superficie"],
            background=c["superficie"],
            foreground=c["texto"],
            bordercolor=c["contorno_controlo"],
            borderwidth=1,
            relief="solid",
            padding=e["apertado"] + 1,
            arrowcolor=c["texto_suave"],
            insertcolor=c["texto"],
            selectbackground=c["acento_suave"],
            selectforeground=c["texto"],
        )
        estilo.map(
            classe,
            bordercolor=[("focus", c["foco"]), ("disabled", c["contorno"])],
            foreground=[("disabled", c["texto_tenue"])],
            fieldbackground=[("disabled", c["superficie_alta"]),
                             ("readonly", c["superficie_alta"])],
        )


def _tabelas(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int], pequeno: tuple) -> None:
    estilo.configure(
        "Treeview",
        background=c["superficie"],
        fieldbackground=c["superficie"],
        foreground=c["texto"],
        rowheight=paleta.ALTURA_LINHA,
        borderwidth=0,
        relief="flat",
    )
    estilo.map(
        "Treeview",
        background=[("selected", c["acento_suave"])],
        foreground=[("selected", c["texto"])],
    )
    estilo.configure(
        "Treeview.Heading",
        background=c["superficie_alta"],
        foreground=c["texto_suave"],
        font=pequeno,
        borderwidth=0,
        relief="flat",
        padding=(e["normal"], e["apertado"] + 2),
    )
    estilo.map("Treeview.Heading", background=[("active", c["superficie_baixa"])])


def _abas(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int], corpo: tuple, destaque: tuple) -> None:
    estilo.configure("TNotebook", background=c["superficie"], borderwidth=0,
                     tabmargins=(0, 0, 0, 0))
    estilo.configure(
        "TNotebook.Tab",
        background=c["superficie"],
        foreground=c["texto_suave"],
        padding=(e["largo"], e["normal"]),
        borderwidth=0,
        # Sem isto, o clam desenha um contorno à volta de cada aba e a que
        # não está selecionada fica a parecer uma caixa pousada em cima da
        # página, em vez de um separador.
        bordercolor=c["superficie"],
        lightcolor=c["superficie"],
        darkcolor=c["superficie"],
        font=corpo,
    )
    estilo.map(
        "TNotebook.Tab",
        background=[("selected", c["superficie"]), ("active", c["superficie_alta"])],
        foreground=[("selected", c["acento"]), ("active", c["texto"])],
        font=[("selected", destaque)],
    )


def _controlos(estilo: ttk.Style, c: Dict[str, str], e: Dict[str, int]) -> None:
    estilo.configure(
        "TCheckbutton",
        background=c["superficie"],
        foreground=c["texto"],
        indicatorcolor=c["superficie"],
        indicatorbackground=c["superficie"],
        bordercolor=c["contorno_controlo"],
        focuscolor=c["foco"],
        padding=(e["apertado"], e["minimo"]),
    )
    estilo.map(
        "TCheckbutton",
        indicatorcolor=[("selected", c["acento"]), ("disabled", c["superficie_alta"])],
        foreground=[("disabled", c["texto_tenue"])],
    )
    estilo.configure(
        "TRadiobutton",
        background=c["superficie"],
        foreground=c["texto"],
        indicatorcolor=c["superficie"],
        bordercolor=c["contorno_controlo"],
        focuscolor=c["foco"],
        padding=(e["apertado"], e["minimo"]),
    )
    estilo.map("TRadiobutton", indicatorcolor=[("selected", c["acento"])])
    estilo.configure(
        "TProgressbar",
        background=c["acento"],
        troughcolor=c["superficie_baixa"],
        bordercolor=c["superficie_baixa"],
        lightcolor=c["acento"],
        darkcolor=c["acento"],
        thickness=6,
    )
    for classe in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        estilo.configure(
            classe,
            background=c["superficie_baixa"],
            troughcolor=c["superficie"],
            bordercolor=c["superficie"],
            arrowcolor=c["texto_suave"],
            borderwidth=0,
            relief="flat",
        )
        estilo.map(classe, background=[("active", c["contorno"])])


def _fontes_do_sistema(raiz: tk.Misc, corpo: tuple) -> None:
    """Alinha as fontes nomeadas do Tk com a escala.

    Os widgets clássicos — ``tk.Listbox``, ``tk.Text``, os menus, as caixas de
    diálogo — não passam pelo ttk e ficariam com a letra de origem. Sem isto,
    metade da aplicação mudava de aspeto e a outra metade não, que se nota
    mais do que não mudar nenhuma.
    """
    for nome in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkIconFont"):
        try:
            tkfont.nametofont(nome, root=raiz).configure(family=corpo[0], size=corpo[1])
        except tk.TclError:  # pragma: no cover - fonte nomeada ausente
            logger.debug("Fonte %s não existe nesta instalação do Tk.", nome)


def aplicar(raiz: tk.Misc, novo_modo: str = "claro") -> ttk.Style:
    """Põe a paleta a valer em toda a aplicação.

    Chamada uma vez, com a janela de raiz, antes de se construir o que quer
    que seja. Chamá-la outra vez com outro modo muda a aplicação inteira.

    Raises:
        ValueError: modo desconhecido. Validado **antes** de se tocar em
            qualquer estilo: meio tema aplicado é pior do que nenhum.
    """
    global _modo
    c = paleta.cores(novo_modo)
    _modo = novo_modo

    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:  # pragma: no cover - instalação de Tk invulgar
        logger.warning("Tema 'clam' indisponível; a aparência fica a do sistema.")

    corpo = fonte("corpo", raiz=raiz)
    pequeno = fonte("pequeno", raiz=raiz)
    destaque = fonte("destaque", negrito=True, raiz=raiz)
    e = paleta.ESPACO

    _fontes_do_sistema(raiz, corpo)
    try:
        raiz.configure(background=c["superficie"])
    except tk.TclError:  # pragma: no cover - widget sem background
        pass

    estilo.configure(
        ".",
        background=c["superficie"],
        foreground=c["texto"],
        fieldbackground=c["superficie"],
        bordercolor=c["contorno"],
        lightcolor=c["superficie"],
        darkcolor=c["superficie"],
        troughcolor=c["superficie_baixa"],
        focuscolor=c["foco"],
        font=corpo,
        borderwidth=0,
        relief="flat",
    )

    _superficies(estilo, c, e, destaque)
    _texto(estilo, c, raiz, pequeno, destaque)
    _botoes(estilo, c, e)
    _lateral(estilo, c, e, corpo)
    _entradas(estilo, c, e)
    _tabelas(estilo, c, e, pequeno)
    _abas(estilo, c, e, corpo, destaque)
    _controlos(estilo, c, e)

    logger.info("Aparência aplicada: modo %s, letra %s.", novo_modo, familia(raiz))
    return estilo
