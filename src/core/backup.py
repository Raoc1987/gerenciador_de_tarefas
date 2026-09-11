"""Cópias de segurança dos dados do utilizador.

Agora que há contas, estrutura da empresa, auditoria e dados de plugins, há
mais para perder do que uma lista de tarefas. Isto guarda tudo isso num
ficheiro só e sabe repô-lo.

**Uma cópia leva dados, nunca código.** Os plugins instalados ficam de fora de
propósito. Um ficheiro de cópia anda por e-mail, por pen, por uma pasta
partilhada — é exatamente o tipo de coisa que alguém troca por outra. Se
restaurar pudesse instalar plugins, restaurar passava a ser uma forma de
executar código de outra pessoa na máquina de quem confia no ficheiro. Os ids
e as versões dos plugins ficam registados no manifesto, para se saber o que
reinstalar, e mais nada.

O que entra:

* o banco (tarefas, contas, unidades, auditoria, registo de plugins);
* as configurações da aplicação e as de cada plugin;
* os dados privados de cada plugin.

O que fica de fora: os registos (``logs/``), que são diagnóstico e não dados,
e as pastas dos plugins instalados, pelo motivo acima.

Restaurar **nunca** apaga sem rede: o estado atual é guardado numa cópia de
emergência antes de qualquer coisa ser tocada, e o caminho dessa cópia é
devolvido a quem chamou.
"""

from __future__ import annotations

import json
import shutil
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import List, Optional, Tuple

from core.log import obter_logger
from core.paths import (
    caminho_banco,
    diretorio_config,
    diretorio_dados_utilizador,
    garantir_diretorio,
)
from core.version import APP_VERSION

logger = obter_logger(__name__)

#: Versão do formato da cópia. Muda se a arrumação interna mudar.
FORMATO = 1

NOME_MANIFESTO = "backup.json"
NOME_BANCO = "dados/tarefas.db"
PASTA_CONFIG = "config"
PASTA_DADOS_PLUGINS = "plugin_data"

#: Limites de sanidade ao ler um arquivo de fora.
MAX_ARQUIVOS = 20_000
MAX_TAMANHO_TOTAL = 500 * 1024 * 1024
MAX_RACIO_COMPRESSAO = 200


# --------------------------------------------------------------------- erros


class BackupError(Exception):
    """Erro base das cópias de segurança."""

    chave_mensagem = "backup_erro"


class ArquivoInvalidoError(BackupError):
    """O ficheiro não é uma cópia válida, ou não é seguro abrir."""

    chave_mensagem = "backup_invalido"


class BackupIncompativelError(BackupError):
    """A cópia veio de uma versão da aplicação mais recente do que esta."""

    chave_mensagem = "backup_incompativel"


# ----------------------------------------------------------------- manifesto


@dataclass(frozen=True)
class Manifesto:
    """O que uma cópia diz sobre si própria."""

    formato: int
    app_version: str
    esquema: int
    criado_em: str
    plugins: Tuple[Tuple[str, str], ...] = ()

    @property
    def data_legivel(self) -> str:
        return self.criado_em.replace("T", " ")

    def para_dicionario(self) -> dict:
        return {
            "formato": self.formato,
            "app_version": self.app_version,
            "esquema": self.esquema,
            "criado_em": self.criado_em,
            "plugins": [{"id": i, "versao": v} for i, v in self.plugins],
        }

    @classmethod
    def de_dicionario(cls, dados) -> "Manifesto":
        """Lê um manifesto vindo de um ficheiro que não controlamos.

        Raises:
            ArquivoInvalidoError: se faltar um campo ou o tipo estiver errado.
        """
        if not isinstance(dados, dict):
            raise ArquivoInvalidoError("O manifesto da cópia não é um objeto JSON.")
        try:
            formato = int(dados["formato"])
            esquema = int(dados["esquema"])
            app_version = str(dados["app_version"])
            criado_em = str(dados["criado_em"])
        except (KeyError, TypeError, ValueError) as erro:
            raise ArquivoInvalidoError(f"Manifesto incompleto: {erro}") from erro

        plugins: List[Tuple[str, str]] = []
        for entrada in dados.get("plugins") or []:
            if isinstance(entrada, dict) and "id" in entrada:
                plugins.append((str(entrada["id"]), str(entrada.get("versao", ""))))

        return cls(
            formato=formato,
            app_version=app_version,
            esquema=esquema,
            criado_em=criado_em,
            plugins=tuple(plugins),
        )


