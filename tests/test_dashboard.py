"""Testes do dashboard e dos gráficos desenhados em Canvas."""

import pathlib
from datetime import date, timedelta

import pytest

from conftest import TKINTER_DISPONIVEL

pytestmark = pytest.mark.skipif(
    not TKINTER_DISPONIVEL, reason="ambiente sem interface gráfica"
)

tk = pytest.importorskip("tkinter", reason="ambiente sem Tkinter")
ttk = pytest.importorskip("tkinter.ttk", reason="ambiente sem Tkinter")

from analytics import fontes  # noqa: E402
from widgets.graficos import (  # noqa: E402
    CartaoKPI,
    GraficoBarras,
    GraficoLinhas,
    Serie,
)

HOJE = date(2026, 6, 15)


@pytest.fixture
def raiz():
    """Janela descartável para montar widgets."""
    from conftest import criar_janela_com_retentativa

    janela = criar_janela_com_retentativa(tk.Tk)
    janela.geometry("900x600")
    yield janela
    try:
        janela.destroy()
    except tk.TclError:  # pragma: no cover
        pass


def itens_do_canvas(grafico):
    """Tipos dos itens desenhados, para verificar que algo foi desenhado."""
    return [grafico.canvas.type(item) for item in grafico.canvas.find_all()]


def textos_do_canvas(grafico):
    return [
        grafico.canvas.itemcget(item, "text")
        for item in grafico.canvas.find_all()
        if grafico.canvas.type(item) == "text"
    ]


def botoes(widget):
    """Mapa ``texto -> botão`` dos botões sob um widget."""
    encontrados = {}

    def percorrer(atual):
        for filho in atual.winfo_children():
            if isinstance(filho, ttk.Button):
                encontrados[str(filho.cget("text"))] = filho
            percorrer(filho)

    percorrer(widget)
    return encontrados


def rotulos(widget):
    """Todos os textos dos ttk.Label sob um widget."""
    encontrados = []

    def percorrer(atual):
        for filho in atual.winfo_children():
            if isinstance(filho, ttk.Label):
                encontrados.append(str(filho.cget("text")))
            percorrer(filho)

    percorrer(widget)
    return encontrados


# ================================================================= GRÁFICOS


def test_grafico_de_linhas_desenha(raiz):
    pontos = [(date(2026, 6, d), float(d)) for d in range(1, 11)]
    grafico = GraficoLinhas(raiz, [Serie("Concluídas", pontos)], titulo="Teste")
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    tipos = itens_do_canvas(grafico)
    assert "line" in tipos, "a série tem de ser desenhada"
    assert "Teste" in textos_do_canvas(grafico)
    assert "Concluídas" in textos_do_canvas(grafico), "a legenda identifica a série"


def test_grafico_de_linhas_sem_dados_mostra_mensagem(raiz):
    grafico = GraficoLinhas(raiz, [], texto_sem_dados="Sem dados neste período.")
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    assert "Sem dados neste período." in textos_do_canvas(grafico)
    assert "line" not in itens_do_canvas(grafico)


def test_grafico_de_linhas_aceita_pontos_da_analise(raiz):
    """Aceita objetos Ponto (com .dia/.valor), não só tuplas."""
    from analytics.series import Ponto

    pontos = [Ponto(date(2026, 6, d), float(d)) for d in range(1, 6)]
    grafico = GraficoLinhas(raiz, [Serie("Série", pontos)])
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    assert "line" in itens_do_canvas(grafico)


def test_previsao_e_desenhada_a_tracejado(raiz):
    reais = [(date(2026, 6, d), float(d)) for d in range(1, 6)]
    previstos = [(date(2026, 6, d), float(d)) for d in range(6, 9)]
    grafico = GraficoLinhas(
        raiz,
        [Serie("Real", reais), Serie("Previsão", previstos, tracejado=True)],
    )
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    tracejadas = [
        item
        for item in grafico.canvas.find_all()
        if grafico.canvas.type(item) == "line" and grafico.canvas.itemcget(item, "dash")
    ]
    assert tracejadas, "a previsão não pode parecer um dado observado"


