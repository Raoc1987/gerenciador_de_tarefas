"""Testes do empacotamento e do instalador.

Não constroem o executável nem o ``Setup.exe`` — isso é feito por
``tools/build.py`` e ``tools/build_installer.py``. O que estes testes impedem
é a **divergência silenciosa**: a receita do PyInstaller e o script do Inno
Setup ficarem a falar de arquivos, nomes ou versões que já não existem.
"""

import re

import pytest

from core.version import APP_ID, APP_NAME, APP_PUBLISHER, APP_URL, APP_VERSION


@pytest.fixture
def spec(raiz_projeto):
    """Conteúdo do ``GerenciadorDeTarefas.spec``."""
    caminho = raiz_projeto / "GerenciadorDeTarefas.spec"
    assert caminho.is_file(), "a receita do PyInstaller deve existir"
    return caminho.read_text(encoding="utf-8")


@pytest.fixture
def iss(raiz_projeto):
    """Conteúdo do ``installer/setup.iss``."""
    caminho = raiz_projeto / "installer" / "setup.iss"
    assert caminho.is_file(), "o script do Inno Setup deve existir"
    return caminho.read_text(encoding="utf-8")


def definicao_iss(texto: str, nome: str) -> str:
    """Extrai o valor de um ``#define`` do script do Inno Setup."""
    achado = re.search(rf'#define\s+{nome}\s+"([^"]*)"', texto)
    assert achado, f"#define {nome} não encontrado em setup.iss"
    return achado.group(1)


def diretiva_iss(texto: str, nome: str) -> str:
    """Extrai o valor de uma diretiva ``Nome=valor`` da secção [Setup]."""
    achado = re.search(rf"^{nome}=(.+)$", texto, re.MULTILINE)
    assert achado, f"diretiva {nome} não encontrada em setup.iss"
    return achado.group(1).strip()


# ----------------------------------------------------------------- recursos


def test_icone_existe_e_tem_varios_tamanhos(raiz_projeto):
    icone = raiz_projeto / "assets" / "icon.ico"
    assert icone.is_file(), "assets/icon.ico deve estar versionado"
    assert icone.stat().st_size > 1000
    # Cabeçalho ICO: reservado=0, tipo=1, número de imagens.
    cabecalho = icone.read_bytes()[:6]
    assert cabecalho[:4] == b"\x00\x00\x01\x00"
    quantidade = int.from_bytes(cabecalho[4:6], "little")
    assert quantidade >= 4, "o ícone deve trazer vários tamanhos"


# ------------------------------------------------------------- PyInstaller


def test_spec_empacota_os_recursos_necessarios(spec):
    assert "assets/idiomas" in spec
    assert "plugins/available" in spec
    assert "icon.ico" in spec


def test_spec_nao_repete_nome_nem_versao(spec):
    """Nome e versão vêm de core/version.py, não estão escritos à mão."""
    assert "from core.version import" in spec
    assert "name=APP_ID" in spec
    assert f'"{APP_VERSION}"' not in spec


def test_spec_declara_a_superficie_de_sdk_dos_plugins(spec):
    """Os módulos que um plugin pode importar têm de ser empacotados."""
    for modulo in ("calendar_widget", "utils", "language_manager", "core.plugin_api"):
        assert f'"{modulo}"' in spec, f"{modulo} deve estar em hiddenimports"


def test_spec_e_aplicacao_grafica(spec):
    assert "console=False" in spec


def test_modulos_do_sdk_existem_mesmo(spec, raiz_projeto):
    """Evita que hiddenimports aponte para módulos já removidos."""
    bloco = spec.split("hiddenimports = [", 1)[1].split("]", 1)[0]
    declarados = re.findall(r'"([a-z_][a-z_.]*)"', bloco)
    do_projeto = [m for m in declarados if not m.startswith("tkinter")]
    for modulo in do_projeto:
        caminho = raiz_projeto / "src" / (modulo.replace(".", "/") + ".py")
        if caminho.exists():
            continue
        # senão, tem de ser um módulo da biblioteca padrão importável
        __import__(modulo)


# -------------------------------------------------------------- Inno Setup


def test_iss_usa_os_mesmos_nome_id_e_editor(iss):
    assert definicao_iss(iss, "AppName") == APP_NAME
    assert definicao_iss(iss, "AppId") == APP_ID
    assert definicao_iss(iss, "AppPublisher") == APP_PUBLISHER
    assert definicao_iss(iss, "AppUrl") == APP_URL


def test_iss_tem_a_versao_atual_por_omissao(iss):
    """O valor por omissão é o de core/version.py (o build passa /DAppVersion)."""
    assert definicao_iss(iss, "AppVersion") == APP_VERSION


def test_iss_aponta_para_a_pasta_gerada_pelo_pyinstaller(iss):
    assert definicao_iss(iss, "SourceDir").endswith(f"dist\\{APP_ID}")


def test_nome_do_instalador(iss):
    assert diretiva_iss(iss, "OutputBaseFilename") == "{#AppId}-Setup"


def test_instalador_usa_o_icone_da_aplicacao(iss, raiz_projeto):
    # O caminho está em notação Windows; normalizar para o teste correr em Linux.
    caminho = diretiva_iss(iss, "SetupIconFile").replace("\\", "/")
    assert (raiz_projeto / "installer" / caminho).resolve().is_file()


