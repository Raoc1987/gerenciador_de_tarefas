"""Testes da captura de exceções que ninguém apanhou.

O que se verifica aqui não é o formato da mensagem: é que uma falha deixa
rasto. Uma exceção que se perde transforma um defeito reproduzível num
"às vezes não funciona".
"""

import logging
import sys
import threading

import pytest

import main
from core import log


@pytest.fixture(autouse=True)
def ganchos_repostos(monkeypatch):
    """Os ganchos são globais do processo: nenhum teste os deixa instalados."""
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(log, "_excecoes_capturadas", False)
    yield


# ====================================================== INTERPRETADOR


def test_excecao_nao_tratada_vai_para_o_log(caplog):
    log.instalar_captura_de_excecoes()

    with caplog.at_level(logging.CRITICAL):
        try:
            raise ValueError("rebentou")
        except ValueError:
            sys.excepthook(*sys.exc_info())

    assert "Exceção não tratada" in caplog.text
    assert "rebentou" in caplog.text, "o traceback tem de lá estar"


def test_o_gancho_anterior_continua_a_ser_chamado():
    """Instalar o log não pode roubar o comportamento de quem já lá estava."""
    chamado = []
    sys.excepthook = lambda *args: chamado.append(args)

    log.instalar_captura_de_excecoes()
    try:
        raise ValueError("rebentou")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    assert len(chamado) == 1


def test_interromper_nao_e_falha(caplog):
    """Ctrl+C é uma decisão de quem está a usar, não um defeito."""
    with caplog.at_level(logging.CRITICAL):
        log.registar_excecao_nao_tratada(KeyboardInterrupt, KeyboardInterrupt(), None)

    assert caplog.text == ""


def test_instalar_e_idempotente():
    log.instalar_captura_de_excecoes()
    primeiro = sys.excepthook
    log.instalar_captura_de_excecoes()

    assert sys.excepthook is primeiro, "instalar duas vezes empilharia ganchos"


# ============================================================ THREADS


def test_falha_em_thread_deixa_rasto(caplog):
    log.instalar_captura_de_excecoes()

    def rebentar():
        raise RuntimeError("falha na thread")

    with caplog.at_level(logging.CRITICAL):
        tarefa = threading.Thread(target=rebentar, name="ensaio")
        tarefa.start()
        tarefa.join()

    assert "falha na thread" in caplog.text
    assert "ensaio" in caplog.text, "saber qual a thread é metade do diagnóstico"


# =========================================================== INTERFACE


def test_erro_em_callback_do_tk_deixa_rasto(caplog, monkeypatch):
    """O Tk engole a exceção do callback; empacotado, não há stderr que a receba."""
    tk = pytest.importorskip("tkinter")
    monkeypatch.setattr(
        tk.Tk, "report_callback_exception", tk.Tk.report_callback_exception
    )

    main.instalar_captura_do_tk()

    with caplog.at_level(logging.CRITICAL):
        try:
            raise ValueError("erro no botão")
        except ValueError:
            # Como o Tk chama: na raiz, com o estado da exceção atual.
            tk.Tk.report_callback_exception(None, *sys.exc_info())

    assert "erro no botão" in caplog.text
    assert "interface" in caplog.text


# =============================================================== ROTAÇÃO


def test_o_log_guarda_o_suficiente_para_diagnosticar():
    """Uma sequência de erros não pode apagar a causa antes de ser lida."""
    total = log.TAMANHO_MAXIMO_LOG * (log.COPIAS_DE_LOG + 1)

    assert total >= 8 * 1024 * 1024, f"só {total} bytes de histórico de log"