def test_grafico_de_barras_mostra_valores(raiz):
    grafico = GraficoBarras(raiz, [("Concluídas", 12), ("Pendentes", 5)])
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    assert itens_do_canvas(grafico).count("rectangle") == 2
    textos = textos_do_canvas(grafico)
    assert "12" in textos and "5" in textos
    assert "Concluídas" in textos


def test_grafico_de_barras_tudo_a_zero_e_tratado_como_sem_dados(raiz):
    grafico = GraficoBarras(raiz, [("A", 0), ("B", 0)], texto_sem_dados="Sem dados.")
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    assert "Sem dados." in textos_do_canvas(grafico)


def test_grafico_redesenha_ao_mudar_dados(raiz):
    grafico = GraficoBarras(raiz, [("A", 1)])
    grafico.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    grafico.definir_dados([("A", 1), ("B", 2), ("C", 3)])
    raiz.update()
    assert itens_do_canvas(grafico).count("rectangle") == 3


def test_cartao_kpi_mostra_valor_e_variacao(raiz):
    cartao = CartaoKPI(raiz, rotulo="Tarefas", valor="42", variacao=12.5)
    cartao.pack()
    raiz.update()
    textos = rotulos(raiz)
    assert "Tarefas" in textos
    assert "42" in textos
    assert any("12.5%" in t for t in textos)


def test_cartao_kpi_sem_variacao_nao_inventa_seta(raiz):
    cartao = CartaoKPI(raiz, rotulo="Tarefas", valor="42", variacao=None)
    cartao.pack()
    raiz.update()
    assert not any("▲" in t or "▼" in t for t in rotulos(raiz))


def test_cartao_kpi_com_subida_ma(raiz):
    """Em 'atrasadas', subir é mau: a cor tem de refletir isso."""
    from widgets.graficos import COR_ALERTA

    cartao = CartaoKPI(raiz, rotulo="Atrasadas", valor="7", variacao=30.0, subir_e_bom=False)
    cartao.pack()
    raiz.update()
    variacao = [w for w in cartao.winfo_children() if isinstance(w, ttk.Label)][-1]
    assert str(variacao.cget("foreground")) == COR_ALERTA


# ================================================================ DASHBOARD


def tarefas_de_exemplo(hoje=HOJE):
    """Histórico com conclusões, atrasos e vencimentos de hoje."""
    linhas = []
    identificador = 1
    for dias_atras in range(20, 0, -1):
        dia = (hoje - timedelta(days=dias_atras)).isoformat()
        linhas.append((identificador, f"Concluída {identificador}", dia, 1, dia, dia))
        identificador += 1
    linhas.append(
        (identificador, "Atrasada", (hoje - timedelta(days=3)).isoformat(), 0,
         (hoje - timedelta(days=10)).isoformat(), None)
    )
    identificador += 1
    linhas.append(
        (identificador, "Vence hoje", hoje.isoformat(), 0, hoje.isoformat(), None)
    )
    return linhas


@pytest.fixture
def painel(raiz):
    """Dashboard alimentado por dados fixos, sem tocar no banco."""
    from dashboard_ui import PainelDashboard

    def panorama_fixo(dias=30):
        return fontes.panorama(dias=dias, hoje=HOJE, tarefas=tarefas_de_exemplo())

    widget = PainelDashboard(raiz, obter_panorama=panorama_fixo)
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    return widget


def test_dashboard_mostra_os_kpis(painel, raiz):
    textos = rotulos(painel)
    assert "Criadas (30d)" in textos
    assert "Concluídas (30d)" in textos
    assert "Pendentes" in textos
    assert "Atrasadas" in textos
    assert "22" in textos, "20 concluídas + 1 atrasada + 1 que vence hoje"
    assert "20" in textos


def variacao_do_cartao(painel, chave):
    """Texto da linha de variação de um cartão (vazio quando não há)."""
    return str(painel._cartoes[chave].winfo_children()[-1].cget("text"))


def test_so_o_fluxo_tem_variacao(painel):
    """Comparar 'pendentes agora' com o passado exigiria histórico de estado."""
    assert set(painel.panorama.variacoes) == {"criadas", "concluidas"}
    assert variacao_do_cartao(painel, "pendentes") == "", "estado não inventa variação"
    assert variacao_do_cartao(painel, "atrasadas") == ""
    assert variacao_do_cartao(painel, "taxa") == ""


