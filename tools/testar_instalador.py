"""Testa o instalador Windows de verdade: instalar, atualizar e desinstalar.

Percurso executado (tudo em modo silencioso, com executáveis reais)::

    instalação limpa  ->  atalhos e registo de desinstalação
                      ->  primeira execução, dados do utilizador criados
                      ->  instalador de uma versão mais recente
                      ->  atualização na mesma pasta, dados preservados
                      ->  desinstalação: programa removido, DADOS PRESERVADOS
                      ->  desinstalação com /REMOVEDATA=yes: dados removidos

Requer o Inno Setup (ver ``tools/build_installer.py``).

Segurança: usa a pasta de dados real (``%APPDATA%\\GerenciadorDeTarefas``),
porque é exatamente essa que a desinstalação tem de respeitar. Se ela já
existir antes do teste, o teste **aborta** em vez de mexer nos seus dados.

Uso::

    python tools/testar_instalador.py
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
VERSAO_PY = SRC / "core" / "version.py"

sys.path.insert(0, str(SRC))

from core.version import APP_ID, APP_NAME, APP_VERSION  # noqa: E402

INSTALADOR = RAIZ / "installer" / "Output" / f"{APP_ID}-Setup.exe"


def pasta_de_dados() -> Path:
    """A mesma pasta que a aplicação e o instalador usam."""
    return Path(os.environ["APPDATA"]) / APP_ID


def atalho_menu_iniciar() -> Path:
    """Atalho criado no Menu Iniciar do utilizador atual."""
    return (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / f"{APP_NAME}.lnk"
    )


def _correr(comando: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(comando, capture_output=True, timeout=600, **kwargs)


def _construir(versao: str | None) -> None:
    """Constrói o .exe e o instalador, opcionalmente com outra versão."""
    original = VERSAO_PY.read_text(encoding="utf-8")
    try:
        if versao is not None:
            VERSAO_PY.write_text(
                re.sub(r'APP_VERSION: str = "[^"]+"', f'APP_VERSION: str = "{versao}"', original),
                encoding="utf-8",
            )
        for script in ("build.py", "build_installer.py"):
            argumentos = [sys.executable, str(RAIZ / "tools" / script)]
            if script == "build.py":
                argumentos.append("--sem-teste")
            resultado = _correr(argumentos, cwd=RAIZ)
            if resultado.returncode != 0:
                saida = (resultado.stdout or b"").decode("utf-8", errors="replace")
                erro = (resultado.stderr or b"").decode("utf-8", errors="replace")
                raise SystemExit(f"{script} falhou:\n{saida[-2000:]}\n{erro[-2000:]}")
    finally:
        if versao is not None:
            VERSAO_PY.write_text(original, encoding="utf-8")


def _instalar(destino: Path) -> int:
    """Instalação silenciosa só para o utilizador atual."""
    return _correr(
        [
            str(INSTALADOR),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CURRENTUSER",
            f"/DIR={destino}",
        ]
    ).returncode


def _desinstalar(destino: Path, remover_dados: bool = False) -> int:
    desinstalador = next(destino.glob("unins*.exe"), None)
    if desinstalador is None:
        raise SystemExit(f"Desinstalador não encontrado em {destino}")
    argumentos = [str(desinstalador), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    if remover_dados:
        argumentos.append("/REMOVEDATA=yes")
    # O desinstalador copia-se para %TEMP% e devolve o controlo de imediato;
    # esperar pelo processo filho garante que já terminou.
    return _correr(argumentos).returncode


def _esperar(condicao, segundos: int = 30) -> bool:
    """Espera até ``condicao()`` ser verdadeira.

    O desinstalador do Inno Setup copia-se para %TEMP% e devolve o controlo
    antes de terminar: verificar de imediato dá falsos negativos.
    """
    for _ in range(segundos * 2):
        if condicao():
            return True
        time.sleep(0.5)
    return condicao()


def _versao_instalada(destino: Path, dados: Path) -> str:
    """A versão que o executável instalado diz ter.

    Quando não responde, devolve o motivo em vez de ``""``: uma verificação que
    falha sem dizer o que obteve obriga quem lê o registo do CI a adivinhar.
    """
    ambiente = dict(os.environ)
    ambiente["GDT_DATA_DIR"] = str(dados)
    try:
        resultado = _correr([str(destino / f"{APP_ID}.exe"), "--version"], env=ambiente)
    except (OSError, subprocess.TimeoutExpired) as erro:
        return f"(não respondeu: {erro})"

    saida = (resultado.stdout or b"").decode("utf-8", errors="replace").strip()
    if not saida:
        erro = (resultado.stderr or b"").decode("utf-8", errors="replace").strip()
        detalhe = f"; {erro[:200]}" if erro else ""
        return f"(sem saída, código {resultado.returncode}{detalhe})"
    return saida.split()[-1]


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--versao-nova", default="1.1.0")
    opcoes = analisador.parse_args(argumentos)

    if os.name != "nt":
        raise SystemExit("Este teste só corre no Windows.")

    dados = pasta_de_dados()
    if dados.exists():
        raise SystemExit(
            f"{dados} já existe.\n"
            "O teste precisa de começar do zero para poder verificar a "
            "desinstalação. Faça uma cópia e apague a pasta, ou corra o teste "
            "noutra conta de utilizador."
        )

    area = Path(tempfile.mkdtemp(prefix="gdt_inst_"))
    destino = area / "Programas" / APP_ID
    falhas: list[str] = []

    def verificar(nome: str, condicao: bool, detalhe: str = "") -> None:
        print(f"[{'OK  ' if condicao else 'FALHA'}] {nome}{(' — ' + detalhe) if detalhe else ''}")
        if not condicao:
            falhas.append(nome)

    try:
        print(f"== 1. construir a versão {APP_VERSION} e o instalador")
        _construir(None)
        verificar("instalador gerado", INSTALADOR.is_file(),
                  f"{INSTALADOR.stat().st_size / (1024 * 1024):.1f} MiB")

        print("== 2. instalação limpa (silenciosa)")
        codigo = _instalar(destino)
        verificar("instalador terminou sem erro", codigo == 0, f"código {codigo}")
        verificar("executável instalado", (destino / f"{APP_ID}.exe").is_file())
        verificar("recursos instalados",
                  (destino / "_internal" / "assets" / "idiomas" / "pt.json").is_file())
        verificar("desinstalador criado", any(destino.glob("unins*.exe")))
        verificar("atalho no Menu Iniciar", atalho_menu_iniciar().is_file(),
                  str(atalho_menu_iniciar()))
        # A instalação silenciosa devolve o controlo antes de o último ficheiro
        # estar no sítio — é a mesma assincronia que o `_esperar` já cobre na
        # desinstalação. Correr o executável de imediato apanha-o a meio, e uma
        # amostra única transformava isso numa falha sem explicação.
        obtida = ""

        def versao_bate() -> bool:
            nonlocal obtida
            obtida = _versao_instalada(destino, dados)
            return obtida == APP_VERSION

        verificar("versão correta", _esperar(versao_bate), obtida)

        print("== 3. primeira execução (cria dados do utilizador)")
        ambiente = dict(os.environ)
        relatorio = area / "r1.txt"
        primeira = _correr(
            [str(destino / f"{APP_ID}.exe"), "--autoteste", "--relatorio", str(relatorio)],
            env=ambiente,
        )
        verificar("aplicação instalada arranca", primeira.returncode == 0)
        verificar("dados criados em %APPDATA%", (dados / "tarefas.db").is_file(), str(dados))
        verificar("plugin embutido instalado",
                  (dados / "plugins" / "installed" / "calendar" / "plugin.json").is_file())

        conexao = sqlite3.connect(dados / "tarefas.db")
        conexao.execute(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, criada_em)"
            " VALUES ('Tarefa criada antes de atualizar', '2026-12-24', 0, '2026-09-11T10:00:00')"
        )
        conexao.execute("UPDATE plugins SET enabled = 1 WHERE id = 'calendar'")
        conexao.commit()
        conexao.close()

        print(f"== 4. construir e instalar a versão {opcoes.versao_nova} por cima")
        _construir(opcoes.versao_nova)
        codigo = _instalar(destino)
        verificar("atualização terminou sem erro", codigo == 0, f"código {codigo}")
        verificar("versão atualizada",
                  _versao_instalada(destino, dados) == opcoes.versao_nova,
                  _versao_instalada(destino, dados))

        conexao = sqlite3.connect(dados / "tarefas.db")
        tarefas = [t[0] for t in conexao.execute("SELECT descricao FROM tarefas")]
        plugins = conexao.execute("SELECT id, enabled FROM plugins").fetchall()
        conexao.close()
        verificar("tarefas preservadas na atualização",
                  "Tarefa criada antes de atualizar" in tarefas, str(tarefas))
        verificar("plugin continua ativo", ("calendar", 1) in plugins, str(plugins))

        print("== 5. desinstalação (sem pedir remoção de dados)")
        codigo = _desinstalar(destino)
        verificar("desinstalador terminou sem erro", codigo == 0, f"código {codigo}")
        verificar(
            "programa removido",
            _esperar(lambda: not (destino / f"{APP_ID}.exe").exists()),
        )
        verificar("atalho removido", _esperar(lambda: not atalho_menu_iniciar().exists()))
        verificar("DADOS DO UTILIZADOR PRESERVADOS", (dados / "tarefas.db").is_file())
        verificar("plugins do utilizador preservados",
                  (dados / "plugins" / "installed" / "calendar").is_dir())

        print("== 6. reinstalar e desinstalar com /REMOVEDATA=yes")
        _instalar(destino)
        codigo = _desinstalar(destino, remover_dados=True)
        verificar("desinstalação com remoção de dados", codigo == 0, f"código {codigo}")
        verificar(
            "dados removidos a pedido explícito",
            _esperar(lambda: not dados.exists()),
            str(dados),
        )
    finally:
        # Restaura a árvore com a versão original e limpa o que o teste criou.
        _construir(None)
        shutil.rmtree(area, ignore_errors=True)
        shutil.rmtree(dados, ignore_errors=True)
        atalho = atalho_menu_iniciar()
        if atalho.exists():
            atalho.unlink()

    if falhas:
        print(f"\nFALHOU: {', '.join(falhas)}")
        return 1
    print("\nINSTALADOR OK — instalação, atualização e desinstalação verificadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
