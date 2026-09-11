"""Gera ``assets/icon.ico`` — o ícone da aplicação e do instalador.

O ``.ico`` está versionado no repositório; este script só é preciso para o
regenerar. Requer Pillow (``pip install pillow``), que **não** é dependência
da aplicação nem do empacotamento::

    python tools/gerar_icone.py

Desenho: uma prancheta com três linhas, a primeira com um visto — legível
mesmo a 16x16, que é o tamanho da barra de tarefas.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "assets" / "icon.ico"

#: Tamanhos que o Windows usa (barra de tarefas, explorador, atalhos, lojas).
TAMANHOS = [16, 24, 32, 48, 64, 128, 256]

FUNDO = (37, 99, 156, 255)      # azul
PAPEL = (250, 250, 250, 255)    # branco
CLIPE = (150, 160, 170, 255)    # cinzento
LINHA = (120, 132, 145, 255)
VISTO = (34, 150, 83, 255)      # verde


def desenhar(lado: int):
    """Desenha o ícone num tamanho de referência grande e devolve a imagem."""
    from PIL import Image, ImageDraw

    imagem = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    u = lado / 16  # unidade de grelha

    # Fundo arredondado.
    desenho.rounded_rectangle(
        [0, 0, lado - 1, lado - 1], radius=int(3 * u), fill=FUNDO
    )

    # Prancheta.
    desenho.rounded_rectangle(
        [3 * u, 3 * u, 13 * u, 14 * u], radius=int(0.8 * u), fill=PAPEL
    )
    # Clipe no topo.
    desenho.rounded_rectangle(
        [6 * u, 1.8 * u, 10 * u, 4 * u], radius=int(0.6 * u), fill=CLIPE
    )

    espessura = max(1, int(0.7 * u))
    # Linhas de texto.
    for indice, y in enumerate((7.2, 9.6, 12.0)):
        fim = 11 * u if indice else 10.4 * u
        desenho.line([5.2 * u, y * u, fim, y * u], fill=LINHA, width=espessura)

    # Visto sobre a primeira linha.
    desenho.line(
        [4.6 * u, 7.1 * u, 5.6 * u, 8.1 * u], fill=VISTO, width=max(1, int(0.9 * u))
    )
    desenho.line(
        [5.6 * u, 8.1 * u, 7.6 * u, 5.6 * u], fill=VISTO, width=max(1, int(0.9 * u))
    )
    return imagem


def gerar(destino: Path = DESTINO) -> Path:
    """Cria o ``.ico`` com todos os tamanhos e devolve o caminho."""
    from PIL import Image

    base = desenhar(256)
    imagens = [
        base if lado == 256 else base.resize((lado, lado), Image.LANCZOS)
        for lado in TAMANHOS
    ]
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagens[-1].save(destino, format="ICO", sizes=[(lado, lado) for lado in TAMANHOS])
    return destino


def main() -> int:
    """Ponto de entrada da linha de comandos."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("É preciso Pillow para gerar o ícone: pip install pillow", file=sys.stderr)
        return 1

    caminho = gerar()
    print(f"Ícone gerado: {caminho} ({caminho.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