def test_sem_periodo_anterior_nem_o_fluxo_mostra_variacao(painel):
    """Os dados de exemplo só têm 20 dias: não há 30 dias anteriores."""
    assert painel.panorama.fluxo_anterior.concluidas == 0
    assert painel.panorama.variacoes["concluidas"] is None
    assert variacao_do_cartao(painel, "concluidas") == ""


def test_com_periodo_anterior_o_fluxo_mostra_variacao(raiz):
    """Com histórico dos dois lados, a comparação aparece."""
    from dashboard_ui import PainelDashboard

    linhas = []
    for dias_atras in range(60, 0, -1):
        dia = (HOJE - timedelta(days=dias_atras)).isoformat()
        # o dobro das conclusões na segunda metade do histórico
        for _ in range(2 if dias_atras <= 30 else 1):
            linhas.append((len(linhas) + 1, "Tarefa", dia, 1, dia, dia))

    widget = PainelDashboard(
        raiz,
        obter_panorama=lambda dias=30: fontes.panorama(dias=dias, hoje=HOJE, tarefas=linhas),
    )
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    # Quase o dobro das conclusões; a fronteira da janela impede um 100% exato.
    assert widget.panorama.variacoes["concluidas"] > 50
    assert "▲" in variacao_do_cartao(widget, "concluidas")
    assert variacao_do_cartao(widget, "pendentes") == ""


def test_dashboard_mostra_insights_com_numeros(painel):
    textos = rotulos(painel)
    assert any("atrasada" in t.lower() for t in textos)
    assert any("vencem hoje" in t.lower() for t in textos)


def test_dashboard_desenha_os_graficos(painel):
    assert "line" in itens_do_canvas(painel._grafico_linhas)
    assert "rectangle" in itens_do_canvas(painel._grafico_barras)


def test_mudar_o_periodo_recalcula(painel, raiz):
    assert painel.dias == 30
    painel.definir_periodo(7)
    raiz.update()
    assert painel.dias == 7
    assert painel.panorama.dias == 7
    assert len(painel.panorama.criadas) == 7


def test_periodos_disponiveis_no_seletor(painel):
    assert list(painel._seletor.cget("values")) == [
        "Últimos 7 dias",
        "Últimos 30 dias",
        "Últimos 90 dias",
        "Últimos 365 dias",
    ]


def test_dashboard_sem_dados_nao_finge(raiz):
    from dashboard_ui import PainelDashboard

    widget = PainelDashboard(raiz, obter_panorama=lambda dias=30: fontes.panorama(
        dias=dias, hoje=HOJE, tarefas=[]
    ))
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    textos = rotulos(widget)
    assert "0" in textos
    assert any("Sem observações" in t for t in textos)
    assert "Sem dados neste período." in textos_do_canvas(widget._grafico_linhas)


def test_dashboard_respeita_permissoes(raiz, monkeypatch):
    from core import permissoes
    from core.permissoes import Papel, Permissao
    from dashboard_ui import PainelDashboard

    monkeypatch.setitem(
        permissoes.PAPEIS,
        "sem_analise",
        Papel("sem_analise", frozenset({Permissao.TAREFAS_LER})),
    )
    permissoes.definir_sessao("bruno", "sem_analise", persistir=False)
    widget = PainelDashboard(raiz, obter_panorama=lambda dias=30: fontes.panorama(
        dias=dias, hoje=HOJE, tarefas=tarefas_de_exemplo()
    ))
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    textos = rotulos(widget)
    assert any("permissão" in t.lower() for t in textos)
    assert "—" in textos, "os cartões não mostram números"


def test_erro_no_calculo_nao_derruba_o_dashboard(raiz):
    from dashboard_ui import PainelDashboard

    def explode(dias=30):
        raise RuntimeError("falha a calcular")

    widget = PainelDashboard(raiz, obter_panorama=explode)
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()

    assert widget.winfo_exists()
    assert any("indicadores" in t.lower() for t in rotulos(widget))


