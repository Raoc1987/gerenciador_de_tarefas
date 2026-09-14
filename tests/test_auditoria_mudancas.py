"""A trilha passa a dizer de quê para quê.

Registar que alguém mudou o papel de uma conta responde metade da pergunta.
Numa auditoria a sério, a outra metade — de que papel para que papel — é a que
interessa.

E há um limite que estes testes guardam com mais cuidado do que a
funcionalidade em si: a trilha **não** é sítio para o conteúdo do trabalho.
"""

import json

import pytest

import database as db
from core import (
    auditoria,
    eventos,
    funcionalidades,
    organizacao,
    permissoes,
    utilizadores,
)
from core.auditoria import RegistoAuditoria
from core.organizacao import TipoUnidade

SENHA = "Uma-Senha-Longa-123"


@pytest.fixture(autouse=True)
def trilha():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    auditoria.ativar()


def ultimo(evento: str) -> RegistoAuditoria:
    registos = [r for r in auditoria.consultar() if r.evento == evento]
    assert registos, f"não houve registo de {evento}"
    return registos[0]


# ======================================================= O QUE FICA GUARDADO


def test_mudar_o_papel_diz_de_qual_para_qual():
    utilizadores.criar("bruno", SENHA, papel="colaborador")
    utilizadores.definir_papel("bruno", "gestor")

    registo = ultimo(eventos.UTILIZADOR_ALTERADO)
    assert registo.antes == {"papel": "colaborador"}
    assert registo.depois == {"papel": "gestor"}
    assert registo.mudancas() == [("papel", "colaborador", "gestor")]


def test_mudar_de_unidade_diz_de_onde_para_onde():
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    equipa = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, empresa.id)
    utilizadores.criar("bruno", SENHA, papel="colaborador")

    utilizadores.definir_unidade("bruno", empresa.id)
    utilizadores.definir_unidade("bruno", equipa.id)

    registo = ultimo(eventos.UTILIZADOR_ALTERADO)
    assert registo.antes == {"unidade": empresa.id}
    assert registo.depois == {"unidade": equipa.id}


def test_renomear_uma_unidade():
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    organizacao.renomear(empresa.id, "Acme Lda")

    assert ultimo(eventos.UNIDADE_ALTERADA).mudancas() == [
        ("nome", "Acme", "Acme Lda")
    ]


def test_mover_uma_unidade_diz_de_que_pai_para_que_pai():
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    outra = organizacao.criar("Holding", TipoUnidade.EMPRESA)
    equipa = organizacao.criar("Engenharia", TipoUnidade.DEPARTAMENTO, empresa.id)

    organizacao.mover(equipa.id, outra.id)

    assert ultimo(eventos.UNIDADE_ALTERADA).mudancas() == [
        ("pai_id", empresa.id, outra.id)
    ]


def test_desligar_uma_funcionalidade():
    funcionalidades.definir("painel", False)

    assert ultimo(eventos.FUNCIONALIDADE_ALTERADA).mudancas() == [
        ("ligada", True, False)
    ]


def test_o_resumo_le_se_como_uma_frase():
    utilizadores.criar("bruno", SENHA, papel="colaborador")
    utilizadores.definir_papel("bruno", "gestor")

    assert ultimo(eventos.UTILIZADOR_ALTERADO).resumo_da_mudanca() == (
        "papel: colaborador -> gestor"
    )


def test_os_booleanos_leem_se_em_portugues():
    funcionalidades.definir("painel", False)
    assert ultimo(eventos.FUNCIONALIDADE_ALTERADA).resumo_da_mudanca() == (
        "ligada: sim -> não"
    )


def test_um_valor_em_falta_nao_aparece_como_None():
    """``None`` num relatório é ruído; um travessão diz "não havia"."""
    empresa = organizacao.criar("Acme", TipoUnidade.EMPRESA)
    equipa = organizacao.criar("Eng", TipoUnidade.DEPARTAMENTO, empresa.id)
    utilizadores.criar("bruno", SENHA, papel="colaborador")
    utilizadores.definir_unidade("bruno", equipa.id)

    assert "—" in ultimo(eventos.UTILIZADOR_ALTERADO).resumo_da_mudanca()


# ============================================ O QUE NÃO PODE FICAR GUARDADO


