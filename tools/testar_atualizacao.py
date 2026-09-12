"""Simula uma atualização da aplicação e verifica que nada do utilizador se perde.

O que faz, de ponta a ponta, com executáveis reais::

    build v1.0.0  ->  "instala" numa pasta  ->  cria tarefas e ativa um plugin
                  ->  build v1.1.0
                  ->  substitui os arquivos da aplicação (o que o instalador faz)
                  ->  volta a abrir e confirma tarefas, configuração e plugins

Não precisa do Inno Setup: substitui a pasta da aplicação tal como o
instalador faria, o que é exatamente o passo que pode destruir dados se os
caminhos estiverem errados.

Uso::

    python tools/testar_atualizacao.py
    python tools/testar_atualizacao.py --versao-nova 2.0.0
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
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
VERSAO_PY = SRC / "core" / "version.py"

sys.path.insert(0, str(SRC))

from core.version import APP_ID, APP_VERSION  # noqa: E402


def _executar(executavel: Path, argumentos: list[str], dados: Path) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ)
    ambiente["GDT_DATA_DIR"] = str(dados)
    return subprocess.run(
        [str(executavel), *argumentos], capture_output=True, env=ambiente, timeout=300
    )


def _versao_do_exe(executavel: Path, dados: Path) -> str:
    resultado = _executar(executavel, ["--version"], dados)
    saida = (resultado.stdout or b"").decode("utf-8", errors="replace").strip()
    return saida.split()[-1] if saida else ""


def _construir(versao: str | None = None) -> Path:
    """Constrói o executável, opcionalmente com outra versão em version.py."""
    original = VERSAO_PY.read_text(encoding="utf-8")
    try:
        if versao is not None:
            VERSAO_PY.write_text(
                re.sub(
                    r'APP_VERSION: str = "[^"]+"',
                    f'APP_VERSION: str = "{versao}"',
                    original,
                ),
                encoding="utf-8",
            )
        subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "build.py"), "--sem-teste"],
            cwd=RAIZ,
            check=True,
            capture_output=True,
        )
    finally:
        if versao is not None:
            VERSAO_PY.write_text(original, encoding="utf-8")
    return RAIZ / "dist" / APP_ID


def _instalar(origem: Path, destino: Path) -> Path:
    """Copia a aplicação para a 'pasta de instalação' (o que o instalador faz)."""
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origem, destino)
    return destino / f"{APP_ID}.exe"


def _criar_dados_do_utilizador(dados: Path) -> None:
    """Cria tarefas como se o utilizador as tivesse escrito."""
    banco = dados / "tarefas.db"
    conexao = sqlite3.connect(banco)
    try:
        conexao.execute(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, criada_em)"
            " VALUES ('Tarefa anterior à atualização', '2026-12-24', 0, '2026-09-11T10:00:00')"
        )
        conexao.execute("UPDATE plugins SET enabled = 1 WHERE id = 'calendar'")
        conexao.commit()
    finally:
        conexao.close()
    (dados / "config").mkdir(parents=True, exist_ok=True)
    (dados / "config" / "app_config.json").write_text(
        '{"idioma": "en"}', encoding="utf-8"
    )


def _ler_estado(dados: Path) -> dict:
    conexao = sqlite3.connect(dados / "tarefas.db")
    try:
        tarefas = conexao.execute("SELECT descricao FROM tarefas").fetchall()
        plugins = conexao.execute("SELECT id, version, enabled FROM plugins").fetchall()
    finally:
        conexao.close()
    config = (dados / "config" / "app_config.json").read_text(encoding="utf-8")
    return {
        "tarefas": [t[0] for t in tarefas],
        "plugins": plugins,
        "config": config,
        "plugins_instalados": sorted(
            p.name for p in (dados / "plugins" / "installed").iterdir()
        ),
    }


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--versao-nova", default="1.1.0")
    opcoes = analisador.parse_args(argumentos)

    area = Path(tempfile.mkdtemp(prefix="gdt_upgrade_"))
    instalacao = area / "Programas" / APP_ID
    dados = area / "AppData" / APP_ID
    dados.mkdir(parents=True)
    falhas: list[str] = []

    def verificar(nome: str, condicao: bool, detalhe: str = "") -> None:
        print(f"[{'OK  ' if condicao else 'FALHA'}] {nome}{(' — ' + detalhe) if detalhe else ''}")
        if not condicao:
            falhas.append(nome)

    try:
        print(f"== 1. build da versão {APP_VERSION}")
        exe = _instalar(_construir(), instalacao)
        verificar("versão antiga instalada", _versao_do_exe(exe, dados) == APP_VERSION)

        print("== 2. primeira execução (cria banco e semeia plugins)")
        primeira = _executar(exe, ["--autoteste", "--relatorio", str(area / "r1.txt")], dados)
        verificar("primeira execução", primeira.returncode == 0)

        print("== 3. o utilizador cria dados")
        _criar_dados_do_utilizador(dados)
        antes = _ler_estado(dados)
        verificar("dados criados", bool(antes["tarefas"]), str(antes["tarefas"]))

        print(f"== 4. build da versão {opcoes.versao_nova}")
        nova = _construir(opcoes.versao_nova)

        print("== 5. atualização: substitui os arquivos da aplicação")
        exe = _instalar(nova, instalacao)
        verificar(
            "versão nova instalada",
            _versao_do_exe(exe, dados) == opcoes.versao_nova,
            _versao_do_exe(exe, dados),
        )

        print("== 6. execução após a atualização")
        segunda = _executar(exe, ["--autoteste", "--relatorio", str(area / "r2.txt")], dados)
        verificar("execução após atualizar", segunda.returncode == 0)
        if (area / "r2.txt").is_file():
            print((area / "r2.txt").read_text(encoding="utf-8"))

        depois = _ler_estado(dados)
        verificar("tarefas preservadas", depois["tarefas"] == antes["tarefas"], str(depois["tarefas"]))
        verificar("configuração preservada", depois["config"] == antes["config"], depois["config"])
        verificar(
            "plugins instalados preservados",
            depois["plugins_instalados"] == antes["plugins_instalados"],
            str(depois["plugins_instalados"]),
        )
        verificar(
            "estado dos plugins preservado",
            all(linha[2] == 1 for linha in depois["plugins"] if linha[0] == "calendar"),
            str(depois["plugins"]),
        )
        verificar(
            "dados do utilizador fora da pasta da aplicação",
            not (instalacao / "tarefas.db").exists(),
        )
    finally:
        shutil.rmtree(area, ignore_errors=True)
        # Deixa a árvore de build com a versão original.
        subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "build.py"), "--sem-teste"],
            cwd=RAIZ,
            capture_output=True,
        )

    if falhas:
        print(f"\nFALHOU: {', '.join(falhas)}")
        return 1
    print("\nATUALIZAÇÃO OK — nenhum dado do utilizador foi perdido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