def test_instalador_cria_atalhos_e_desinstalador(iss):
    assert "[Icons]" in iss
    assert "{autoprograms}" in iss, "deve criar entrada no Menu Iniciar"
    assert "{autodesktop}" in iss, "deve poder criar atalho no ambiente de trabalho"
    assert "UninstallDisplayIcon=" in iss


def test_instalador_reconhece_a_instalacao_existente(iss):
    """AppId estável + UsePreviousAppDir são o que torna a atualização possível."""
    assert re.search(r"^AppId=\{\{[0-9A-F-]{36}\}", iss, re.MULTILINE | re.IGNORECASE)
    assert diretiva_iss(iss, "UsePreviousAppDir") == "yes"
    assert diretiva_iss(iss, "CloseApplications") == "yes"


def test_instalador_nao_exige_administrador(iss):
    assert diretiva_iss(iss, "PrivilegesRequired") == "lowest"
    assert diretiva_iss(iss, "PrivilegesRequiredOverridesAllowed") == "dialog"


def test_instalador_nao_escreve_dados_do_utilizador(iss):
    """A aplicação vai para {app}; os dados do utilizador não são instalados."""
    secao_files = iss.split("[Files]", 1)[1].split("[Icons]", 1)[0]
    assert "{userappdata}" not in secao_files
    assert "tarefas.db" not in iss
    assert "DestDir: \"{app}\"" in secao_files


def test_desinstalacao_nao_apaga_dados_em_silencio(iss):
    """A pasta de dados só é apagada depois de uma confirmação explícita."""
    assert "CurUninstallStepChanged" in iss
    codigo = iss.split("[Code]", 1)[1]
    assert "MB_YESNO" in codigo, "tem de perguntar ao utilizador"
    assert "MB_DEFBUTTON2" in codigo, "a opção por omissão deve ser manter os dados"
    assert "DelTree" in codigo

    apagados = iss.split("[UninstallDelete]", 1)[1].split("[Code]", 1)[0]
    assert "{userappdata}" not in apagados


def test_desinstalacao_usa_o_mesmo_caminho_de_dados_que_a_aplicacao(iss):
    """O caminho no instalador tem de coincidir com core/paths.py no Windows."""
    assert "{userappdata}\\{#AppId}" in iss


def test_iss_suporta_os_tres_idiomas_da_aplicacao(iss):
    secao = iss.split("[Languages]", 1)[1].split("[Tasks]", 1)[0]
    assert "brazilianportuguese" in secao
    assert "english" in secao
    assert "spanish" in secao


def test_desinstalacao_silenciosa_mantem_os_dados_por_omissao(iss):
    """Sem /REMOVEDATA=yes, uma desinstalação automatizada preserva os dados."""
    codigo = iss.split("[Code]", 1)[1]
    assert "{param:REMOVEDATA|no}" in codigo, "o valor por omissão tem de ser 'no'"
    assert "RemocaoDeDadosPedidaNaLinhaDeComandos" in codigo


def test_remocao_de_dados_so_com_pedido_explicito(iss):
    """DelTree só acontece por parâmetro explícito ou por resposta 'sim'."""
    codigo = iss.split("[Code]", 1)[1]
    ocorrencias = codigo.count("DelTree")
    assert ocorrencias == 2, "só os dois caminhos explícitos podem apagar dados"
    posicao_param = codigo.index("RemocaoDeDadosPedidaNaLinhaDeComandos()")
    posicao_pergunta = codigo.index("MB_YESNO")
    primeiro, segundo = [m.start() for m in re.finditer("DelTree", codigo)]
    assert posicao_param < primeiro < posicao_pergunta < segundo


# ==================================== NOMES QUE COLIDEM COM O EMPACOTADOR


def test_nenhum_modulo_da_aplicacao_colide_com_um_hook_do_pyinstaller():
    """Um nome de topo generico colide com um pacote do PyPI, e o build parte.

    Aconteceu: `src/workflow/` bateu com o pacote `workflow` do PyPI, para o
    qual o PyInstaller traz um hook. O hook tenta importar *esse* pacote,
    falha, e o executavel deixa de ser construido -- mas os 1045 testes
    continuavam verdes, porque o problema so existe ao empacotar.

    Este teste tira o erro da CI e traz-no para ca.
    """
    from pathlib import Path

    import pytest

    contrib = pytest.importorskip(
        "_pyinstaller_hooks_contrib", reason="PyInstaller nao instalado"
    )
    stdhooks = Path(contrib.__file__).parent / "stdhooks"
    if not stdhooks.is_dir():  # pragma: no cover - instalacao diferente
        pytest.skip("hooks do PyInstaller nao encontrados")

    raiz = Path(__file__).resolve().parent.parent / "src"
    nossos = {p.stem for p in raiz.glob("*.py")} | {
        p.name for p in raiz.iterdir() if p.is_dir() and p.name != "__pycache__"
    }

    colisoes = sorted(
        nome for nome in nossos if (stdhooks / f"hook-{nome}.py").exists()
    )
    assert not colisoes, (
        f"Estes modulos tem o nome de um pacote do PyPI com hook proprio: "
        f"{colisoes}. O PyInstaller vai tentar aplicar-lhes o hook desse "
        f"pacote e o build falha. Escolha outro nome."
    )
