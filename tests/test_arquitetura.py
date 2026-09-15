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
    "widgets",
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
            assert raiz not in {"analytics", "reporting"}, (
                f"core/{arquivo.name} importa {importado}"
            )


@pytest.mark.parametrize("pacote", ["analytics", "reporting", "regras"])
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
    for arquivo in (SRC / "analytics").rglob("*.py"):
        if arquivo.name == "fontes.py":
            continue
        assert "database" not in importados_por(arquivo), (
            f"analytics/{arquivo.name} devia pedir os dados a fontes.py"
        )


def test_o_motor_de_automacao_nao_conhece_dominios():
    """Se o motor souber o que é uma tarefa, deixou de ser um motor.

    O que ele executa são ações que outros registaram. Conhecer um domínio
    seria o primeiro passo para se tornar o sítio onde todos se encontram —
    um monólito com outro nome.
    """
    dominios = {"tarefas_servico", "analytics", "reporting", "organizacao"}
    for arquivo in (SRC / "regras").rglob("*.py"):
        for importado in importados_por(arquivo):
            raiz = importado.split(".")[0]
            assert raiz not in dominios, f"regras/{arquivo.name} importa {importado}"
            # O armazenamento é infraestrutura, não um domínio — a auditoria e
            # a organização também o usam. Mas só o repositório: o motor que
            # soubesse ler o banco começaria a lê-lo para decidir.
            if arquivo.name != "repositorio.py":
                assert raiz != "database", f"regras/{arquivo.name} importa database"


#: O que só :mod:`tarefas_servico` pode fazer ao armazenamento.
FUNCOES_DE_TAREFAS = {
    "adicionar_tarefa", "buscar_tarefas", "buscar_tarefas_completas",
    "tarefas_por_data", "obter_tarefa", "concluir_tarefa", "remover_tarefa",
    "dono_de", "unidade_de",
}

#: Quem pode mexer nas tarefas: a política, o próprio armazenamento, e o
#: arranque da aplicação (que só cria o esquema).
PODEM_TOCAR_EM_TAREFAS = {"tarefas_servico.py", "database.py", "main.py"}


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
                assert origem != "database", (
                    f"{arquivo.name} chama database.{no.attr}; use tarefas_servico."
                )
            elif isinstance(no, ast.ImportFrom) and no.module == "database":
                trazidos = {alias.name for alias in no.names} & FUNCOES_DE_TAREFAS
                assert not trazidos, (
                    f"{arquivo.name} importa {sorted(trazidos)} de database."
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
        "import database",
        "def ler():",
        "    return database.buscar_tarefas()",
    ]
    pelo_sql = [
        "import database",
        "def ler():",
        "    with database.conectar() as c:",
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
    proibidos = {"database", "gui", "core.plugin_manager", "tarefas_servico"}
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


def test_cada_adr_tem_decisao_e_consequencias():
    adrs = sorted(ARQUITETURA.glob("ADR-*.md"))
    assert len(adrs) >= 4, "as decisões de arquitetura vivem em ADRs."
    for adr in adrs:
        texto = adr.read_text(encoding="utf-8")
        assert "## Decisão" in texto, f"{adr.name} não diz o que foi decidido."
        assert "## Consequências" in texto or "## Consequência" in texto, (
            f"{adr.name} não diz o que isso custa."
        )