def _plugins_registados() -> Tuple[Tuple[str, str], ...]:
    """Ids e versões dos plugins instalados, só para memória futura."""
    try:
        import database

        database.criar_tabela()
        with database.conectar() as conexao:
            linhas = conexao.execute(
                "SELECT id, version FROM plugins ORDER BY id"
            ).fetchall()
        return tuple((str(i), str(v)) for i, v in linhas)
    except Exception:  # pragma: no cover - defensivo
        logger.exception("Não foi possível listar os plugins para o manifesto.")
        return ()


# ------------------------------------------------------------------- escrita


def nome_sugerido(agora: Optional[datetime] = None) -> str:
    """Nome de ficheiro com a data, para as cópias não se sobreporem."""
    momento = (agora or datetime.now()).strftime("%Y-%m-%d_%H%M")
    return f"copia-{momento}.zip"


def criar(destino: Path) -> Path:
    """Escreve uma cópia de segurança em ``destino``.

    O banco é copiado pela API do SQLite — ver :func:`database.copiar_para` —
    e não por cópia do ficheiro, para a cópia nunca apanhar uma escrita a meio.

    Returns:
        O caminho do ficheiro escrito.
    """
    import database

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    manifesto = Manifesto(
        formato=FORMATO,
        app_version=APP_VERSION,
        esquema=database.versao_do_esquema(),
        criado_em=datetime.now().isoformat(timespec="seconds"),
        plugins=_plugins_registados(),
    )

    raiz = diretorio_dados_utilizador()
    # Escrita para um ficheiro ao lado e só depois renomeada: uma cópia
    # interrompida a meio não pode ficar no sítio a fingir que está completa.
    provisorio = destino.with_suffix(destino.suffix + ".parcial")
    try:
        with TemporaryDirectory(prefix="gdt_backup_") as temporario:
            copia_banco = database.copiar_para(Path(temporario) / "tarefas.db")

            with zipfile.ZipFile(provisorio, "w", zipfile.ZIP_DEFLATED) as arquivo:
                arquivo.writestr(
                    NOME_MANIFESTO,
                    json.dumps(manifesto.para_dicionario(), ensure_ascii=False, indent=2),
                )
                arquivo.write(copia_banco, NOME_BANCO)
                for pasta, prefixo in (
                    (diretorio_config(), PASTA_CONFIG),
                    (raiz / PASTA_DADOS_PLUGINS, PASTA_DADOS_PLUGINS),
                ):
                    _guardar_pasta(arquivo, pasta, prefixo)

        provisorio.replace(destino)
    finally:
        provisorio.unlink(missing_ok=True)

    logger.info("Cópia de segurança criada: %s", destino)
    return destino


def _guardar_pasta(arquivo: zipfile.ZipFile, pasta: Path, prefixo: str) -> None:
    """Acrescenta uma pasta inteira ao arquivo, se existir."""
    if not pasta.is_dir():
        return
    for ficheiro in sorted(pasta.rglob("*")):
        if not ficheiro.is_file() or ficheiro.is_symlink():
            continue
        arquivo.write(ficheiro, f"{prefixo}/{ficheiro.relative_to(pasta).as_posix()}")


# -------------------------------------------------------------------- leitura