def test_dashboard_reage_a_uma_tarefa_criada(raiz):
    """A espinha completa: criar tarefa -> evento -> dashboard recalcula."""
    import database
    from core import eventos
    from dashboard_ui import PainelDashboard

    database.criar_tabela()
    widget = PainelDashboard(raiz)
    widget.pack(fill=tk.BOTH, expand=True)
    raiz.update()
    assert widget.panorama.kpis.total == 0

    database.adicionar_tarefa("Tarefa nova")
    raiz.update()
    # O recálculo é adiado para agrupar rajadas de eventos.
    raiz.after(400, raiz.quit)
    raiz.mainloop()

    assert widget.panorama.kpis.total == 1
    assert eventos.barramento().subscritores("tarefa.criada"), "o painel está subscrito"


def test_dashboard_cancela_a_subscricao_ao_ser_destruido(raiz):
    from core import eventos
    from dashboard_ui import PainelDashboard

    widget = PainelDashboard(raiz, obter_panorama=lambda dias=30: fontes.panorama(
        dias=dias, hoje=HOJE, tarefas=[]
    ))
    widget.pack()
    raiz.update()
    assert eventos.barramento().subscritores("tarefa.criada")

    widget.destroy()
    raiz.update()
    assert eventos.barramento().subscritores("tarefa.criada") == []


def test_dashboard_traduz_os_insights(painel, raiz):
    import language_manager as lm

    lm.definir_idioma("en", persistir=False)
    painel.aplicar_idioma()
    raiz.update()

    textos = rotulos(painel)
    assert "Completed (30d)" in textos
    assert "Pending" in textos
    assert any("overdue" in t.lower() for t in textos)


# ============================================================== EXPORTAÇÃO


@pytest.fixture
def dialogos_de_ficheiro(monkeypatch, tmp_path):
    """Substitui os diálogos modais da exportação e regista o que apareceu."""
    from tkinter import filedialog, messagebox

    import dashboard_ui

    registo = {"destino": str(tmp_path / "relatorio.pdf"), "info": [], "erro": [], "aviso": []}
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", lambda *a, **k: registo["destino"]
    )
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: registo["info"].append(a))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: registo["erro"].append(a))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: registo["aviso"].append(a))
    monkeypatch.setattr(dashboard_ui, "filedialog", filedialog)
    monkeypatch.setattr(dashboard_ui, "messagebox", messagebox)
    return registo


def test_botao_exportar_gera_o_ficheiro(painel, raiz, dialogos_de_ficheiro, monkeypatch):
    import database

    database.criar_tabela()
    database.adicionar_tarefa("Tarefa para o relatório", "2030-01-01")

    botoes(painel)["Exportar"].invoke()
    raiz.update()

    destino = pathlib.Path(dialogos_de_ficheiro["destino"])
    assert destino.is_file(), "o relatório tem de existir no disco"
    assert destino.read_bytes().startswith(b"%PDF")
    assert dialogos_de_ficheiro["info"], "o utilizador tem de saber onde ficou"
    assert str(destino) in dialogos_de_ficheiro["info"][-1][1]


def test_cancelar_a_gravacao_nao_escreve_nada(painel, raiz, dialogos_de_ficheiro):
    dialogos_de_ficheiro["destino"] = ""
    assert painel.exportar() is None
    assert not dialogos_de_ficheiro["info"]


def test_exportar_sem_permissao_avisa(raiz, dialogos_de_ficheiro):
    from core import permissoes
    from dashboard_ui import PainelDashboard

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    widget = PainelDashboard(
        raiz, obter_panorama=lambda dias=30: fontes.panorama(dias=dias, hoje=HOJE, tarefas=[])
    )
    widget.pack()
    raiz.update()

    assert widget.exportar() is None
    assert dialogos_de_ficheiro["aviso"]
    assert not pathlib.Path(dialogos_de_ficheiro["destino"]).exists()


def test_falha_a_exportar_mostra_erro_e_nao_derruba(painel, raiz, dialogos_de_ficheiro, monkeypatch):
    import dashboard_ui

    def explode(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(dashboard_ui.servico, "exportar", explode)
    assert painel.exportar() is None
    assert dialogos_de_ficheiro["erro"]
    assert painel.winfo_exists()
