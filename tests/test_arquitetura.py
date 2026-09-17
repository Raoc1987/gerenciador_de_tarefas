"""Testes que fazem a arquitetura falhar quando é violada.

Uma regra de arquitetura que não falha um teste é uma sugestão (ADR-0004).
Estes testes leem o código e verificam:

* que nada entra em ``src/core/`` sem justificação escrita;
* que as camadas não se invertem;
* que os plugins continuam do lado de fora do núcleo;
* que os documentos de arquitetura não ficam a mentir.

Falhar aqui não é um bug a tapar: é uma decisão de arquitetura por tomar.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"
CORE = SRC / "core"
PLUGINS = RAIZ / "plugins" / "available"
ARQUITETURA = RAIZ / "docs" / "architecture"

#: Módulos de interface. Nada abaixo da camada de UI os pode importar.
INTERFACE = {
    "tkinter",
    "gui",
    "dashboard_ui",
    "plugin_ui",
    "auditoria_ui",
    "login_ui",
    "utilizadores_ui",
    "componentes",
}


def importados_por(arquivo: Path) -> set:
    """Nomes de topo importados por um ficheiro Python."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes.add(no.module)
    return nomes


def modulos_de(pasta: Path) -> list:
    return sorted(p for p in pasta.glob("*.py"))


@pytest.fixture(scope="module")
def inventario() -> dict:
    """O inventário do Core, com a justificação de cada módulo."""
    dados = json.loads((ARQUITETURA / "core-inventory.json").read_text(encoding="utf-8"))
    return dados["modulos"]


# ======================================================= INVENTÁRIO DO CORE


def test_tudo_no_core_esta_inventariado(inventario):
    """ADR-0004: nada entra no Core sem justificação escrita.

    Se este teste falhar por causa de um módulo novo, a pergunta não é "como
    faço passar o teste" — é "isto pertence mesmo ao Core, ou é um Service,
    um Module ou um Plugin?". Ver docs/architecture/CLASSIFICACAO.md.
    """
    no_disco = {arquivo.name for arquivo in modulos_de(CORE)}
    inventariados = set(inventario)

    novos = no_disco - inventariados
    assert not novos, (
        f"Módulos em src/core/ sem justificação no inventário: {sorted(novos)}. "
        "Justifique porque pertencem ao Core, ou mude-os de sítio."
    )

    desaparecidos = inventariados - no_disco
    assert not desaparecidos, (
        f"O inventário fala de módulos que já não existem: {sorted(desaparecidos)}."
    )


def test_cada_justificacao_diz_alguma_coisa(inventario):
    """"Faz parte do Core" não é uma justificação."""
    for modulo, razao in inventario.items():
        if modulo == "__init__.py":  # marcador de pacote, não é uma decisão
            continue
        assert len(razao.split()) >= 4, f"{modulo}: a justificação é curta demais."
        assert razao.strip().endswith("."), f"{modulo}: escreva uma frase."


def test_o_core_e_pequeno_o_suficiente_para_ser_lido(inventario):
    """Um Core que ninguém consegue ler inteiro deixou de ser um Core."""
    assert len(inventario) <= 20, (
        f"O Core tem {len(inventario)} módulos. Antes de acrescentar mais um, "
        "veja o que devia ter saído de lá."
    )


# ============================================================== CAMADAS


def test_o_core_nao_conhece_a_interface():
    for arquivo in modulos_de(CORE):
        for importado in importados_por(arquivo):
            raiz = importado.split(".")[0]
            assert raiz not in INTERFACE, f"core/{arquivo.name} importa {importado}"


def test_o_core_nao_depende_da_analise_nem_dos_relatorios():
    """A dependência é ao contrário: a análise usa o Core."""
    for arquivo in modulos_de(CORE):
        for importado in importados_por(arquivo):
            raiz = importado.split(".")[0]
            assert raiz not in {"analitica", "relatorios"}, (
                f"core/{arquivo.name} importa {importado}"
            )


@pytest.mark.parametrize("pacote", ["analitica", "relatorios", "regras"])
def test_as_camadas_de_aplicacao_nao_tocam_na_interface(pacote):
    """ADR-0003: têm de servir a janela, um agendamento ou um plugin por igual.

    Também não conhecem o motor de plugins: quem calcula não carrega código.
    """
    for arquivo in (SRC / pacote).rglob("*.py"):
        for importado in importados_por(arquivo):
            raiz = importado.split(".")[0]
            assert raiz not in INTERFACE, f"{pacote}/{arquivo.name} importa {importado}"
            assert importado != "core.plugin_manager", (
                f"{pacote}/{arquivo.name} importa o motor de plugins"
            )