def _validar_nome(nome: str) -> str:
    """Valida um membro do arquivo e devolve-o normalizado.

    As mesmas defesas que os pacotes de plugins usam: um ficheiro de cópia vem
    de fora, e um ``..`` bem colocado escreveria onde lhe apetecesse.
    """
    normalizado = nome.replace("\\", "/")
    while normalizado.startswith("./"):
        normalizado = normalizado[2:]

    if not normalizado or normalizado in (".", "/"):
        raise ArquivoInvalidoError(f"Entrada inválida na cópia: {nome!r}.")
    if normalizado.startswith("/"):
        raise ArquivoInvalidoError(f"Caminho absoluto na cópia: {nome!r}.")
    if len(normalizado) > 1 and normalizado[1] == ":":
        raise ArquivoInvalidoError(f"Caminho com unidade de disco: {nome!r}.")

    partes = PurePosixPath(normalizado).parts
    if any(parte == ".." for parte in partes):
        raise ArquivoInvalidoError(f"Caminho com '..' na cópia: {nome!r}.")
    if any(parte.startswith("~") for parte in partes):
        raise ArquivoInvalidoError(f"Caminho suspeito na cópia: {nome!r}.")
    return normalizado


def _membros_seguros(arquivo: zipfile.ZipFile) -> List[zipfile.ZipInfo]:
    """Os membros a extrair, depois de recusar tudo o que não sirva."""
    membros: List[zipfile.ZipInfo] = []
    total = 0
    for info in arquivo.infolist():
        if info.is_dir():
            continue
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ArquivoInvalidoError(f"Ligação simbólica na cópia: {info.filename!r}.")

        nome = _validar_nome(info.filename)
        # Só três sítios são reconhecidos. Um ficheiro fora deles não faz
        # parte de uma cópia nossa, e extraí-lo seria escrever o desconhecido.
        if nome != NOME_MANIFESTO and nome != NOME_BANCO:
            if not nome.startswith((PASTA_CONFIG + "/", PASTA_DADOS_PLUGINS + "/")):
                raise ArquivoInvalidoError(f"Ficheiro inesperado na cópia: {nome!r}.")

        total += info.file_size
        if total > MAX_TAMANHO_TOTAL:
            raise ArquivoInvalidoError("A cópia é grande demais para ser aberta.")
        if info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_RACIO_COMPRESSAO:
            raise ArquivoInvalidoError(f"Compressão suspeita em {nome!r}.")

        membros.append(info)
        if len(membros) > MAX_ARQUIVOS:
            raise ArquivoInvalidoError("A cópia tem ficheiros a mais.")

    return membros


def inspecionar(caminho_zip: Path) -> Manifesto:
    """Lê o manifesto de uma cópia, sem extrair nada.

    É o que a interface mostra antes de perguntar se quer mesmo restaurar.

    Raises:
        ArquivoInvalidoError: se não for um ZIP, faltar o manifesto ou algum
            membro não for seguro.
    """
    caminho_zip = Path(caminho_zip)
    try:
        with zipfile.ZipFile(caminho_zip) as arquivo:
            _membros_seguros(arquivo)
            try:
                bruto = arquivo.read(NOME_MANIFESTO)
            except KeyError as erro:
                raise ArquivoInvalidoError(
                    "O ficheiro não tem manifesto: não é uma cópia desta aplicação."
                ) from erro
    except zipfile.BadZipFile as erro:
        raise ArquivoInvalidoError(f"O ficheiro não é um ZIP válido: {erro}") from erro
    except FileNotFoundError as erro:
        raise ArquivoInvalidoError(f"Ficheiro não encontrado: {caminho_zip}") from erro

    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ArquivoInvalidoError(f"Manifesto ilegível: {erro}") from erro

    return Manifesto.de_dicionario(dados)


def verificar_compatibilidade(manifesto: Manifesto) -> None:
    """Recusa uma cópia que esta build não sabe ler.

    Raises:
        BackupIncompativelError: se o formato ou o esquema forem mais recentes
            do que os desta aplicação. Abrir um banco do futuro é ler colunas
            que não se conhecem; atualizar a aplicação é a resposta certa.
    """
    import database

    if manifesto.formato > FORMATO:
        raise BackupIncompativelError(
            f"A cópia está no formato {manifesto.formato} e esta versão lê até "
            f"ao {FORMATO}. Atualize a aplicação."
        )
    if manifesto.esquema > database.VERSAO_ESQUEMA:
        raise BackupIncompativelError(
            f"A cópia foi feita pela versão {manifesto.app_version}, mais recente "
            f"do que a instalada ({APP_VERSION}). Atualize a aplicação e tente "
            "de novo — restaurá-la assim corromperia os dados."
        )


