"""Ponto de entrada do Gerenciador de Tarefas.

Além de abrir a interface, aceita duas opções de linha de comandos:

``--version``
    Escreve a versão e sai.

``--verificar-banco``
    Corre ``PRAGMA integrity_check`` e mostra a versão do schema, **sem tocar
    no banco**: é o primeiro passo do diagnóstico quando alguém suspeita de
    dados corrompidos ou de uma migração que ficou a meio.

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

from core.log import (  # noqa: E402
    configurar_logging,
    instalar_captura_de_excecoes,
    obter_logger,
    registar_excecao_nao_tratada,
)
from core.version import APP_NAME, APP_VERSION  # noqa: E402


def instalar_captura_do_tk() -> None:
    """Encaminha para o log os erros dos *callbacks* da interface.

    O Tk apanha a exceção de um *callback*, imprime-a no ``stderr`` e continua.
    Empacotada em modo gráfico, a aplicação não tem ``stderr``: o botão não faz
    nada e não fica registo nenhum de porquê. Daí este gancho — o núcleo não o
    pode instalar sozinho porque não importa a interface (ADR-0001).
    """
    import tkinter as tk

    def relatar(self, tipo, valor, tb) -> None:  # assinatura exigida pelo Tk
        registar_excecao_nao_tratada(tipo, valor, tb, "interface")

    tk.Tk.report_callback_exception = relatar


def autoteste(relatorio: Path | None = None) -> int:
    """Executa as verificações de integridade e produz um relatório.

    Args:
        relatorio: arquivo onde escrever o relatório, além de o imprimir.
            Necessário quando a aplicação corre sem consola.

    Returns:
        0 se tudo passou, 1 se alguma verificação falhou.
    """
    from core import auditoria

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

    auditoria.ativar()

    # --- banco de dados
    try:
        import banco_de_dados

        banco_de_dados.criar_tabela()
        tarefa_id = banco_de_dados.adicionar_tarefa("autoteste", "2030-01-01")
        encontrada = banco_de_dados.obter_tarefa(tarefa_id)
        banco_de_dados.remover_tarefa(tarefa_id)
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

    # --- arranque real: a aplicação abre mesmo?
    try:
        verificar_arranque_real(verificar)
    except Exception as erro:  # pragma: no cover
        verificar("arranque real", False, repr(erro))

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


def verificar_banco() -> int:
    """Diz se o banco está íntegro e em que versão de schema está.

    Abre em modo **só de leitura**, de propósito: um diagnóstico que aplica
    migrações deixa de ser um diagnóstico. Sem isto, a única forma de ver o
    estado do banco de um utilizador era abrir a aplicação — que é
    precisamente o que já não estava a funcionar.

    Returns:
        0 se o banco está íntegro (ou ainda não existe), 1 caso contrário.
    """
    import sqlite3

    from core.paths import caminho_banco

    caminho = caminho_banco()
    linhas = [f"banco: {caminho}"]

    if not caminho.exists():
        linhas.append("ainda não existe — nada para verificar.")
        print("\n".join(linhas))
        return 0

    try:
        with sqlite3.connect(f"{caminho.as_uri()}?mode=ro", uri=True) as conexao:
            versao = int(conexao.execute("PRAGMA user_version").fetchone()[0])
            integridade = str(conexao.execute("PRAGMA integrity_check").fetchone()[0])
    except sqlite3.Error as erro:
        linhas.append(f"FALHA ao abrir o banco: {erro}")
        print("\n".join(linhas))
        obter_logger("main").error("Verificação do banco falhou: %s", erro)
        return 1

    linhas.append(f"versão do schema (user_version): {versao}")
    linhas.append(f"integrity_check: {integridade}")

    intacto = integridade == "ok"
    linhas.append("BANCO OK" if intacto else "BANCO COM PROBLEMAS")
    print("\n".join(linhas))
    obter_logger("main").info(
        "Verificação do banco: %s (schema v%d)", integridade, versao
    )
    return 0 if intacto else 1


def main(argumentos: list[str] | None = None) -> int:
    """Inicializa os serviços e abre a interface. Devolve o código de saída."""
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)

    if "--version" in argumentos or "-V" in argumentos:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    configurar_logging()
    instalar_captura_de_excecoes()
    instalar_captura_do_tk()
    logger = obter_logger("main")
    logger.info("%s %s a iniciar (pid=%s)", APP_NAME, APP_VERSION, os.getpid())

    if "--verificar-banco" in argumentos:
        try:
            return verificar_banco()
        except Exception:
            logger.exception("Falha ao verificar o banco.")
            return 1

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
        return abrir_aplicacao()
    except Exception:
        logger.exception("Falha fatal na aplicação.")
        return 1


def verificar_arranque_real(verificar) -> None:
    """Abre a aplicação pelo caminho verdadeiro e confirma que se vê.

    O autoteste antigo construía a janela principal diretamente. Passava
    sempre — inclusive enquanto o programa, ao ser aberto a sério, ficava a
    correr sem nada no ecrã, porque a janela de início de sessão era escondida
    com a raiz. Um build não devia poder dizer "válido" sobre um caminho que
    ninguém percorre.

    Corre numa área de dados temporária, **sempre**. Criar a conta de
    administrador na instalação real trancaria o utilizador fora do seu
    próprio programa: passaria a existir uma conta, e o ecrã de primeira
    utilização nunca mais apareceria.
    """
    import os
    import secrets
    import tempfile

    from core.paths import ENV_DATA_DIR

    #: Um arranque normal demora segundos. Isto é folga para uma máquina lenta,
    #: não uma espera esperada.
    LIMITE_MS = 60_000

    estado: dict = {}
    # A senha não pode conter o nome de utilizador: é a política da aplicação
    # a funcionar, e os dados de verificação têm de a respeitar como os de
    # qualquer pessoa.
    utilizador = "autoteste"
    senha = "Arranque-" + secrets.token_hex(12)

    def desistir(raiz) -> None:
        """Uma aplicação que não abre fica à espera para sempre.

        Foi exatamente o que aconteceu quando a janela de sessão era escondida
        com a raiz: o programa não falhava, ficava pendurado. Sem isto o
        autoteste herdava o mesmo bloqueio em vez de o reportar.
        """
        estado["expirou"] = True
        try:
            raiz.destroy()
        except Exception:  # pragma: no cover - defensivo
            pass

    def preencher_sessao(janela) -> None:
        """Faz o que uma pessoa faria, já com o ciclo de eventos a correr."""
        try:
            estado["sessao"] = bool(janela.winfo_viewable())
            janela.entrada_nome.insert(0, "Autoteste")
            janela.entrada_utilizador.insert(0, utilizador)
            janela.entrada_senha.insert(0, senha)
            janela.entrada_confirmacao.insert(0, senha)
            janela.submeter()
            if janela.winfo_exists() and janela.resultado is None:
                estado["erro_sessao"] = janela.mensagem.cget("text") or "recusado"
                janela.destroy()
        except Exception as erro:  # pragma: no cover - diagnóstico
            estado["erro_sessao"] = repr(erro)
            if janela.winfo_exists():
                janela.destroy()

    def ao_abrir_sessao(janela) -> None:
        # Agendado, não imediato: assim corre dentro da espera pela janela,
        # como um utilizador a escrever. A agir já, fechava a janela antes de
        # alguém começar a esperar por ela.
        janela.after(0, preencher_sessao, janela)
        janela.after(LIMITE_MS, desistir, janela.master)

    def ao_abrir_principal(janela) -> None:
        try:
            janela.update()
            estado["principal"] = bool(janela.winfo_viewable())
            estado["abas"] = len(janela.winfo_children())
        except Exception as erro:  # pragma: no cover - diagnóstico
            estado["erro_principal"] = repr(erro)
        finally:
            janela.destroy()  # sai do mainloop

    anterior = os.environ.get(ENV_DATA_DIR)
    with tempfile.TemporaryDirectory(prefix="gdt_arranque_") as isolado:
        os.environ[ENV_DATA_DIR] = isolado
        try:
            codigo = abrir_aplicacao(ao_abrir_sessao, ao_abrir_principal)
        except Exception as erro:  # pragma: no cover - diagnóstico
            estado["erro"] = repr(erro)
            codigo = 1
        finally:
            if anterior is None:
                os.environ.pop(ENV_DATA_DIR, None)
            else:
                os.environ[ENV_DATA_DIR] = anterior

    if estado.get("expirou"):
        motivo = "a aplicação ficou a correr sem abrir (esgotou o tempo)"
    else:
        motivo = estado.get("erro_sessao") or estado.get("erro") or ""

    sessao_ok = estado.get("sessao") is True
    principal_ok = estado.get("principal") is True
    verificar(
        "janela de início de sessão visível",
        sessao_ok,
        "" if sessao_ok else (motivo or "nada apareceu no ecrã"),
    )
    verificar(
        "janela principal visível",
        principal_ok,
        "" if principal_ok else (motivo or estado.get("erro_principal", "")),
    )
    verificar(
        "arranque completo",
        codigo == 0 and not estado.get("expirou"),
        f"código {codigo}",
    )


def abrir_aplicacao(ao_abrir_sessao=None, ao_abrir_principal=None) -> int:
    """Pede credenciais e, se forem aceites, abre a janela principal.

    O início de sessão e a aplicação partilham o mesmo interpretador Tk: a
    janela principal só é construída depois de haver sessão.

    Args:
        ao_abrir_sessao: chamado com a janela de início de sessão.
        ao_abrir_principal: chamado com a janela principal, já dentro do
            ``mainloop``.

    Os dois ganchos existem para o ``--autoteste`` poder verificar **este**
    arranque, e não um parecido. Um build só devia dizer "válido" sobre o
    caminho que o utilizador percorre.
    """
    import tkinter as tk

    import gui
    import login_ui
    from core import auditoria, utilizadores

    logger = obter_logger("main")
    auditoria.ativar()
    # A trilha só encolhe aqui, e só se houver política definida. Falhar a
    # aplicá-la nunca impede a aplicação de abrir.
    try:
        auditoria.aplicar_retencao_configurada()
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Falha ao aplicar a retenção da auditoria.")

    raiz = tk.Tk()
    raiz.withdraw()
    try:
        utilizador = login_ui.autenticar(raiz, ao_abrir=ao_abrir_sessao)
        if utilizador is None:
            logger.info("Início de sessão cancelado; a sair.")
            raiz.destroy()
            return 0

        janela = gui.criar_janela(raiz=raiz)
        if ao_abrir_principal is not None:
            # Dentro do mainloop, não antes: é lá que a janela existe a sério.
            janela.after(0, ao_abrir_principal, janela)
        janela.mainloop()
    finally:
        try:
            utilizadores.terminar_sessao()
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao encerrar a sessão.")

    logger.info("Aplicação encerrada normalmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