def test_so_as_fontes_da_analise_conhecem_o_banco():
    for arquivo in (SRC / "analitica").rglob("*.py"):
        if arquivo.name == "fontes.py":
            continue
        assert "banco_de_dados" not in importados_por(arquivo), (
            f"analitica/{arquivo.name} devia pedir os dados a fontes.py"
        )


def test_o_motor_de_automacao_nao_conhece_dominios():
    """Se o motor souber o que é uma tarefa, deixou de ser um motor.

    O que ele executa são ações que outros registaram. Conhecer um domínio
    seria o primeiro passo para se tornar o sítio onde todos se encontram —
    um monólito com outro nome.
    """
    dominios = {"tarefas_servico", "analitica", "relatorios", "organizacao"}
    for arquivo in (SRC / "regras").rglob("*.py"):
        for importado in importados_por(arquivo):
            raiz = importado.split(".")[0]
            assert raiz not in dominios, f"regras/{arquivo.name} importa {importado}"
            # O armazenamento é infraestrutura, não um domínio — a auditoria e
            # a organização também o usam. Mas só o repositório: o motor que
            # soubesse ler o banco começaria a lê-lo para decidir.
            if arquivo.name != "repositorio.py":
                assert raiz != "banco_de_dados", f"regras/{arquivo.name} importa banco_de_dados"


#: O que só :mod:`tarefas_servico` pode fazer ao armazenamento.
FUNCOES_DE_TAREFAS = {
    "adicionar_tarefa", "buscar_tarefas", "buscar_tarefas_completas",
    "tarefas_por_data", "obter_tarefa", "concluir_tarefa", "remover_tarefa",
    "dono_de", "unidade_de",
}

#: Quem pode mexer nas tarefas: a política, o próprio armazenamento, e o
#: arranque da aplicação (que só cria o esquema).
PODEM_TOCAR_EM_TAREFAS = {"tarefas_servico.py", "banco_de_dados.py", "main.py"}


def test_a_politica_de_tarefas_vive_num_sitio_so():
    """Quem decide o que a sessão vê é o serviço, não a interface.

    A regra é sobre as **tarefas**, não sobre o armazenamento em geral: um
    serviço que guarda o seu próprio estado numa tabela sua não está a furar
    nada. O que não pode é ler ou escrever tarefas por fora, porque aí saltava
    a visibilidade por dono e por unidade.

    Duas maneiras de furar, e as duas são verificadas: chamar as funções de
    tarefas do armazenamento, ou escrever SQL contra a tabela.
    """
    for arquivo in modulos_de(SRC):
        if arquivo.name in PODEM_TOCAR_EM_TAREFAS:
            continue
        codigo = arquivo.read_text(encoding="utf-8")
        arvore = ast.parse(codigo)

        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute) and no.attr in FUNCOES_DE_TAREFAS:
                origem = getattr(no.value, "id", "")
                assert origem != "banco_de_dados", (
                    f"{arquivo.name} chama banco_de_dados.{no.attr}; use tarefas_servico."
                )
            elif isinstance(no, ast.ImportFrom) and no.module == "banco_de_dados":
                trazidos = {alias.name for alias in no.names} & FUNCOES_DE_TAREFAS
                assert not trazidos, (
                    f"{arquivo.name} importa {sorted(trazidos)} de banco_de_dados."
                )
            elif isinstance(no, ast.Constant) and isinstance(no.value, str):
                sql = " ".join(no.value.lower().split())
                for padrao in ("from tarefas", "into tarefas", "update tarefas"):
                    assert padrao not in sql, (
                        f"{arquivo.name} consulta a tabela tarefas diretamente."
                    )


def test_a_regra_das_tarefas_apanharia_uma_fuga():
    """O teste acima só vale se falhar quando alguém fura mesmo.

    Verificado aqui em vez de acreditado: as duas maneiras de chegar às
    tarefas por fora têm de ser detetadas.
    """
    pela_funcao = [
        "import banco_de_dados",
        "def ler():",
        "    return banco_de_dados.buscar_tarefas()",
    ]
    pelo_sql = [
        "import banco_de_dados",
        "def ler():",
        "    with banco_de_dados.conectar() as c:",
        "        return c.execute('SELECT id FROM tarefas').fetchall()",
    ]

    for fuga in (pela_funcao, pelo_sql):
        arvore = ast.parse(chr(10).join(fuga))
        apanhado = False
        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute) and no.attr in FUNCOES_DE_TAREFAS:
                apanhado = True
            elif isinstance(no, ast.Constant) and isinstance(no.value, str):
                if "from tarefas" in " ".join(no.value.lower().split()):
                    apanhado = True
        assert apanhado, f"esta fuga passava despercebida: {fuga[-1]!r}"


