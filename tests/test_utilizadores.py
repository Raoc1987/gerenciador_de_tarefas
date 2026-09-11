"""Testes de palavras-passe, contas e autenticação."""

from datetime import datetime, timedelta

import pytest

from core import eventos, permissoes, seguranca, utilizadores
from core.permissoes import Permissao
from core.seguranca import SenhaInvalidaError
from core.utilizadores import (
    MotivoFalha,
    NomeIndisponivelError,
    NomeInvalidoError,
    UltimoAdministradorError,
)

SENHA = "plataforma2026"


@pytest.fixture
def admin():
    """Uma conta de administração já criada."""
    return utilizadores.criar("rodrigo", SENHA, "administrador", "Rodrigo Costa")


# =============================================================== SEGURANÇA


def test_hash_nao_contem_a_senha():
    guardado = seguranca.gerar_hash(SENHA)
    assert SENHA not in guardado
    assert guardado.startswith("pbkdf2_sha256$")


def test_o_mesmo_texto_da_hashes_diferentes():
    """Sal próprio por registo: duas contas com a mesma senha não coincidem."""
    assert seguranca.gerar_hash(SENHA) != seguranca.gerar_hash(SENHA)


def test_verificar_aceita_a_senha_certa_e_recusa_as_outras():
    guardado = seguranca.gerar_hash(SENHA)
    assert seguranca.verificar(SENHA, guardado) is True
    assert seguranca.verificar("outra coisa", guardado) is False
    assert seguranca.verificar("", guardado) is False


def test_verificar_com_registo_corrompido():
    for lixo in ("", "sem-dolares", "pbkdf2_sha256$x$y", "outro$1$a$b", None):
        assert seguranca.verificar(SENHA, lixo) is False


def test_senha_normalizada_por_unicode():
    """A mesma palavra escrita com acentos compostos tem de funcionar."""
    composta = "palávra-passe"          # á pré-composto
    decomposta = "palávra-passe"        # a + acento
    guardado = seguranca.gerar_hash(composta)
    assert seguranca.verificar(decomposta, guardado) is True


def test_rehash_quando_o_custo_sobe():
    antigo = seguranca.gerar_hash(SENHA, iteracoes=1000)
    assert seguranca.precisa_de_rehash(antigo) is True
    assert seguranca.precisa_de_rehash(seguranca.gerar_hash(SENHA)) is False


@pytest.mark.parametrize(
    "senha,problema",
    [
        ("", "senha_vazia"),
        ("curta1", "senha_curta"),
        ("12345678", "senha_so_digitos"),
        ("password", "senha_trivial"),
        ("  espacos  ", "senha_com_espacos_nas_pontas"),
        ("aaaaaaaaaa", "senha_repetitiva"),
        ("x" * 200, "senha_longa"),
    ],
)
def test_senhas_recusadas(senha, problema):
    assert problema in seguranca.problemas_da_senha(senha)


def test_senha_nao_pode_conter_o_utilizador():
    assert "senha_contem_utilizador" in seguranca.problemas_da_senha(
        "rodrigo-tem-uma-senha", "rodrigo"
    )


def test_senha_aceitavel():
    assert seguranca.problemas_da_senha(SENHA, "rodrigo") == []


def test_validar_senha_levanta_com_a_lista():
    with pytest.raises(SenhaInvalidaError) as erro:
        seguranca.validar_senha("123")
    assert "senha_curta" in erro.value.problemas
    assert erro.value.chave_mensagem == "senha_invalida"


# ================================================================= CONTAS


def test_primeiro_arranque_nao_tem_contas():
    assert utilizadores.existe_algum() is False


def test_criar_conta(admin):
    assert utilizadores.existe_algum() is True
    assert admin.nome_utilizador == "rodrigo"
    assert admin.apresentacao == "Rodrigo Costa"
    assert admin.ativo is True
    assert admin.papel.pode(Permissao.SISTEMA_ADMIN)


def test_a_senha_nunca_fica_em_claro_no_banco(admin):
    import database

    with database.conectar() as conexao:
        guardado = conexao.execute("SELECT senha_hash FROM utilizadores").fetchone()[0]
    assert SENHA not in guardado
    assert seguranca.verificar(SENHA, guardado)


def test_nome_de_utilizador_e_unico_sem_distinguir_maiusculas(admin):
    with pytest.raises(NomeIndisponivelError):
        utilizadores.criar("RODRIGO", SENHA, "colaborador")