def test_o_conteudo_de_uma_tarefa_nunca_entra_na_trilha():
    """O limite que este mecanismo não pode atravessar.

    Que a tarefa 12 foi concluída é um facto auditável. O que ela dizia não é
    assunto da trilha — uma auditoria que guarda o trabalho todo é a maior
    fuga de dados da aplicação.
    """
    tarefa = db.adicionar_tarefa("Segredo comercial importante", "2030-01-01")
    db.concluir_tarefa(tarefa)

    guardado = json.dumps(
        [(r.detalhe, r.antes, r.depois) for r in auditoria.consultar()],
        ensure_ascii=False,
    )
    assert "Segredo comercial" not in guardado


def test_um_campo_fora_da_lista_e_descartado():
    """Não basta quem publica mandar: o campo tem de constar da lista."""
    eventos.publicar(
        eventos.UTILIZADOR_ALTERADO,
        origem="teste",
        id="bruno",
        antes={"papel": "colaborador", "senha_hash": "muito-secreto"},
        depois={"papel": "gestor", "senha_hash": "outro-segredo"},
    )

    registo = ultimo(eventos.UTILIZADOR_ALTERADO)
    assert registo.antes == {"papel": "colaborador"}
    assert "senha_hash" not in registo.depois


def test_um_evento_sem_lista_nao_guarda_nada():
    """Só os eventos que declaram campos é que guardam valores."""
    eventos.publicar(
        eventos.TAREFA_CRIADA,
        origem="teste",
        id=1,
        antes={"descricao": "antiga"},
        depois={"descricao": "nova"},
    )

    registo = ultimo(eventos.TAREFA_CRIADA)
    assert registo.antes == {} and registo.depois == {}


def test_um_antes_que_nao_e_objeto_e_ignorado():
    """Um publicador distraído não pode partir a trilha."""
    eventos.publicar(
        eventos.FUNCIONALIDADE_ALTERADA,
        origem="teste",
        id="painel",
        antes="isto devia ser um objeto",
        depois={"ligada": False},
    )

    registo = ultimo(eventos.FUNCIONALIDADE_ALTERADA)
    assert registo.antes == {}
    assert registo.depois == {"ligada": False}


# ================================================================ LEITURA


def test_so_o_que_mudou_aparece():
    """Repetir um valor igual dos dois lados obriga a comparar tudo à vista."""
    registo = RegistoAuditoria(
        1,
        "2026-01-01",
        "x",
        "ana",
        "",
        "",
        "teste",
        antes={"papel": "gestor", "ativo": True},
        depois={"papel": "gestor", "ativo": False},
    )
    assert registo.mudancas() == [("ativo", True, False)]


def test_um_json_ilegivel_nao_impede_ler_a_trilha():
    """Uma trilha que não abre por causa de uma linha má é pior que a linha."""
    db.criar_tabela()
    with db.conectar() as conexao:
        conexao.execute(
            "INSERT INTO auditoria (momento, evento, utilizador, alvo, detalhe,"
            " origem, antes, depois) VALUES"
            " ('2026-01-01', 'utilizador.alterado', 'ana', 'x', '', 'teste',"
            " 'nao e json', '[1, 2]')"
        )

    registo = ultimo(eventos.UTILIZADOR_ALTERADO)
    assert registo.antes == {}
    assert registo.depois == {}, "uma lista também não serve"


def test_as_linhas_antigas_continuam_a_ler_se():
    """A migração é aditiva: quem já tinha trilha não a perde."""
    db.criar_tabela()
    with db.conectar() as conexao:
        conexao.execute(
            "INSERT INTO auditoria (momento, evento, utilizador, alvo, detalhe, origem)"
            " VALUES ('2026-01-01', 'utilizador.alterado', 'ana', 'x', 'd', 'teste')"
        )

    registo = ultimo(eventos.UTILIZADOR_ALTERADO)
    assert registo.detalhe == "d"
    assert registo.mudancas() == []


def test_a_janela_mostra_a_mudanca():
    from conftest import TKINTER_DISPONIVEL, criar_janela_com_retentativa

    if not TKINTER_DISPONIVEL:
        pytest.skip("ambiente sem interface gráfica")

    tk = pytest.importorskip("tkinter")
    from auditoria_ui import JanelaAuditoria

    utilizadores.criar("bruno", SENHA, papel="colaborador")
    utilizadores.definir_papel("bruno", "gestor")

    raiz = criar_janela_com_retentativa(tk.Tk)
    raiz.withdraw()
    tela = JanelaAuditoria(raiz)
    try:
        textos = [
            " ".join(str(v) for v in tela.tabela.item(linha, "values"))
            for linha in tela.tabela.get_children()
        ]
        assert any("colaborador -> gestor" in t for t in textos)
    finally:
        tela.destroy()
        raiz.destroy()
