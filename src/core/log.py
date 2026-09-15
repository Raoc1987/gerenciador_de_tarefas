"""Configuração central de logging da aplicação.

Inclui a captura das exceções que ninguém apanhou. Sem ela, uma falha numa
ação da interface desaparece sem rasto: o Tk imprime o *traceback* no ``stderr``
e, numa aplicação empacotada em modo gráfico, não há ``stderr`` nenhum para o
receber. O utilizador vê um botão que não faz nada e o log não sabe porquê.
"""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from core.paths import diretorio_logs

_configurado = False
_excecoes_capturadas = False

#: Tamanho de cada arquivo de log e quantas gerações se guardam.
#:
#: São 10 MB no total. O valor anterior (512 KB × 3) cabia num dia normal, mas
#: uma sequência de erros — que é exatamente quando o log importa — enchia as
#: três gerações em minutos e apagava a causa antes de alguém a ler.
TAMANHO_MAXIMO_LOG = 2 * 1024 * 1024
COPIAS_DE_LOG = 5


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura o logger raiz (arquivo rotativo + console). Idempotente."""
    global _configurado
    logger = logging.getLogger()
    if _configurado:
        return logger

    logger.setLevel(nivel)
    formato = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        arquivo = RotatingFileHandler(
            diretorio_logs() / "app.log",
            maxBytes=TAMANHO_MAXIMO_LOG,
            backupCount=COPIAS_DE_LOG,
            encoding="utf-8",
        )
        arquivo.setFormatter(formato)
        logger.addHandler(arquivo)
    except OSError:
        # Sem permissão de escrita: a aplicação continua, apenas sem log em arquivo.
        pass

    if sys.stderr is not None:
        consola = logging.StreamHandler(sys.stderr)
        consola.setFormatter(formato)
        logger.addHandler(consola)

    _configurado = True
    return logger


def obter_logger(nome: str) -> logging.Logger:
    """Logger nomeado para um módulo ou plugin."""
    return logging.getLogger(nome)


def registar_excecao_nao_tratada(tipo, valor, tb, origem: str = "") -> None:
    """Escreve no log uma exceção que ninguém apanhou.

    É o ponto único por onde passam as três origens possíveis — o interpretador,
    uma *thread* e um *callback* do Tk — para que todas fiquem registadas da
    mesma maneira.

    ``KeyboardInterrupt`` não é falha: quem interrompe sabe o que fez.
    """
    if issubclass(tipo, KeyboardInterrupt):
        return
    onde = f" ({origem})" if origem else ""
    obter_logger("excecoes").critical(
        "Exceção não tratada%s", onde, exc_info=(tipo, valor, tb)
    )


def instalar_captura_de_excecoes() -> None:
    """Encaminha para o log as exceções do interpretador e das *threads*.

    O ``stderr`` continua a receber o *traceback* pelo handler de consola, por
    isso correr na consola não muda de comportamento. Idempotente.

    A parte do Tk fica de fora de propósito: o núcleo não importa a interface
    (ADR-0001). Quem abre a janela é que a instala, chamando
    :func:`registar_excecao_nao_tratada`.
    """
    global _excecoes_capturadas
    if _excecoes_capturadas:
        return

    anterior = sys.excepthook

    def ao_falhar(tipo, valor, tb):
        registar_excecao_nao_tratada(tipo, valor, tb, "interpretador")
        anterior(tipo, valor, tb)

    sys.excepthook = ao_falhar

    def ao_falhar_em_thread(args):
        registar_excecao_nao_tratada(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            f"thread {getattr(args.thread, 'name', '?')}",
        )

    threading.excepthook = ao_falhar_em_thread
    _excecoes_capturadas = True