# =============================================== SEM DEPENDÊNCIAS EXTERNAS


def _nomes_locais() -> set:
    """Módulos e pacotes que a própria aplicação fornece."""
    nomes = {caminho.stem for caminho in SRC.rglob("*.py")}
    nomes |= {p.name for p in SRC.iterdir() if p.is_dir()}
    # Cada plugin importa os seus próprios módulos irmãos.
    nomes |= {caminho.stem for caminho in PLUGINS.rglob("*.py")}
    return nomes


def test_a_aplicacao_so_usa_a_biblioteca_padrao():
    """Nada do que é distribuído pode importar de fora da stdlib (ADR-0002).

    É a regra que mantém o executável pequeno e a instalação sem compilação
    nativa. Sem um teste, ela dependia de alguém reparar no `import` novo na
    revisão — e uma dependência entra uma vez e fica.
    """
    locais = _nomes_locais()
    for pasta in (SRC, PLUGINS):
        for arquivo in pasta.rglob("*.py"):
            if "__pycache__" in arquivo.parts:
                continue
            for importado in importados_por(arquivo):
                raiz = importado.split(".")[0]
                assert raiz in sys.stdlib_module_names or raiz in locais, (
                    f"{arquivo.relative_to(RAIZ)} importa {importado}, "
                    "que não vem da biblioteca padrão nem da aplicação."
                )


def test_nao_ha_dependencias_de_execucao_declaradas():
    """`requirements.txt` vazio é a mesma regra, do lado da instalação."""
    linhas = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
    declaradas = [
        linha.strip()
        for linha in linhas
        if linha.strip() and not linha.strip().startswith("#")
    ]
    assert not declaradas, (
        f"requirements.txt declara dependências de execução: {declaradas}. "
        "Ver docs/architecture/ADR-0002."
    )


# ============================================================== PLUGINS


def test_nenhum_plugin_fura_o_contrato():
    """Tudo o que um plugin usa da aplicação chega pelo ContextoPlugin."""
    proibidos = {"banco_de_dados", "gui", "core.plugin_manager", "tarefas_servico"}
    for manifesto in PLUGINS.glob("*/plugin.json"):
        for arquivo in manifesto.parent.rglob("*.py"):
            importados = importados_por(arquivo)
            for proibido in proibidos:
                assert proibido not in importados, (
                    f"o plugin {manifesto.parent.name} importa {proibido}"
                )


def test_os_plugins_embutidos_abrem_nesta_versao():
    """Um plugin que acompanha a aplicação tem de ser compatível com ela.

    `compativel_com` estava testado com manifestos inventados; os manifestos
    reais não. Subir a versão da aplicação para lá do `max_app_version` de um
    plugin embutido entregava-o desativado a toda a gente, sem nada falhar aqui.
    """
    from core.plugin_api import ManifestoPlugin
    from core.version import APP_VERSION

    manifestos = sorted(PLUGINS.glob("*/plugin.json"))
    assert manifestos, "não há plugins embutidos para verificar."
    for caminho in manifestos:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto = ManifestoPlugin.de_dicionario(dados)
        assert manifesto.compativel_com(APP_VERSION), (
            f"o plugin {caminho.parent.name} exige "
            f"{manifesto.min_app_version}..{manifesto.max_app_version or 'sem limite'} "
            f"e a aplicação está em {APP_VERSION}."
        )


def test_os_plugins_nao_dependem_uns_dos_outros():
    nomes = {pasta.name for pasta in PLUGINS.iterdir() if pasta.is_dir()}
    for pasta in PLUGINS.iterdir():
        if not pasta.is_dir():
            continue
        for arquivo in pasta.rglob("*.py"):
            for importado in importados_por(arquivo):
                raiz = importado.split(".")[0]
                assert raiz not in nomes - {pasta.name}, (
                    f"o plugin {pasta.name} importa o plugin {raiz}"
                )


# ============================================== O ESPAÇO DE NOMES DE TOPO