@pytest.mark.parametrize("nome", ["ab", "x" * 40, "com espaço", "com@arroba", ""])
def test_nomes_de_utilizador_invalidos(nome):
    with pytest.raises(NomeInvalidoError):
        utilizadores.criar(nome, SENHA)


def test_criar_com_senha_fraca_nao_cria_conta():
    with pytest.raises(SenhaInvalidaError):
        utilizadores.criar("ana", "123")
    assert utilizadores.obter("ana") is None


def test_papel_desconhecido_cai_no_padrao():
    conta = utilizadores.criar("ana", SENHA, "papel_inexistente")
    assert conta.papel_nome == permissoes.PAPEL_PADRAO


def test_listar_e_obter(admin):
    utilizadores.criar("ana", SENHA, "colaborador")
    assert [c.nome_utilizador for c in utilizadores.listar()] == ["ana", "rodrigo"]
    assert utilizadores.obter("ANA").nome_utilizador == "ana"
    assert utilizadores.obter("ninguem") is None


# =========================================================== AUTENTICAÇÃO


def test_autenticar_com_sucesso(admin):
    resultado = utilizadores.autenticar("rodrigo", SENHA)
    assert resultado.sucesso
    assert resultado.utilizador.nome_utilizador == "rodrigo"
    assert resultado.utilizador.ultimo_acesso is not None


def test_autenticar_ignora_maiusculas_no_nome(admin):
    assert utilizadores.autenticar("Rodrigo", SENHA).sucesso


def test_senha_errada(admin):
    resultado = utilizadores.autenticar("rodrigo", "errada12345")
    assert not resultado.sucesso
    assert resultado.motivo == MotivoFalha.CREDENCIAIS


def test_utilizador_inexistente_nao_se_distingue_de_senha_errada(admin):
    """Dizer "esse utilizador não existe" entregaria metade da resposta."""
    inexistente = utilizadores.autenticar("ninguem", "seja_o_que_for")
    senha_errada = utilizadores.autenticar("rodrigo", "errada12345")
    assert inexistente.motivo == senha_errada.motivo == MotivoFalha.CREDENCIAIS


def test_conta_desativada_nao_entra(admin):
    utilizadores.criar("ana", SENHA, "colaborador")
    utilizadores.definir_ativo("ana", False)
    resultado = utilizadores.autenticar("ana", SENHA)
    assert not resultado.sucesso
    assert resultado.motivo == MotivoFalha.INATIVO


def test_bloqueio_depois_de_varias_falhas(admin):
    for _ in range(utilizadores.TENTATIVAS_ATE_BLOQUEAR):
        utilizadores.autenticar("rodrigo", "errada12345")

    # Mesmo com a senha certa, a conta está bloqueada.
    resultado = utilizadores.autenticar("rodrigo", SENHA)
    assert resultado.motivo == MotivoFalha.BLOQUEADO
    assert 0 < resultado.minutos_restantes <= utilizadores.MINUTOS_DE_BLOQUEIO


def test_entrada_com_sucesso_limpa_as_tentativas(admin):
    utilizadores.autenticar("rodrigo", "errada12345")
    utilizadores.autenticar("rodrigo", "errada12345")
    assert utilizadores.obter("rodrigo").tentativas_falhadas == 2

    utilizadores.autenticar("rodrigo", SENHA)
    assert utilizadores.obter("rodrigo").tentativas_falhadas == 0


def test_bloqueio_expira(admin):
    import database

    for _ in range(utilizadores.TENTATIVAS_ATE_BLOQUEAR):
        utilizadores.autenticar("rodrigo", "errada12345")

    passado = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    with database.conectar() as conexao:
        conexao.execute("UPDATE utilizadores SET bloqueado_ate = ?", (passado,))

    assert utilizadores.autenticar("rodrigo", SENHA).sucesso


def test_o_custo_da_derivacao_sobe_na_entrada(admin, monkeypatch):
    """Uma conta antiga é regravada com o custo atual quando o dono entra."""
    import database

    fraco = seguranca.gerar_hash(SENHA, iteracoes=1000)
    with database.conectar() as conexao:
        conexao.execute("UPDATE utilizadores SET senha_hash = ?", (fraco,))

    assert utilizadores.autenticar("rodrigo", SENHA).sucesso
    with database.conectar() as conexao:
        guardado = conexao.execute("SELECT senha_hash FROM utilizadores").fetchone()[0]
    assert seguranca.precisa_de_rehash(guardado) is False


