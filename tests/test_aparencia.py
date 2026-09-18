"""Testes da aparência.

"Bonito" é uma opinião e não se testa. **Legível** é um número, e testa-se:
estes testes medem o contraste de cada par de cores que aparece mesmo no
ecrã, nos dois modos, contra os limiares da WCAG 2.1.

O outro teste é o que impede a decadência. Um sistema de tokens dura até ao
dia em que alguém tem pressa e escreve ``"#7a8794"`` num ecrã novo — e a
partir daí volta a haver duas fontes de verdade. A regra está em
``tests/test_arquitetura.py``, junto às outras regras de arquitetura.
"""

import pytest

from aparencia import contraste, paleta, tema
from aparencia.contraste import AA_GRANDE, AA_TEXTO, racio

#: Pares ``(frente, fundo)`` de **texto** que a aplicação desenha mesmo.
#:
#: A lista é escrita à mão de propósito. Gerá-la de todas as combinações
#: possíveis daria centenas de pares que ninguém vai ver, e o teste passaria
#: a medir combinações imaginárias — ou a falhar por causa delas.
PARES_DE_TEXTO = [
    ("texto", "superficie"),
    ("texto", "superficie_alta"),
    ("texto", "acento_suave"),
    ("texto_suave", "superficie"),
    ("texto_suave", "superficie_alta"),
    ("texto_tenue", "superficie"),
    ("acento", "superficie"),
    ("acento", "superficie_alta"),
    ("bom", "superficie"),
    ("aviso", "superficie"),
    ("mau", "superficie"),
    ("sobre_acento", "acento"),
]

#: Pares que identificam um controlo, e não texto. Limiar mais baixo.
PARES_DE_CONTROLO = [
    ("contorno_controlo", "superficie"),
    ("contorno_controlo", "superficie_alta"),
    ("foco", "superficie"),
    ("acento", "superficie"),
]

MODOS = ("claro", "escuro")


# ================================================================= medida


def test_a_formula_do_contraste_esta_certa():
    """Ancoras conhecidas: se estas falharem, tudo o resto está errado."""
    assert racio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert racio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.01)
    # O rácio não tem sentido de direção.
    assert racio("#123456", "#FFFFFF") == pytest.approx(racio("#FFFFFF", "#123456"))


def test_a_luminancia_nao_e_a_media_dos_canais():
    """O verde pesa muito mais do que o azul, e é isso que torna a fórmula útil.

    Com a média simples, estes dois dariam o mesmo — e um deles é legível
    sobre branco, o outro não.
    """
    assert contraste.luminancia("#00FF00") > contraste.luminancia("#0000FF") * 5


def test_uma_cor_mal_formada_nao_passa_em_silencio():
    for bruta in ("azul", "#FFF", "", "#12345"):
        with pytest.raises(ValueError):
            racio(bruta, "#FFFFFF")


# ============================================================= legibilidade


@pytest.mark.parametrize("modo", MODOS)
def test_todo_o_texto_passa_o_limiar_da_norma(modo):
    c = paleta.cores(modo)
    falhas = [
        f"{frente} sobre {fundo}: {racio(c[frente], c[fundo]):.2f}"
        for frente, fundo in PARES_DE_TEXTO
        if racio(c[frente], c[fundo]) < AA_TEXTO
    ]
    assert not falhas, f"No modo {modo}, abaixo de {AA_TEXTO}:1 — {falhas}"


@pytest.mark.parametrize("modo", MODOS)
def test_os_controlos_distinguem_se_do_fundo(modo):
    c = paleta.cores(modo)
    falhas = [
        f"{frente} sobre {fundo}: {racio(c[frente], c[fundo]):.2f}"
        for frente, fundo in PARES_DE_CONTROLO
        if racio(c[frente], c[fundo]) < AA_GRANDE
    ]
    assert not falhas, f"No modo {modo}, abaixo de {AA_GRANDE}:1 — {falhas}"


@pytest.mark.parametrize("modo", MODOS)
def test_as_series_dos_graficos_distinguem_se_entre_si(modo):
    """Duas séries quase iguais obrigam a conferir a legenda para ler o gráfico.

    Aqui a medida é a **distância percebida** (ΔE), e não o rácio de
    contraste. Escrevi este teste com o rácio à primeira, e ele reprovou uma
    paleta que estava certa: o rácio compara luminância, e um azul e um verde
    igualmente luminosos dão 1,16 — que qualquer pessoa distingue. Era a
    pergunta errada com o número que eu já tinha à mão.

    Isto não cobre daltonismo: duas cores podem ter ΔE alto e ser o mesmo
    para quem não distingue vermelho de verde. É por isso que o gráfico de
    linhas separa as séries também pelo traço (contínuo, tracejado,
    pontilhado) — a cor não é a única pista.
    """
    series = paleta.series(modo)
    assert len(set(series)) == len(series), "há uma cor de série repetida"
    for i, uma in enumerate(series):
        for outra in series[i + 1 :]:
            afastamento = contraste.distancia(uma, outra)
            assert afastamento >= contraste.DISTINTAS, (
                f"{uma} e {outra} estão a ΔE {afastamento:.1f}, abaixo de "
                f"{contraste.DISTINTAS}: passam por variações da mesma cor."
            )


@pytest.mark.parametrize("modo", MODOS)
def test_as_series_veem_se_sobre_o_fundo(modo):
    fundo = paleta.cores(modo)["superficie"]
    for cor in paleta.series(modo):
        assert racio(cor, fundo) >= 2.0, f"{cor} desaparece sobre {fundo}"


# ================================================================= tokens


def test_os_dois_modos_tem_exatamente_os_mesmos_papeis():
    """Um token a faltar num modo é um ``KeyError`` só no modo menos usado."""
    assert set(paleta.CLARO) == set(paleta.ESCURO)


def test_um_modo_desconhecido_e_um_erro():
    with pytest.raises(ValueError):
        paleta.cores("sepia")


@pytest.mark.parametrize("modo", MODOS)
def test_todas_as_cores_estao_em_formato_conhecido(modo):
    for nome, valor in paleta.cores(modo).items():
        assert valor.startswith("#") and len(valor) == 7, f"{nome} = {valor!r}"
        racio(valor, "#FFFFFF")  # levanta se não for interpretável


def test_a_escala_de_letra_e_fechada():
    """Aceitar um tamanho solto era abrir a porta que isto veio fechar."""
    with pytest.raises(ValueError):
        tema.fonte("gigante")


def test_a_escala_de_letra_cresce():
    tamanhos = [paleta.TAMANHO[n] for n in
                ("micro", "pequeno", "corpo", "destaque", "subtitulo", "titulo", "display")]
    assert tamanhos == sorted(tamanhos)
    assert len(set(tamanhos)) == len(tamanhos), "dois degraus com o mesmo tamanho"


def test_a_escala_de_espaco_assenta_numa_grelha_de_quatro():
    """Menos o mínimo, que existe para o ajuste fino de uma linha de texto."""
    for nome, valor in paleta.ESPACO.items():
        if nome == "minimo":
            continue
        assert valor % 4 == 0, f"{nome} = {valor} sai da grelha"


def test_pedir_uma_fonte_sem_ecra_nao_rebenta():
    """Os testes têm de poder perguntar sem abrir uma janela."""
    familia, pontos = tema.fonte("corpo")
    assert isinstance(familia, str) and familia
    assert pontos == paleta.TAMANHO["corpo"]