def nomes_de_topo() -> set:
    """Os nomes que ``src/`` ocupa no espaço global de módulos."""
    return {p.stem for p in SRC.glob("*.py")} | {
        p.name for p in SRC.iterdir() if p.is_dir() and p.name != "__pycache__"
    }


@pytest.fixture(scope="module")
def nomes_declarados() -> dict:
    return json.loads((ARQUITETURA / "nomes-de-topo.json").read_text(encoding="utf-8"))


def test_todo_o_nome_de_topo_esta_declarado(nomes_declarados):
    """ADR-0005: um nome de topo é uma decisão, e as decisões escrevem-se.

    ``src/`` está no ``sys.path``: cada ficheiro e cada pasta ali ocupa um
    nome no espaço global de módulos, partilhado com tudo o que esteja
    instalado. Ninguém decidiu chamar ``workflow`` ao motor de regras — foi a
    palavra que apareceu — e meses depois o build parou, porque o PyInstaller
    traz um hook para o pacote ``workflow`` do PyPI.

    Este teste não sabe adivinhar colisões futuras. Faz a única coisa que
    ataca o problema na raiz: obriga a escolha do nome a ser uma decisão, no
    dia em que o módulo é criado.
    """
    declarados = set(nomes_declarados["nomes"])
    no_disco = nomes_de_topo()

    novos = no_disco - declarados
    assert not novos, (
        f"Nomes de topo por declarar: {sorted(novos)}. Acrescente-os a "
        f"docs/architecture/nomes-de-topo.json — e leia a regra que lá está "
        f"antes de escolher a palavra."
    )

    fantasmas = declarados - no_disco
    assert not fantasmas, (
        f"O inventário fala de nomes que já não existem: {sorted(fantasmas)}."
    )


def test_as_excecoes_de_nome_tem_todas_uma_razao(nomes_declarados):
    """Uma exceção sem razão escrita é só uma exceção."""
    for nome, razao in nomes_declarados["excecoes_de_nome"].items():
        if nome.startswith("_"):
            continue
        assert nome in nomes_de_topo(), f"o inventário mantém {nome!r}, que já não existe."
        assert len(razao) > 40, f"a razão para manter {nome!r} é curta demais."


# ============================================= OS PLUGINS QUE VÊM DENTRO


@pytest.fixture(scope="module")
def inventario_embutidos() -> dict:
    """Versão e impressão digital de cada plugin que acompanha a aplicação."""
    dados = json.loads(
        (ARQUITETURA / "plugins-embutidos.json").read_text(encoding="utf-8")
    )
    return dados["plugins"]


def impressoes_dos_embutidos() -> dict:
    """O que está hoje em ``plugins/available``, lido do disco."""
    import sys

    sys.path.insert(0, str(SRC))
    from core.plugin_package import impressao_da_pasta

    atual = {}
    for pasta in sorted(p for p in PLUGINS.iterdir() if p.is_dir()):
        manifesto = pasta / "plugin.json"
        if not manifesto.is_file():
            continue
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
        atual[dados["id"]] = {
            "versao": dados["version"],
            "impressao": impressao_da_pasta(pasta),
        }
    return atual


def test_mexer_num_plugin_embutido_obriga_a_subir_a_versao(inventario_embutidos):
    """ADR-0006: a versão é o que faz uma correção chegar a quem já a precisa.

    A semeadura compara versões. Um plugin embutido corrigido sem subir de
    versão fica corrigido no repositório e continua partido em todas as
    instalações que existem — foi assim que o Calendar passou a declarar as
    permissões de que precisa e, na máquina de quem já o tinha, continuou a
    falhar a ativação durante uma versão inteira.

    Este teste não sabe o que a alteração fez. Sabe que o conteúdo mudou, e
    que o número que decide se ela sai daqui ficou na mesma.
    """
    atual = impressoes_dos_embutidos()

    novos = set(atual) - set(inventario_embutidos)
    assert not novos, (
        f"Plugins embutidos por declarar: {sorted(novos)}. "
        f"Corra: python tools/inventario_plugins.py"
    )
    fantasmas = set(inventario_embutidos) - set(atual)
    assert not fantasmas, (
        f"O inventário fala de plugins que já não existem: {sorted(fantasmas)}."
    )

    for plugin_id, declarado in sorted(inventario_embutidos.items()):
        agora = atual[plugin_id]
        if agora["impressao"] == declarado["impressao"]:
            assert agora["versao"] == declarado["versao"], (
                f"{plugin_id}: a versão subiu para {agora['versao']} sem nada ter "
                f"mudado no conteúdo. Corra: python tools/inventario_plugins.py"
            )
            continue
        assert agora["versao"] != declarado["versao"], (
            f"{plugin_id}: o conteúdo mudou e a versão continua em "
            f"{agora['versao']}. Quem já tem este plugin instalado nunca vai "
            f"receber a alteração (ADR-0006). Suba a versão em "
            f"plugins/available/{plugin_id}/plugin.json e corra: "
            f"python tools/inventario_plugins.py"
        )


