"""As cores, os espaços e os tamanhos de letra — um sítio só.

Antes disto, doze ficheiros de interface escolhiam as suas cores à mão e
onze valores em hexadecimal andavam copiados entre eles. O resultado
previsível: o mesmo "cinzento de texto secundário" com dois valores
diferentes consoante o ecrã, e ninguém a reparar.

Um token não é uma cor: é um **papel**. ``texto_suave`` continua a chamar-se
assim no modo escuro, onde é mais claro do que o fundo. Quem usa pede o papel
e não o valor, e é por isso que o modo escuro custa um dicionário em vez de
uma passagem por toda a base de código.

Os valores não foram escolhidos a olho. ``tests/test_aparencia.py`` mede o
contraste de cada par que aparece mesmo no ecrã contra os limiares da
WCAG 2.1 — nos dois modos.
"""

from __future__ import annotations

from typing import Dict

#: Escala de espaçamento, em píxeis, sobre uma grelha de 4.
#:
#: Uma escala fechada é o que faz vários ecrãs parecerem o mesmo produto.
#: Com números livres, cada ecrã acaba com o seu próprio ritmo — 5 aqui, 7
#: ali — e a diferença nota-se sem se conseguir dizer porquê.
ESPACO: Dict[str, int] = {
    "minimo": 2,
    "apertado": 4,
    "normal": 8,
    "confortavel": 12,
    "largo": 16,
    "seccao": 24,
    "pagina": 32,
}

#: Tamanhos de letra, em pontos.
TAMANHO: Dict[str, int] = {
    "micro": 8,
    "pequeno": 9,
    "corpo": 10,
    "destaque": 11,
    "subtitulo": 13,
    "titulo": 17,
    "display": 24,
}

#: Famílias tentadas por ordem; a primeira instalada ganha.
#:
#: A letra do sistema é a escolha certa num programa de secretária: é a que a
#: pessoa já lê o dia inteiro, é a que tem as métricas afinadas para o ecrã
#: dela, e não obriga a embutir um ficheiro de tipo de letra no instalador.
FAMILIAS = (
    "Segoe UI Variable Text",
    "Segoe UI",
    "SF Pro Text",
    "Inter",
    "Noto Sans",
    "DejaVu Sans",
    "Helvetica",
)

#: Altura de uma linha de tabela. O ttk usa 20 por omissão, que é o aperto de
#: uma folha de cálculo; uma lista de trabalho lê-se melhor com ar.
ALTURA_LINHA = 30

#: Dois papéis que não se devem juntar, e que eu tinha juntado:
#:
#: * ``contorno`` e ``contorno_subtil`` **separam** — a linha de um cartão, a
#:   régua entre secções. São decoração, e a norma não lhes exige contraste;
#:   dar-lho transformava cada divisória num traço preto a gritar.
#: * ``contorno_controlo`` **identifica** — é a borda que diz "isto é uma
#:   caixa onde se escreve". Quando é a única pista de que ali há um campo,
#:   a WCAG 1.4.11 exige 3:1, e o teste verifica-o.
#:
#: A medição obrigou a separá-los: com um token só, ou os campos ficavam por
#: identificar ou as divisórias ficavam a berrar.
CLARO: Dict[str, str] = {
    "superficie": "#FFFFFF",
    "superficie_alta": "#F4F6F9",
    "superficie_baixa": "#E9EDF2",
    "contorno": "#CBD3DC",
    "contorno_subtil": "#E4E9EF",
    "contorno_controlo": "#78838F",
    "texto": "#141A21",
    "texto_suave": "#4F5B69",
    "texto_tenue": "#6B7684",
    "acento": "#1F5FD0",
    "acento_forte": "#17499F",
    "acento_suave": "#E7EEFB",
    "sobre_acento": "#FFFFFF",
    "bom": "#12684A",
    "aviso": "#7A5200",
    "mau": "#B3241C",
    "foco": "#1F5FD0",
}

ESCURO: Dict[str, str] = {
    "superficie": "#14181D",
    "superficie_alta": "#1B2026",
    "superficie_baixa": "#252B33",
    "contorno": "#3A424C",
    "contorno_subtil": "#272E36",
    "contorno_controlo": "#6E7885",
    "texto": "#E9ECF0",
    "texto_suave": "#B3BCC7",
    "texto_tenue": "#98A3B0",
    "acento": "#7BA7FF",
    "acento_forte": "#A0C1FF",
    "acento_suave": "#1E2A3C",
    "sobre_acento": "#0E1319",
    "bom": "#5CC98F",
    "aviso": "#E3AC4A",
    "mau": "#FF8A80",
    "foco": "#7BA7FF",
}

MODOS: Dict[str, Dict[str, str]] = {"claro": CLARO, "escuro": ESCURO}

#: Cores das séries dos gráficos, por ordem de uso.
#:
#: Distintas entre si **e** legíveis sobre a superfície dos dois modos. Um
#: gráfico que usa a paleta da interface acaba com duas séries quase iguais.
SERIES_CLARO = ("#1F5FD0", "#12684A", "#9A4E00", "#7A3EA1", "#0E6E78", "#A3323A")
SERIES_ESCURO = ("#7BA7FF", "#5CC98F", "#E3AC4A", "#C79BEA", "#5FD0DC", "#FF8A80")


def cores(modo: str) -> Dict[str, str]:
    """As cores de um modo.

    Raises:
        ValueError: um modo desconhecido é um erro de escrita, e devolver o
            claro em silêncio deixava o modo escuro meio aplicado.
    """
    try:
        return dict(MODOS[modo])
    except KeyError:
        raise ValueError(f"Modo de aparência desconhecido: {modo!r}") from None


def series(modo: str) -> tuple:
    """As cores das séries dos gráficos, para este modo."""
    return SERIES_ESCURO if modo == "escuro" else SERIES_CLARO
