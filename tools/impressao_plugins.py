"""Impressão digital dos plugins que acompanham a aplicação.

Serve uma regra só: **um plugin embutido não muda sem subir a versão**. A
versão é a única coisa que a semeadura do arranque tem para decidir se a
cópia instalada na máquina de alguém está para trás. Quando o conteúdo muda e
a versão fica na mesma, a aplicação instalada continua com o código antigo
para sempre — foi assim que o ``calendar`` ficou sem o ``permissions`` que já
estava no repositório.

``docs/architecture/plugins-embutidos.json`` guarda a impressão de cada
plugin e ``tests/test_arquitetura.py`` falha quando deixa de coincidir. O
teste não sabe se a mudança é grande ou pequena: sabe que houve uma, e que
uma versão nova é o que a faz chegar a quem já tem a aplicação.

Uso::

    python tools/impressao_plugins.py            # mostra o que está diferente
    python tools/impressao_plugins.py --gravar   # regrava a declaração
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGINS = RAIZ / "plugins" / "available"
DECLARACAO = RAIZ / "docs" / "architecture" / "plugins-embutidos.json"

#: Nomes que nunca entram num pacote — os mesmos que ``empacotar_plugin``
#: ignora. A impressão cobre o que é distribuído, não o que está no disco.
IGNORADOS = {"__pycache__", ".git", ".pytest_cache", ".DS_Store"}

#: Onde os fins de linha são normalizados antes de somar.
#:
#: O repositório é lido em CRLF no Windows e em LF no Linux (``core.autocrlf``)
#: — sem isto, a mesma árvore daria impressões diferentes e o teste falharia
#: consoante a máquina. Só para texto: num binário, dois bytes trocados são
#: uma mudança e têm de contar.
EXTENSOES_DE_TEXTO = {".py", ".json", ".md", ".txt"}


def arquivos_de(pasta: Path) -> list[Path]:
    """Os arquivos do plugin que entram no pacote, por ordem estável."""
    return sorted(
        arquivo
        for arquivo in pasta.rglob("*")
        if arquivo.is_file()
        and not any(parte in IGNORADOS for parte in arquivo.relative_to(pasta).parts)
    )


def impressao_de_pasta(pasta: Path) -> str:
    """Resumo SHA-256 do conteúdo de um plugin.

    Entram os caminhos e o conteúdo: renomear um arquivo é uma mudança tanto
    como editá-lo.
    """
    resumo = hashlib.sha256()
    for arquivo in arquivos_de(pasta):
        conteudo = arquivo.read_bytes()
        if arquivo.suffix.lower() in EXTENSOES_DE_TEXTO:
            conteudo = conteudo.replace(b"\r\n", b"\n")
        resumo.update(arquivo.relative_to(pasta).as_posix().encode("utf-8"))
        resumo.update(b"\0")
        resumo.update(hashlib.sha256(conteudo).digest())
    return resumo.hexdigest()


def versao_de(pasta: Path) -> str:
    """Versão declarada no manifesto do plugin."""
    manifesto = json.loads((pasta / "plugin.json").read_text(encoding="utf-8"))
    return manifesto["version"]


def pastas_de_plugins() -> list[Path]:
    """As pastas de plugin embutido do repositório."""
    return sorted(
        pasta
        for pasta in PLUGINS.iterdir()
        if pasta.is_dir() and (pasta / "plugin.json").is_file()
    )


def impressoes_atuais() -> dict:
    """O que está no disco, no formato da declaração."""
    return {
        pasta.name: {"versao": versao_de(pasta), "impressao": impressao_de_pasta(pasta)}
        for pasta in pastas_de_plugins()
    }


def ler_declaracao() -> dict:
    """A declaração gravada, ou um esqueleto vazio se ainda não existir."""
    if not DECLARACAO.is_file():
        return {"plugins": {}}
    return json.loads(DECLARACAO.read_text(encoding="utf-8"))


def gravar(declaracao: dict, plugins: dict) -> None:
    """Regrava a declaração, preservando os textos que explicam a regra."""
    declaracao["plugins"] = plugins
    DECLARACAO.write_text(
        json.dumps(declaracao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argumentos: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comandos."""
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument(
        "--gravar",
        action="store_true",
        help="atualiza a declaração em vez de apenas comparar",
    )
    opcoes = analisador.parse_args(argumentos)

    declaracao = ler_declaracao()
    declarados = declaracao.get("plugins", {})
    atuais = impressoes_atuais()

    diferentes = [
        nome
        for nome in sorted(set(declarados) | set(atuais))
        if declarados.get(nome) != atuais.get(nome)
    ]

    if opcoes.gravar:
        gravar(declaracao, atuais)
        if diferentes:
            print(f"Declaração atualizada: {', '.join(diferentes)}")
            print("Confirme que a versão subiu em cada um antes de fazer commit.")
        else:
            print("Declaração já estava atualizada.")
        return 0

    for nome in diferentes:
        antes, agora = declarados.get(nome), atuais.get(nome)
        if antes is None:
            print(f"[novo]     {nome} v{agora['versao']}")
        elif agora is None:
            print(f"[removido] {nome} (declarado em v{antes['versao']})")
        elif antes["versao"] == agora["versao"]:
            print(f"[MUDOU]    {nome} continua em v{agora['versao']} — suba a versão.")
        else:
            print(f"[versão]   {nome} {antes['versao']} -> {agora['versao']}")

    if not diferentes:
        print("Nada mudou nos plugins embutidos.")
        return 0

    print(f"\nPara aceitar: python {Path(__file__).relative_to(RAIZ).as_posix()} --gravar")
    return 1


if __name__ == "__main__":
    sys.exit(main())