def test_cada_plugin_embutido_declara_o_acesso_que_usa():
    """Um plugin que usa as tarefas tem de as pedir no manifesto.

    O campo ``permissions`` é o contrato: sem ele o ``ContextoPlugin`` recusa
    o acesso em tempo de execução, e o plugin instala-se para falhar mais
    tarde. Ausente e vazio não são a mesma coisa — vazio é uma afirmação
    ("não acede a nada"), ausente é um esquecimento.
    """
    for pasta in sorted(p for p in PLUGINS.iterdir() if p.is_dir()):
        manifesto = pasta / "plugin.json"
        if not manifesto.is_file():
            continue
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
        assert "permissions" in dados, (
            f"{pasta.name}: o manifesto não diz a que acede. Declare "
            f'"permissions": [] se não acede a nada.'
        )


# ====================================================== DOCUMENTOS FIÉIS


@pytest.fixture(scope="module")
def classificacao() -> str:
    return (ARQUITETURA / "CLASSIFICACAO.md").read_text(encoding="utf-8")


def test_a_classificacao_cobre_tudo_o_que_existe(classificacao):
    """O documento de classificação não pode ficar para trás do código."""
    pacotes = [p.name for p in SRC.iterdir() if p.is_dir() and p.name != "__pycache__"]
    for pacote in pacotes:
        assert pacote in classificacao, f"{pacote}/ não está classificado."

    for pasta in PLUGINS.iterdir():
        if pasta.is_dir():
            assert pasta.name in classificacao, f"o plugin {pasta.name} não está classificado."


def test_nenhum_numero_de_adr_se_repete():
    """Dois ADRs com o mesmo número são duas decisões com a mesma morada.

    Aconteceu: dois ramos a andar em paralelo escolheram ambos o 0006 — um
    para a posse dos plugins, outro para as políticas de acesso. O git juntou
    os dois sem se queixar, porque os nomes dos ficheiros eram diferentes, e
    a partir daí "ver ADR-0006" no meio do código deixava de apontar para
    sítio nenhum em concreto.

    Escolher o número seguinte é a parte fácil. O que faltava era alguém
    reparar, e é isso que este teste faz.
    """
    import re
    from collections import defaultdict

    por_numero = defaultdict(list)
    for adr in sorted(ARQUITETURA.glob("ADR-*.md")):
        achado = re.match(r"ADR-(\d+)", adr.name)
        assert achado, f"{adr.name} não começa por ADR-<número>."
        por_numero[achado.group(1)].append(adr.name)

    repetidos = {n: f for n, f in por_numero.items() if len(f) > 1}
    assert not repetidos, (
        f"Números de ADR repetidos: {repetidos}. Renumere o mais recente — "
        f"o número já publicado é referido a partir do código."
    )


def test_o_numero_no_titulo_e_o_do_ficheiro():
    """Um ADR renumerado no nome e não no título mente duas vezes."""
    import re

    for adr in sorted(ARQUITETURA.glob("ADR-*.md")):
        numero = re.match(r"ADR-(\d+)", adr.name).group(1)
        primeira = adr.read_text(encoding="utf-8").splitlines()[0]
        assert primeira.startswith(f"# ADR-{numero}"), (
            f"{adr.name} começa por {primeira!r}, que não é o seu número."
        )


def test_cada_adr_tem_decisao_e_consequencias():
    adrs = sorted(ARQUITETURA.glob("ADR-*.md"))
    assert len(adrs) >= 4, "as decisões de arquitetura vivem em ADRs."
    for adr in adrs:
        texto = adr.read_text(encoding="utf-8")
        assert "## Decisão" in texto, f"{adr.name} não diz o que foi decidido."
        assert "## Consequências" in texto or "## Consequência" in texto, (
            f"{adr.name} não diz o que isso custa."
        )
