"""Gráficos desenhados diretamente no ``tkinter.Canvas``.

Sem matplotlib (ver ADR-0002): cada gráfico é ~100 linhas, redesenha-se ao
mudar de tamanho e usa as cores do tema do sistema, integrando-se na janela em
vez de parecer uma figura colada por cima.

Componentes:

* :class:`CartaoKPI` — um número grande com rótulo e variação;
* :class:`GraficoLinhas` — séries temporais, com previsão a tracejado;
* :class:`GraficoBarras` — comparação entre categorias.

Todos aceitam ``dados`` vazios e mostram uma mensagem em vez de um eixo vazio.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Callable, List, Optional, Sequence, Tuple

# Paleta: distinguível, legível sobre fundos claros, sem depender de tema.
COR_PRIMARIA = "#25639c"
COR_SECUNDARIA = "#2f9e5f"
COR_ALERTA = "#c0392b"
COR_ATENCAO = "#d38b1a"
COR_NEUTRA = "#7a8794"
COR_GRELHA = "#dfe4e8"
COR_TEXTO = "#33404d"

PALETA = (COR_PRIMARIA, COR_SECUNDARIA, COR_ATENCAO, COR_ALERTA, COR_NEUTRA)


def _fundo_do_tema(widget: tk.Misc) -> str:
    """Cor de fundo do tema atual, para o canvas não destoar."""
    try:
        cor = ttk.Style(widget).lookup("TFrame", "background")
        return cor or "#ffffff"
    except tk.TclError:  # pragma: no cover - temas exóticos
        return "#ffffff"


@dataclass
class Serie:
    """Uma linha do gráfico."""

    nome: str
    pontos: Sequence
    """Sequência de ``(x, y)`` ou de objetos com ``.dia`` e ``.valor``."""

    cor: str = COR_PRIMARIA
    tracejado: bool = False
    """Usado para previsões: o que ainda não aconteceu não é linha cheia."""

    def valores(self) -> List[Tuple]:
        """Normaliza os pontos para ``(x, y)``."""
        normalizados = []
        for ponto in self.pontos:
            if hasattr(ponto, "dia") and hasattr(ponto, "valor"):
                normalizados.append((ponto.dia, float(ponto.valor)))
            else:
                x, y = ponto
                normalizados.append((x, float(y)))
        return normalizados


class _GraficoBase(ttk.Frame):
    """Tratamento comum: redesenhar ao redimensionar, margens, mensagem vazia."""

    MARGEM_ESQUERDA = 44
    MARGEM_DIREITA = 12
    MARGEM_TOPO = 26
    MARGEM_BASE = 30
    ALTURA_MINIMA = 140

    def __init__(
        self,
        master: tk.Misc,
        titulo: str = "",
        altura: int = 200,
        texto_sem_dados: str = "",
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._titulo = titulo
        self._texto_sem_dados = texto_sem_dados
        self.canvas = tk.Canvas(
            self,
            height=max(altura, self.ALTURA_MINIMA),
            highlightthickness=0,
            background=_fundo_do_tema(self),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _: self.redesenhar())

    # -------------------------------------------------------------- API

    def definir_titulo(self, titulo: str) -> None:
        """Muda o título e redesenha (usado na troca de idioma)."""
        self._titulo = titulo
        self.redesenhar()

    def definir_texto_sem_dados(self, texto: str) -> None:
        """Mensagem mostrada quando não há o que desenhar."""
        self._texto_sem_dados = texto
        self.redesenhar()

    def redesenhar(self) -> None:
        """Reconstrói o desenho a partir dos dados atuais."""
        self.canvas.delete("all")
        largura = self.canvas.winfo_width()
        altura = self.canvas.winfo_height()
        if largura <= 1 or altura <= 1:  # ainda não tem tamanho real
            return

        if self._titulo:
            self.canvas.create_text(
                self.MARGEM_ESQUERDA,
                12,
                text=self._titulo,
                anchor=tk.W,
                fill=COR_TEXTO,
                font=("Arial", 10, "bold"),
            )

        if self._sem_dados():
            self.canvas.create_text(
                largura / 2,
                altura / 2,
                text=self._texto_sem_dados,
                fill=COR_NEUTRA,
                font=("Arial", 10),
            )
            return

        self._desenhar(largura, altura)

    # ---------------------------------------------------------- ganchos

    def _sem_dados(self) -> bool:  # pragma: no cover - sobreposto
        return True

    def _desenhar(self, largura: int, altura: int) -> None:  # pragma: no cover
        raise NotImplementedError

    # ---------------------------------------------------------- auxílio

    def _area(self, largura: int, altura: int) -> Tuple[int, int, int, int]:
        return (
            self.MARGEM_ESQUERDA,
            self.MARGEM_TOPO,
            max(largura - self.MARGEM_DIREITA, self.MARGEM_ESQUERDA + 1),
            max(altura - self.MARGEM_BASE, self.MARGEM_TOPO + 1),
        )

    def _eixos(self, x0: int, y0: int, x1: int, y1: int, maximo: float) -> None:
        """Grelha horizontal com rótulos e linha de base."""
        divisoes = 4
        for indice in range(divisoes + 1):
            fracao = indice / divisoes
            y = y1 - (y1 - y0) * fracao
            self.canvas.create_line(x0, y, x1, y, fill=COR_GRELHA)
            self.canvas.create_text(
                x0 - 6,
                y,
                text=self._formatar_numero(maximo * fracao),
                anchor=tk.E,
                fill=COR_NEUTRA,
                font=("Arial", 8),
            )
        self.canvas.create_line(x0, y0, x0, y1, fill=COR_GRELHA)

    @staticmethod
    def _formatar_numero(valor: float) -> str:
        return str(int(valor)) if abs(valor - int(valor)) < 0.05 else f"{valor:.1f}"

    @staticmethod
    def _escala_agradavel(maximo: float, divisoes: int = 4) -> float:
        """Arredonda o topo do eixo para um valor legível.

        Sem isto, um máximo de 105 dá rótulos como 30.2, 60.4, 90.6 — números
        que ninguém lê.
        """
        if maximo <= 0:
            return 1.0
        import math

        passo_bruto = maximo / divisoes
        magnitude = 10 ** math.floor(math.log10(passo_bruto)) if passo_bruto > 0 else 1
        for multiplo in (1, 2, 2.5, 5, 10):
            passo = multiplo * magnitude
            if passo >= passo_bruto:
                return passo * divisoes
        return passo_bruto * divisoes  # pragma: no cover - defensivo


class GraficoLinhas(_GraficoBase):
    """Séries temporais sobrepostas, com legenda."""

    def __init__(self, master: tk.Misc, series: Optional[List[Serie]] = None, **kwargs) -> None:
        self._series: List[Serie] = list(series or [])
        super().__init__(master, **kwargs)

    def definir_series(self, series: Sequence[Serie]) -> None:
        """Substitui os dados e redesenha."""
        self._series = list(series)
        self.redesenhar()

    def _sem_dados(self) -> bool:
        """Sem pontos — ou com tudo a zero.

        Uma linha achatada no zero parece uma medição quando na verdade não
        houve nada para medir; a mensagem é mais honesta do que o desenho.
        """
        valores = [valor for serie in self._series for _, valor in serie.valores()]
        return not valores or all(valor == 0 for valor in valores)

    @staticmethod
    def _posicao_numerica(x) -> Optional[float]:
        """Converte o x para número, quando é uma data."""
        if hasattr(x, "toordinal"):
            return float(x.toordinal())
        if isinstance(x, (int, float)):
            return float(x)
        return None

    def _dominio_x(self) -> Optional[Tuple[float, float]]:
        """Intervalo numérico do eixo X, se todos os pontos forem posicionáveis.

        É isto que põe a previsão **depois** dos dados observados, em vez de a
        desenhar por cima do início da série.
        """
        posicoes = []
        for serie in self._series:
            for x, _ in serie.valores():
                posicao = self._posicao_numerica(x)
                if posicao is None:
                    return None
                posicoes.append(posicao)
        if not posicoes:
            return None
        minimo, maximo = min(posicoes), max(posicoes)
        return (minimo, maximo if maximo > minimo else minimo + 1)

    def _desenhar(self, largura: int, altura: int) -> None:
        x0, y0, x1, y1 = self._area(largura, altura)
        todos = [valor for serie in self._series for _, valor in serie.valores()]
        # Folga no topo para a linha não encostar ao título.
        maximo = self._escala_agradavel(max(max(todos), 1.0) * 1.1)

        self._eixos(x0, y0, x1, y1, maximo)

        dominio = self._dominio_x()
        comprimento = max(len(serie.valores()) for serie in self._series)
        passo = (x1 - x0) / max(comprimento - 1, 1)

        for serie in self._series:
            pontos = serie.valores()
            if len(pontos) < 2:
                continue
            coordenadas = []
            for indice, (x_bruto, valor) in enumerate(pontos):
                if dominio is not None:
                    inicio, fim = dominio
                    fracao = (self._posicao_numerica(x_bruto) - inicio) / (fim - inicio)
                    x = x0 + fracao * (x1 - x0)
                else:
                    x = x0 + indice * passo
                y = y1 - (valor / maximo) * (y1 - y0)
                coordenadas.extend([x, y])
            self.canvas.create_line(
                *coordenadas,
                fill=serie.cor,
                width=2,
                smooth=False,
                dash=(4, 3) if serie.tracejado else None,
            )

        self._rotulos_do_eixo_x(x0, x1, y1)
        self._legenda(x0, y1 + 16)

    def _rotulos_do_eixo_x(self, x0: int, x1: int, y1: int) -> None:
        """Primeiro e último rótulo — mais do que isso fica ilegível."""
        pontos = sorted(
            (x for serie in self._series for x, _ in serie.valores()),
            key=lambda x: self._posicao_numerica(x) or 0,
        )
        if not pontos:
            return
        for posicao, indice in ((x0, 0), (x1, -1)):
            etiqueta = self._formatar_x(pontos[indice])
            self.canvas.create_text(
                posicao,
                y1 + 8,
                text=etiqueta,
                anchor=tk.W if indice == 0 else tk.E,
                fill=COR_NEUTRA,
                font=("Arial", 8),
            )

    @staticmethod
    def _formatar_x(valor) -> str:
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m")
        return str(valor)

    def _legenda(self, x: int, y: int) -> None:
        deslocamento = x
        for serie in self._series:
            if not serie.nome:
                continue
            self.canvas.create_line(
                deslocamento,
                y,
                deslocamento + 14,
                y,
                fill=serie.cor,
                width=2,
                dash=(4, 3) if serie.tracejado else None,
            )
            texto = self.canvas.create_text(
                deslocamento + 19,
                y,
                text=serie.nome,
                anchor=tk.W,
                fill=COR_NEUTRA,
                font=("Arial", 8),
            )
            deslocamento = self.canvas.bbox(texto)[2] + 14


class GraficoBarras(_GraficoBase):
    """Comparação entre categorias, com o valor escrito em cada barra."""

    def __init__(
        self,
        master: tk.Misc,
        dados: Optional[Sequence[Tuple[str, float]]] = None,
        cores: Optional[Sequence[str]] = None,
        **kwargs,
    ) -> None:
        self._dados: List[Tuple[str, float]] = list(dados or [])
        self._cores = list(cores or PALETA)
        super().__init__(master, **kwargs)

    def definir_dados(
        self,
        dados: Sequence[Tuple[str, float]],
        cores: Optional[Sequence[str]] = None,
    ) -> None:
        """Substitui as categorias e redesenha."""
        self._dados = list(dados)
        if cores:
            self._cores = list(cores)
        self.redesenhar()

    def _sem_dados(self) -> bool:
        return not self._dados or all(valor == 0 for _, valor in self._dados)

    def _desenhar(self, largura: int, altura: int) -> None:
        x0, y0, x1, y1 = self._area(largura, altura)
        maximo = self._escala_agradavel(max(max(valor for _, valor in self._dados), 1.0) * 1.1)
        self._eixos(x0, y0, x1, y1, maximo)

        quantidade = len(self._dados)
        espaco = (x1 - x0) / quantidade
        largura_barra = min(espaco * 0.6, 70)

        for indice, (rotulo, valor) in enumerate(self._dados):
            centro = x0 + espaco * (indice + 0.5)
            topo = y1 - (valor / maximo) * (y1 - y0)
            cor = self._cores[indice % len(self._cores)]
            self.canvas.create_rectangle(
                centro - largura_barra / 2,
                topo,
                centro + largura_barra / 2,
                y1,
                fill=cor,
                outline="",
            )
            self.canvas.create_text(
                centro,
                topo - 8,
                text=self._formatar_numero(valor),
                fill=COR_TEXTO,
                font=("Arial", 9, "bold"),
            )
            self.canvas.create_text(
                centro,
                y1 + 10,
                text=rotulo,
                fill=COR_NEUTRA,
                font=("Arial", 8),
                width=espaco,
            )


class CartaoKPI(ttk.Frame):
    """Um indicador: número grande, rótulo e variação face ao período anterior."""

    def __init__(
        self,
        master: tk.Misc,
        rotulo: str = "",
        valor: str = "—",
        variacao: Optional[float] = None,
        cor: str = COR_PRIMARIA,
        subir_e_bom: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(master, relief=tk.GROOVE, borderwidth=1, padding=10, **kwargs)
        self._subir_e_bom = subir_e_bom

        self._rotulo = ttk.Label(self, text=rotulo, foreground=COR_NEUTRA, font=("Arial", 9))
        self._rotulo.pack(anchor=tk.W)
        self._valor = ttk.Label(self, text=valor, foreground=cor, font=("Arial", 20, "bold"))
        self._valor.pack(anchor=tk.W)
        self._variacao = ttk.Label(self, text="", font=("Arial", 8))
        self._variacao.pack(anchor=tk.W)

        self.atualizar(rotulo, valor, variacao)

    def atualizar(
        self,
        rotulo: Optional[str] = None,
        valor: Optional[str] = None,
        variacao: Optional[float] = None,
    ) -> None:
        """Atualiza o conteúdo do cartão.

        ``variacao`` a ``None`` esconde a linha: sem período de comparação não
        se inventa uma seta.
        """
        if rotulo is not None:
            self._rotulo.config(text=rotulo)
        if valor is not None:
            self._valor.config(text=valor)

        if variacao is None:
            self._variacao.config(text="")
            return

        seta = "▲" if variacao > 0 else ("▼" if variacao < 0 else "•")
        bom = (variacao > 0) == self._subir_e_bom
        cor = COR_NEUTRA if variacao == 0 else (COR_SECUNDARIA if bom else COR_ALERTA)
        self._variacao.config(text=f"{seta} {abs(variacao):.1f}%", foreground=cor)