# -------------------------------------------------------------------- restauro


def restaurar(caminho_zip: Path) -> Path:
    """Repõe os dados de uma cópia, guardando o estado atual primeiro.

    A ordem importa e é esta: validar tudo, extrair para um sítio à parte,
    confirmar que o banco extraído abre, **só então** guardar o estado atual e
    trocar. Se alguma coisa falhar antes da troca, nada foi tocado.

    A aplicação deve ser reiniciada a seguir: quem já está a correr tem
    ligações e caches do banco antigo.

    Returns:
        O caminho da cópia de emergência com o estado anterior.

    Raises:
        ArquivoInvalidoError: cópia malformada ou insegura.
        BackupIncompativelError: cópia de uma versão mais recente.
    """
    import database

    caminho_zip = Path(caminho_zip)
    manifesto = inspecionar(caminho_zip)
    verificar_compatibilidade(manifesto)

    raiz = garantir_diretorio(diretorio_dados_utilizador())

    with TemporaryDirectory(prefix="gdt_restauro_") as temporario:
        extraido = Path(temporario) / "conteudo"
        with zipfile.ZipFile(caminho_zip) as arquivo:
            membros = _membros_seguros(arquivo)
            for info in membros:
                nome = _validar_nome(info.filename)
                alvo = extraido / nome
                if not _dentro(alvo, extraido):  # pragma: no cover - defensivo
                    raise ArquivoInvalidoError(f"Caminho fora do destino: {nome!r}.")
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with arquivo.open(info) as origem, open(alvo, "wb") as saida:
                    shutil.copyfileobj(origem, saida, length=1024 * 1024)

        banco_novo = extraido / NOME_BANCO
        if not banco_novo.is_file():
            raise ArquivoInvalidoError("A cópia não traz banco de dados.")
        _exigir_banco_legivel(banco_novo)

        # A rede de segurança. Só a partir daqui é que se toca em alguma coisa.
        emergencia = criar(raiz / "antes-do-restauro.zip")

        shutil.copyfile(banco_novo, caminho_banco())
        for pasta in (PASTA_CONFIG, PASTA_DADOS_PLUGINS):
            _repor_pasta(extraido / pasta, raiz / pasta)

    database.criar_tabela()  # aplica migrações se a cópia for mais antiga
    logger.info(
        "Cópia de %s restaurada; estado anterior guardado em %s",
        manifesto.data_legivel,
        emergencia,
    )
    return emergencia


def _exigir_banco_legivel(caminho: Path) -> None:
    """Confirma que o ficheiro é mesmo um banco desta aplicação."""
    import sqlite3

    import database

    try:
        conexao = sqlite3.connect(caminho)
        try:
            conexao.execute("SELECT 1 FROM tarefas LIMIT 1").fetchone()
        finally:
            conexao.close()
    except sqlite3.Error as erro:
        raise ArquivoInvalidoError(
            f"O banco dentro da cópia não abre: {erro}"
        ) from erro

    versao = database.versao_do_esquema(caminho)
    if versao > database.VERSAO_ESQUEMA:  # pragma: no cover - já visto no manifesto
        raise BackupIncompativelError(
            f"O banco da cópia está no esquema {versao} e esta versão lê até ao "
            f"{database.VERSAO_ESQUEMA}."
        )


def _repor_pasta(origem: Path, destino: Path) -> None:
    """Substitui ``destino`` pelo conteúdo de ``origem``.

    Uma pasta ausente na cópia significa "não havia nada"; apagar o que lá
    está é o comportamento certo, senão ficariam restos do estado anterior
    misturados com o restaurado.
    """
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    if origem.is_dir():
        shutil.copytree(origem, destino)


def _dentro(alvo: Path, raiz: Path) -> bool:
    try:
        alvo.resolve().relative_to(raiz.resolve())
        return True
    except ValueError:
        return False
