"""Ponto de entrada do Gerenciador de Tarefas.

Além de abrir a interface, aceita duas opções de linha de comandos:

``--version``
    Escreve a versão e sai.

``--autoteste [--relatorio ARQUIVO]``
    Verifica, sem intervenção do utilizador, que a aplicação está inteira:
    banco, idiomas, recursos, plugins e criação da janela. Foi feito para
    validar o **executável empacotado** — onde não há código-fonte nem pytest
    — e devolve código de saída diferente de zero se alguma verificação falhar.

    Como a aplicação é empacotada em modo gráfico (sem consola), o relatório
    também pode ser escrito num arquivo com ``--relatorio``: é essa a forma
    fiável de o ler a partir de um script de build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Permite executar tanto `python src/main.py` como o executável empacotado.
_DIRETORIO_SRC = Path(__file__).resolve().parent
if str(_DIRETORIO_SRC) not in sys.path:
    sys.path.insert(0, str(_DIRETORIO_SRC))

from core.log import configurar_logging, obter_logger  # noqa: E402
from core.version import APP_NAME, APP_VERSION  # noqa: E402


def autoteste(relatorio: Path | None = None) -> int:
    """Executa as verificações de integridade e produz um relatório.

    Args:
        relatorio: arquivo onde escrever o relatório, além de o imprimir.
            Necessário quando a aplicação corre sem consola.

    Returns:
        0 se tudo passou, 1 se alguma verificação falhou.
    """
    from core.paths import (
        caminho_banco,
        diretorio_dados_utilizador,
        diretorio_plugins_embutidos,
        diretorio_plugins_instalados,
        diretorio_recursos,
        esta_congelado,
    )

    falhas: list[str] = []
    linhas: list[str] = []

    def verificar(nome: str, condicao: bool, detalhe: str = "") -> None:
        marca = "OK  " if condicao else "FALHA"
        linhas.append(f"[{marca}] {nome}{(' — ' + detalhe) if detalhe else ''}")
        if not condicao:
            falhas.append(nome)

    linhas.append(f"{APP_NAME} {APP_VERSION}")
    linhas.append(f"congelado={esta_congelado()}  recursos={diretorio_recursos()}")
    linhas.append(f"dados do utilizador={diretorio_dados_utilizador()}")

    # --- banco de dados
    try:
        import database

        database.criar_tabela()
        tarefa_id = database.adicionar_tarefa("autoteste", "2030-01-01")
        encontrada = database.obter_tarefa(tarefa_id)
        database.remover_tarefa(tarefa_id)
        verificar("banco de dados", encontrada is not None, str(caminho_banco()))
    except Exception as erro:  # pragma: no cover - caminho de diagnóstico
        verificar("banco de dados", False, repr(erro))

    # --- idiomas
    try:
        import language_manager as lm

        traducoes = {}
        for codigo in lm.IDIOMAS_SUPORTADOS:
            lm.definir_idioma(codigo, persistir=False)
            traducoes[codigo] = lm.carregar_texto("titulo")
        lm.restaurar_idioma_guardado()
        verificar(
            "idiomas",
            all(valor != "titulo" for valor in traducoes.values()),
            ", ".join(f"{c}={v}" for c, v in traducoes.items()),
        )
    except Exception as erro:  # pragma: no cover
        verificar("idiomas", False, repr(erro))

    # --- plugins
    try:
        from core.plugin_manager import PluginManager
        from core.plugin_registry import RegistroEstadoBanco
        from core.plugin_sources import FontePastasLocais

        gerenciador = PluginManager(registro=RegistroEstadoBanco())
        embutidos = FontePastasLocais(diretorio_plugins_embutidos())
        oferecidos = [p.id for p in embutidos.listar()]
        gerenciador.semear_de_fonte(embutidos)
        conhecidos = [r.id for r in gerenciador.descobrir()]
        verificar(
            "plugins embutidos",
            bool(oferecidos),
            f"oferecidos={oferecidos} em {diretorio_plugins_embutidos()}",
        )
        verificar(
            "plugins instalados",
            all(pid in conhecidos for pid in oferecidos),
            f"{conhecidos} em {diretorio_plugins_instalados()}",
        )
    except Exception as erro:  # pragma: no cover
        verificar("plugins", False, repr(erro))

    # --- interface
    try:
        import gui

        janela = gui.criar_janela()
        janela.update_idletasks()
        abas = janela.winfo_children()
        gerenciador_gui = getattr(janela, "gerenciador_de_plugins", None)
        if gerenciador_gui is not None:
            # persistir=False: o autoteste verifica, não altera as escolhas do
            # utilizador — pode ser corrido sobre uma instalação a sério.
            resultado = gerenciador_gui.ativar("calendar", persistir=False)
            verificar("ativar plugin calendar", resultado.sucesso, resultado.detalhes)
            janela.update()
            gerenciador_gui.desativar("calendar", persistir=False)
            gerenciador_gui.desativar_todos()
        janela.destroy()
        verificar("interface gráfica", bool(abas))
    except Exception as erro:  # pragma: no cover
        verificar("interface gráfica", False, repr(erro))

    if falhas:
        linhas.append(
            f"AUTOTESTE FALHOU: {len(falhas)} verificação(ões) — {', '.join(falhas)}"
        )
    else:
        linhas.append("AUTOTESTE OK")

    texto = "\n".join(linhas)
    try:
        print(texto)
    except Exception:  # pragma: no cover - sem consola no modo gráfico
        pass
    if relatorio is not None:
        try:
            relatorio.parent.mkdir(parents=True, exist_ok=True)
            relatorio.write_text(texto + "\n", encoding="utf-8")
        except OSError:  # pragma: no cover - diagnóstico
            obter_logger("main").exception("Falha ao escrever o relatório do autoteste.")

    obter_logger("main").info("Autoteste: %s", "FALHOU" if falhas else "OK")
    return 1 if falhas else 0


def main(argumentos: list[str] | None = None) -> int:
    """Inicializa os serviços e abre a interface. Devolve o código de saída."""
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)

    if "--version" in argumentos or "-V" in argumentos:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    configurar_logging()
    logger = obter_logger("main")
    logger.info("%s %s a iniciar (pid=%s)", APP_NAME, APP_VERSION, os.getpid())

    if "--autoteste" in argumentos:
        relatorio = None
        if "--relatorio" in argumentos:
            indice = argumentos.index("--relatorio")
            if indice + 1 < len(argumentos):
                relatorio = Path(argumentos[indice + 1])
        try:
            return autoteste(relatorio)
        except Exception:
            logger.exception("Falha no autoteste.")
            return 1

    try:
        from gui import iniciar_interface

        iniciar_interface()
    except Exception:
        logger.exception("Falha fatal na aplicação.")
        return 1

    logger.info("Aplicação encerrada normalmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
