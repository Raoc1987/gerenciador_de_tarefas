"""O catálogo de práticas partilhadas (``docs/conhecimento/catalogo.json``) e a
ferramenta que o analisa (``tools/conhecimento.py``).

Um registo que ninguém valida apodrece: o grafo de conhecimento do ALKMIA está
em JSON inválido desde maio (``docs/METODO.md``, R7). Este teste é o que impede
o mesmo aqui, e prova que os parâmetros de decisão têm consequência.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("conhecimento", RAIZ / "tools" / "conhecimento.py")
k = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(k)


def test_o_catalogo_do_repositorio_e_valido():
    assert k.problemas(k.carregar()) == []


def test_cada_skill_agente_e_hook_deste_repositorio_esta_no_catalogo():
    """Uma skill nova sem entrada é uma decisão que ninguém registou."""
    assert k.nao_catalogados(k.carregar()) == []


def _base() -> dict:
    return {
        "atualizado": "2026-10-08",
        "entradas": [{
            "id": "x", "titulo": "X", "tipo": "regra", "origem": "alkmia", "fontes": ["alkmia:docs/BIBLIA.md#M1"],
            "destino": "docs/METODO.md", "decisao": "adaptado", "razao": "porque sim",
            "criterios": {"independente_do_dominio": True, "nasceu_de_incidente": True,
                          "guardavel_por_procedimento": True, "duplica": None, "custo": "baixo"},
            "guarda": {"tipo": "teste", "caminho": "tests/test_conhecimento.py"},
        }],
    }


def _com(**mudancas) -> dict:
    cat = copy.deepcopy(_base())
    e = cat["entradas"][0]
    for chave, valor in mudancas.items():
        if chave in e["criterios"]:
            e["criterios"][chave] = valor
        else:
            e[chave] = valor
    return cat


def test_a_entrada_de_referencia_e_valida():
    assert k.problemas(_base()) == []


@pytest.mark.parametrize("mudancas, motivo", [
    ({"independente_do_dominio": False}, "depende do domínio"),
    ({"duplica": ".claude/skills/auditoria-pr"}, "funde-se ou recusa-se"),
    ({"decisao": "fundido"}, "fundido sem dizer em quê"),
    ({"decisao": "por_decidir"}, "sem próximo passo"),
    ({"razao": " "}, "sem razão"),
    ({"fontes": []}, "não diz de onde"),
    ({"destino": "docs/nao-existe.md"}, "destino"),
    ({"guarda": {"tipo": "teste", "caminho": "tests/nao_existe.py"}}, "a guarda"),
    ({"guarda": None}, "sem guarda"),
    ({"decisao": "talvez"}, "decisao"),
    ({"custo": "enorme"}, "custo"),
], ids=lambda v: v if isinstance(v, str) else None)
def test_cada_parametro_de_decisao_recusa_o_que_deve(mudancas, motivo):
    erros = k.problemas(_com(**mudancas))
    assert any(motivo in e for e in erros), f"esperava {motivo!r} em {erros}"


def test_recusar_algo_do_dominio_e_valido():
    assert k.problemas(_com(independente_do_dominio=False, decisao="recusado", guarda=None, destino=None)) == []


def test_ids_repetidos_sao_recusados():
    cat = _base()
    cat["entradas"].append(copy.deepcopy(cat["entradas"][0]))
    assert any("repetido" in e for e in k.problemas(cat))


def _alkmia_falso(raiz: Path) -> Path:
    (raiz / ".claude" / "agents").mkdir(parents=True)
    (raiz / ".claude" / "agents" / "novo.md").write_text("x", encoding="utf-8")
    (raiz / "docs").mkdir()
    (raiz / "docs" / "BIBLIA.md").write_text(
        "# PARTE I\n**I. Primeiro.** a\n**M1. Regra.** b\n**M22. Nova.** c\n# PARTE II\n**M99. Na parte II.** d\n",
        encoding="utf-8",
    )
    return raiz


def test_a_triagem_mostra_o_que_o_outro_projeto_tem_e_o_catalogo_nao(tmp_path):
    falta = k.por_triar(_base(), _alkmia_falso(tmp_path))
    assert falta == ["alkmia:.claude/agents/novo.md", "alkmia:docs/BIBLIA.md#I", "alkmia:docs/BIBLIA.md#M22"]


def test_a_triagem_recusa_apontar_para_este_repositorio():
    with pytest.raises(SystemExit, match="não pode ser este repositório"):
        k.por_triar(_base(), RAIZ)


def test_a_triagem_nao_escreve_no_outro_projeto(tmp_path):
    raiz = _alkmia_falso(tmp_path)
    antes = {p: p.read_bytes() for p in raiz.rglob("*") if p.is_file()}
    k.por_triar(_base(), raiz)
    assert {p: p.read_bytes() for p in raiz.rglob("*") if p.is_file()} == antes


def test_o_relatorio_conta_o_que_esta_guardado_por_procedimento():
    texto = k.relatorio(k.carregar())
    assert "Guardado por procedimento" in texto
    assert json.loads((RAIZ / "docs" / "conhecimento" / "catalogo.json").read_text(encoding="utf-8"))["entradas"]


def test_a_nota_para_o_alkmia_esta_em_dia_com_o_catalogo():
    """Gerada do catálogo; editada à mão ou esquecida depois de mudar o catálogo, diverge."""
    assert k.NOTA_ALKMIA.read_text(encoding="utf-8") == k.nota_alkmia(k.carregar()), (
        "corra: python tools/conhecimento.py alkmia --escrever"
    )


@pytest.mark.parametrize("mudancas, motivo", [
    ({"para_alkmia": {"estado_la": "talvez", "medido": "x", "como_aplicar": "y"}}, "estado_la"),
    ({"para_alkmia": {"estado_la": "falta", "medido": " ", "como_aplicar": "y"}}, "sem a medição"),
], ids=["estado-desconhecido", "sem-medicao"])
def test_para_alkmia_exige_estado_medicao_e_como(mudancas, motivo):
    cat = _com(origem="gdt", **mudancas)
    assert any(motivo in e for e in k.problemas(cat))


def test_para_alkmia_nao_vale_no_que_veio_do_alkmia():
    cat = _com(para_alkmia={"estado_la": "falta", "medido": "x", "como_aplicar": "y"})
    assert any("só faz sentido no que nasceu aqui" in e for e in k.problemas(cat))