def test_alterar_senha(admin):
    assert utilizadores.alterar_senha("rodrigo", "nova-senha-2026") is True
    assert not utilizadores.autenticar("rodrigo", SENHA).sucesso
    assert utilizadores.autenticar("rodrigo", "nova-senha-2026").sucesso


def test_alterar_senha_desbloqueia(admin):
    for _ in range(utilizadores.TENTATIVAS_ATE_BLOQUEAR):
        utilizadores.autenticar("rodrigo", "errada12345")
    utilizadores.alterar_senha("rodrigo", "nova-senha-2026")
    assert utilizadores.autenticar("rodrigo", "nova-senha-2026").sucesso


# =============================================== PROTEÇÃO DO ADMINISTRADOR


def test_nao_se_remove_o_ultimo_administrador(admin):
    with pytest.raises(UltimoAdministradorError):
        utilizadores.remover("rodrigo")
    assert utilizadores.obter("rodrigo") is not None


def test_nao_se_desativa_o_ultimo_administrador(admin):
    with pytest.raises(UltimoAdministradorError):
        utilizadores.definir_ativo("rodrigo", False)


def test_nao_se_despromove_o_ultimo_administrador(admin):
    with pytest.raises(UltimoAdministradorError):
        utilizadores.definir_papel("rodrigo", "colaborador")


def test_com_dois_administradores_ja_se_pode_remover_um(admin):
    utilizadores.criar("ana", SENHA, "administrador")
    assert utilizadores.remover("rodrigo") is True
    assert [c.nome_utilizador for c in utilizadores.administradores_ativos()] == ["ana"]


def test_administrador_inativo_nao_conta(admin):
    utilizadores.criar("ana", SENHA, "administrador")
    utilizadores.definir_ativo("ana", False)
    with pytest.raises(UltimoAdministradorError):
        utilizadores.remover("rodrigo")


# ==================================================== SESSÃO E PERMISSÕES


def test_iniciar_sessao_aplica_o_papel(admin):
    utilizadores.criar("ana", SENHA, "colaborador")
    utilizadores.iniciar_sessao(utilizadores.obter("ana"))

    assert permissoes.sessao().utilizador == "ana"
    assert permissoes.pode(Permissao.TAREFAS_ESCREVER)
    assert not permissoes.pode(Permissao.PLUGINS_GERIR)


def test_terminar_sessao_publica_evento(admin):
    recebidos = []
    eventos.subscrever(eventos.SESSAO_TERMINADA, recebidos.append)
    utilizadores.iniciar_sessao(admin)
    utilizadores.terminar_sessao()
    assert [e.dados["id"] for e in recebidos] == ["rodrigo"]


# ================================================================ EVENTOS


def test_eventos_de_sessao_e_conta(admin):
    recebidos = []
    eventos.subscrever("sessao.*", recebidos.append)
    eventos.subscrever("utilizador.*", recebidos.append)

    utilizadores.autenticar("rodrigo", SENHA)
    utilizadores.autenticar("rodrigo", "errada12345")
    utilizadores.criar("ana", SENHA, "colaborador")
    utilizadores.definir_papel("ana", "gestor")
    utilizadores.remover("ana")

    assert [e.nome for e in recebidos] == [
        eventos.SESSAO_INICIADA,
        eventos.SESSAO_FALHADA,
        eventos.UTILIZADOR_CRIADO,
        eventos.UTILIZADOR_ALTERADO,
        eventos.UTILIZADOR_REMOVIDO,
    ]


def test_eventos_nunca_levam_a_senha(admin):
    recebidos = []
    eventos.subscrever("*", recebidos.append)

    utilizadores.criar("ana", SENHA, "colaborador")
    utilizadores.alterar_senha("ana", "outra-senha-2026")
    utilizadores.autenticar("ana", "outra-senha-2026")

    for evento in recebidos:
        conteudo = str(evento.dados)
        assert SENHA not in conteudo
        assert "outra-senha-2026" not in conteudo


def test_auditoria_regista_entradas_e_falhas(admin):
    from core import auditoria

    auditoria.ativar()
    utilizadores.autenticar("rodrigo", SENHA)
    utilizadores.autenticar("rodrigo", "errada12345")

    registados = [r.evento for r in auditoria.consultar()]
    assert eventos.SESSAO_INICIADA in registados
    assert eventos.SESSAO_FALHADA in registados

    trilha = auditoria.consultar()
    assert all(SENHA not in r.detalhe for r in trilha)
