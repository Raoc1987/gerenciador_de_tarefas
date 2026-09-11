"""Testes da camada de análise: métricas, séries, insights e fontes."""

from datetime import date, datetime, timedelta

import pytest

from analytics import fontes, insights, metricas, series
from analytics.datas import intervalo_de_dias, para_data, periodo_anterior
from analytics.insights import Nivel, Tipo
from analytics.metricas import KPIs, Tarefa, calcular_kpis
from analytics.series import Ponto

HOJE = date(2026, 6, 15)


def tarefa(
    identificador=1,
    descricao="Tarefa",
    vencimento=None,
    concluida=False,
    criada="2026-06-01",
    concluida_em=None,
):
    """Linha do banco, como ``buscar_tarefas_completas`` a devolveria."""
    return (
        identificador,
        descricao,
        vencimento,
        1 if concluida else 0,
        criada,
        concluida_em,
    )


# =================================================================== DATAS


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("2026-06-15", date(2026, 6, 15)),
        ("2026-06-15T10:30:00", date(2026, 6, 15)),
        (date(2026, 6, 15), date(2026, 6, 15)),
        (datetime(2026, 6, 15, 8, 0), date(2026, 6, 15)),
    ],
)
def test_para_data_converte(entrada, esperado):
    assert para_data(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "   ", "ontem", "15/06/2026", 12345])
def test_para_data_devolve_none_em_vez_de_adivinhar(entrada):
    assert para_data(entrada) is None


def test_intervalo_de_dias():
    assert intervalo_de_dias(HOJE, 7) == (date(2026, 6, 9), HOJE)
    assert intervalo_de_dias(HOJE, 1) == (HOJE, HOJE)


def test_intervalo_invalido():
    with pytest.raises(ValueError):
        intervalo_de_dias(HOJE, 0)


def test_periodo_anterior_tem_a_mesma_duracao():
    inicio, fim = intervalo_de_dias(HOJE, 7)
    antes_inicio, antes_fim = periodo_anterior(inicio, fim)
    assert antes_fim == inicio - timedelta(days=1)
    assert (antes_fim - antes_inicio).days == (fim - inicio).days


# ================================================================ MÉTRICAS


def test_kpis_sem_tarefas():
    vazio = calcular_kpis([], HOJE)
    assert vazio == KPIs()
    assert vazio.tem_dados is False


def test_kpis_basicos():
    tarefas = [
        tarefa(1, concluida=True, concluida_em="2026-06-10"),
        tarefa(2, vencimento="2026-06-10"),          # atrasada
        tarefa(3, vencimento="2026-06-15"),          # vence hoje
        tarefa(4),                                   # sem prazo
    ]
    kpis = calcular_kpis(tarefas, HOJE)
    assert kpis.total == 4
    assert kpis.concluidas == 1
    assert kpis.pendentes == 3
    assert kpis.atrasadas == 1
    assert kpis.vencem_hoje == 1
    assert kpis.sem_prazo == 1
    assert kpis.taxa_conclusao == 25.0
    assert kpis.taxa_atraso == pytest.approx(33.3)


def test_tarefa_concluida_nunca_conta_como_atrasada():
    tarefas = [tarefa(1, vencimento="2026-01-01", concluida=True, concluida_em="2026-01-05")]
    assert calcular_kpis(tarefas, HOJE).atrasadas == 0


def test_tarefa_sem_prazo_nunca_esta_atrasada():
    assert calcular_kpis([tarefa(1)], HOJE).atrasadas == 0


def test_duracao_media_so_com_dados():
    sem_datas = calcular_kpis([tarefa(1, concluida=True)], HOJE)
    assert sem_datas.duracao_media_dias is None

    com_datas = calcular_kpis(
        [
            tarefa(1, concluida=True, criada="2026-06-01", concluida_em="2026-06-03"),
            tarefa(2, concluida=True, criada="2026-06-01", concluida_em="2026-06-05"),
        ],
        HOJE,
    )
    assert com_datas.duracao_media_dias == 3.0


def test_aceita_tuplas_de_cinco_colunas():
    """O formato antigo (sem concluida_em) continua a funcionar."""
    linha = (1, "Tarefa", "2026-06-10", 0, "2026-06-01")
    kpis = calcular_kpis([linha], HOJE)
    assert kpis.total == 1
    assert kpis.atrasadas == 1


def test_normalizar_e_idempotente():
    linha = tarefa(1)
    uma_vez = metricas.normalizar([linha])
    duas_vezes = metricas.normalizar(uma_vez)
    assert uma_vez == duas_vezes
    assert isinstance(duas_vezes[0], Tarefa)


def test_filtrar_por_periodo():
    tarefas = [
        tarefa(1, criada="2026-06-01"),
        tarefa(2, criada="2026-06-10"),
        tarefa(3, criada="2026-06-20"),
    ]
    filtradas = metricas.filtrar_por_periodo(tarefas, date(2026, 6, 5), date(2026, 6, 15))
    assert [t.id for t in filtradas] == [2]


def test_filtrar_ignora_tarefas_sem_a_data_pedida():
    tarefas = [tarefa(1, concluida=True, concluida_em=None)]
    assert metricas.filtrar_por_periodo(tarefas, campo="concluida_em") == []


def test_contar_por():
    tarefas = [tarefa(1, concluida=True), tarefa(2), tarefa(3)]
    contagem = metricas.contar_por(
        tarefas, lambda t: "concluída" if t.concluida else "pendente"
    )
    assert contagem == {"concluída": 1, "pendente": 2}


def test_comparar_devolve_none_quando_o_anterior_era_zero():
    atual = calcular_kpis([tarefa(1, concluida=True, concluida_em="2026-06-10")], HOJE)
    variacoes = metricas.comparar(atual, KPIs())
    assert variacoes["total"] is None
    assert variacoes["concluidas"] is None


def test_comparar_calcula_variacao():
    atual = KPIs(total=150, concluidas=100)
    anterior = KPIs(total=100, concluidas=50)
    variacoes = metricas.comparar(atual, anterior)
    assert variacoes["total"] == 50.0
    assert variacoes["concluidas"] == 100.0


# ================================================================== SÉRIES


def test_serie_diaria_preenche_dias_sem_dados():
    datas = ["2026-06-13", "2026-06-15", "2026-06-15"]
    serie = series.serie_diaria(datas, date(2026, 6, 13), date(2026, 6, 15))
    assert [(p.dia.day, p.valor) for p in serie] == [(13, 1.0), (14, 0.0), (15, 2.0)]


def test_serie_diaria_ignora_datas_invalidas():
    serie = series.serie_diaria([None, "", "ontem"], date(2026, 6, 14), date(2026, 6, 15))
    assert [p.valor for p in serie] == [0.0, 0.0]


def test_ponto_desempacota():
    dia, valor = Ponto(HOJE, 3.0)
    assert (dia, valor) == (HOJE, 3.0)


def test_total_e_media():
    serie = [Ponto(HOJE, 2.0), Ponto(HOJE, 4.0)]
    assert series.total(serie) == 6.0
    assert series.media(serie) == 3.0
    assert series.media([]) is None


def test_media_movel_comeca_no_inicio_da_serie():
    serie = [Ponto(date(2026, 6, i), float(i)) for i in range(1, 6)]
    suavizada = series.media_movel(serie, janela=3)
    assert len(suavizada) == len(serie)
    assert suavizada[0].valor == 1.0        # só um ponto disponível
    assert suavizada[2].valor == 2.0        # média de 1, 2, 3
    assert suavizada[4].valor == 4.0        # média de 3, 4, 5


def test_media_movel_com_janela_invalida():
    with pytest.raises(ValueError):
        series.media_movel([], janela=0)


def test_tendencia_de_subida():
    serie = [Ponto(date(2026, 6, i), float(i)) for i in range(1, 11)]
    ajuste = series.tendencia(serie)
    assert ajuste.valida
    assert ajuste.direcao == "subida"
    assert ajuste.declive == pytest.approx(1.0)
    assert ajuste.r2 == pytest.approx(1.0)


def test_tendencia_de_descida():
    serie = [Ponto(date(2026, 6, i), float(20 - i)) for i in range(1, 11)]
    assert series.tendencia(serie).direcao == "descida"


def test_serie_constante_e_estavel():
    serie = [Ponto(date(2026, 6, i), 5.0) for i in range(1, 11)]
    ajuste = series.tendencia(serie)
    assert ajuste.direcao == "estável"
    assert ajuste.r2 == 1.0


def test_tendencia_com_poucos_pontos_e_invalida():
    serie = [Ponto(date(2026, 6, i), float(i)) for i in range(1, 3)]
    ajuste = series.tendencia(serie)
    assert ajuste.valida is False
    assert ajuste.direcao == "estável"


def test_previsao_prolonga_a_serie():
    serie = [Ponto(date(2026, 6, i), float(i)) for i in range(1, 11)]
    previsao = series.prever(serie, dias=3)
    assert [p.dia for p in previsao] == [
        date(2026, 6, 11),
        date(2026, 6, 12),
        date(2026, 6, 13),
    ]
    assert previsao[0].valor == pytest.approx(11.0, abs=0.1)


def test_previsao_nao_desce_abaixo_de_zero():
    serie = [Ponto(date(2026, 6, i), float(max(0, 5 - i))) for i in range(1, 11)]
    assert all(p.valor >= 0 for p in series.prever(serie, dias=5))


def test_previsao_sem_dados_suficientes_devolve_vazio():
    assert series.prever([Ponto(HOJE, 1.0)], dias=3) == []
    assert series.prever([], dias=3) == []


def test_previsao_de_zero_dias_e_erro():
    with pytest.raises(ValueError):
        series.prever([Ponto(HOJE, 1.0)], dias=0)


def test_anomalia_detetada():
    serie = [Ponto(date(2026, 6, i), 2.0) for i in range(1, 11)]
    serie[5] = Ponto(serie[5].dia, 40.0)
    anomalias = series.detetar_anomalias(serie)
    assert [p.valor for p in anomalias] == [40.0]


def test_serie_normal_nao_tem_anomalias():
    valores = [3.0, 4.0, 2.0, 5.0, 3.0, 4.0, 3.0, 2.0, 4.0, 3.0]
    serie = [Ponto(date(2026, 6, i + 1), v) for i, v in enumerate(valores)]
    assert series.detetar_anomalias(serie) == []


def test_anomalias_exigem_historico_minimo():
    serie = [Ponto(date(2026, 6, i), 1.0) for i in range(1, 5)]
    assert series.detetar_anomalias(serie) == []


def test_variacao_percentual():
    assert series.variacao_percentual(150, 100) == 50.0
    assert series.variacao_percentual(50, 100) == -50.0
    assert series.variacao_percentual(10, 0) is None


# ================================================================ INSIGHTS


def test_sem_tarefas_nao_ha_insights():
    assert insights.gerar([], hoje=HOJE) == []


def test_insight_de_atraso():
    tarefas = [tarefa(i, vencimento="2026-06-01") for i in range(1, 5)]
    encontrados = insights.gerar(tarefas, hoje=HOJE)
    atraso = [i for i in encontrados if i.chave == "insight_atrasadas"]
    assert len(atraso) == 1
    assert atraso[0].parametros["quantidade"] == 4
    assert atraso[0].nivel == Nivel.CRITICO  # 100% das pendentes


def test_atraso_pontual_e_apenas_atencao():
    tarefas = [tarefa(1, vencimento="2026-06-01")] + [
        tarefa(i, vencimento="2026-12-01") for i in range(2, 12)
    ]
    atraso = [i for i in insights.gerar(tarefas, hoje=HOJE) if i.chave == "insight_atrasadas"]
    assert atraso[0].nivel == Nivel.ATENCAO


def test_insight_de_produtividade_a_subir():
    tarefas = []
    identificador = 1
    # período anterior (16/05 a 30/05): 2 conclusões
    for dia in (20, 25):
        tarefas.append(
            tarefa(identificador, concluida=True, concluida_em=f"2026-05-{dia:02d}")
        )
        identificador += 1
    # período atual (01/06 a 15/06): 6 conclusões
    for dia in (2, 4, 6, 8, 10, 12):
        tarefas.append(
            tarefa(identificador, concluida=True, concluida_em=f"2026-06-{dia:02d}")
        )
        identificador += 1

    encontrados = insights.gerar(tarefas, hoje=HOJE, dias=15)
    subida = [i for i in encontrados if i.chave == "insight_produtividade_subiu"]
    assert len(subida) == 1
    assert subida[0].nivel == Nivel.POSITIVO
    assert subida[0].tipo == Tipo.DIAGNOSTICO
    assert subida[0].parametros["atual"] == 6
    assert subida[0].parametros["anterior"] == 2
    assert subida[0].parametros["percentagem"] == 200.0


def test_insight_de_produtividade_a_descer():
    tarefas = []
    identificador = 1
    for dia in (18, 20, 22, 24, 26, 28):
        tarefas.append(
            tarefa(identificador, concluida=True, concluida_em=f"2026-05-{dia:02d}")
        )
        identificador += 1
    tarefas.append(tarefa(identificador, concluida=True, concluida_em="2026-06-02"))

    encontrados = insights.gerar(tarefas, hoje=HOJE, dias=15)
    descida = [i for i in encontrados if i.chave == "insight_produtividade_desceu"]
    assert len(descida) == 1
    assert descida[0].nivel == Nivel.ATENCAO


def test_variacao_pequena_nao_gera_insight():
    """Ruído não é notícia: menos de 10% de variação fica calado."""
    tarefas = []
    identificador = 1
    for dia in (18, 20, 22, 24, 26, 28, 29, 30, 31, 17):
        tarefas.append(
            tarefa(identificador, concluida=True, concluida_em=f"2026-05-{dia:02d}")
        )
        identificador += 1
    for dia in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
        tarefas.append(
            tarefa(identificador, concluida=True, concluida_em=f"2026-06-{dia:02d}")
        )
        identificador += 1

    encontrados = insights.gerar(tarefas, hoje=HOJE, dias=15)
    assert not [i for i in encontrados if "produtividade" in i.chave]


def test_insight_de_vencimento_hoje():
    tarefas = [tarefa(1, vencimento="2026-06-15")]
    encontrados = insights.gerar(tarefas, hoje=HOJE)
    vencem = [i for i in encontrados if i.chave == "insight_vencem_hoje"]
    assert vencem[0].parametros["quantidade"] == 1
    assert vencem[0].tipo == Tipo.PRESCRITIVO


def test_insight_de_tarefas_sem_prazo():
    tarefas = [tarefa(i) for i in range(1, 6)]
    encontrados = insights.gerar(tarefas, hoje=HOJE)
    assert [i for i in encontrados if i.chave == "insight_sem_prazo"]


def test_insights_vem_ordenados_por_gravidade():
    tarefas = [tarefa(1, vencimento="2026-06-01"), tarefa(2, vencimento="2026-06-15")]
    encontrados = insights.gerar(tarefas, hoje=HOJE)
    niveis = [i.nivel for i in encontrados]
    ordem = {Nivel.CRITICO: 0, Nivel.ATENCAO: 1, Nivel.POSITIVO: 2, Nivel.INFORMACAO: 3}
    assert niveis == sorted(niveis, key=lambda n: ordem[n])


def test_insights_nao_inventam_tendencia_com_poucos_dados():
    tarefas = [tarefa(1, concluida=True, concluida_em="2026-06-14")]
    encontrados = insights.gerar(tarefas, hoje=HOJE)
    assert not [i for i in encontrados if i.chave == "insight_tendencia"]


# ================================================================== FONTES


def test_panorama_sem_tarefas():
    visao = fontes.panorama(dias=30, hoje=HOJE, tarefas=[])
    assert visao.tem_dados is False
    assert visao.tem_historico is False
    assert visao.kpis.total == 0
    assert visao.insights == []
    assert len(visao.criadas) == 30


def test_panorama_calcula_tudo_de_uma_vez():
    tarefas = [
        tarefa(1, criada="2026-06-01", concluida=True, concluida_em="2026-06-02"),
        tarefa(2, criada="2026-06-05", vencimento="2026-06-10"),
        tarefa(3, criada="2026-06-14", vencimento="2026-06-15"),
    ]
    visao = fontes.panorama(dias=30, hoje=HOJE, tarefas=tarefas)

    assert visao.tem_dados and visao.tem_historico
    assert visao.kpis.total == 3
    assert visao.kpis.atrasadas == 1
    assert visao.inicio == date(2026, 5, 17)
    assert visao.fim == HOJE
    assert len(visao.criadas) == 30 == len(visao.concluidas)
    assert len(visao.concluidas_suavizadas) == 30
    assert visao.insights, "com atraso e vencimento de hoje tem de haver insights"


def test_panorama_respeita_o_periodo():
    for dias in fontes.PERIODOS:
        visao = fontes.panorama(dias=dias, hoje=HOJE, tarefas=[])
        assert visao.dias == dias
        assert len(visao.criadas) == dias


def test_panorama_le_do_banco(dados_isolados):
    import database

    database.criar_tabela()
    tarefa_id = database.adicionar_tarefa("Do banco", "2030-01-01")
    database.concluir_tarefa(tarefa_id)

    visao = fontes.panorama(dias=30)
    assert visao.kpis.total == 1
    assert visao.kpis.concluidas == 1


def test_analytics_exige_permissao():
    from core import permissoes
    from core.permissoes import PermissaoNegadaError

    permissoes.definir_sessao("bruno", "colaborador", persistir=False)
    with pytest.raises(PermissaoNegadaError):
        fontes.carregar_tarefas()


def test_tendencia_de_conclusoes_do_panorama():
    tarefas = [
        tarefa(i, criada="2026-06-01", concluida=True, concluida_em=f"2026-06-{i:02d}")
        for i in range(1, 11)
    ]
    visao = fontes.panorama(dias=30, hoje=HOJE, tarefas=tarefas)
    assert fontes.tendencia_de_conclusoes(visao).valida


# =========================================================== ARQUITETURA


def test_analytics_nao_depende_da_interface():
    """ADR-0003: a camada de análise não conhece a interface nem os plugins."""
    import ast
    from pathlib import Path

    pasta = Path(__file__).resolve().parent.parent / "src" / "analytics"
    proibidos = {"tkinter", "gui", "plugin_ui", "core.plugin_manager", "dashboard_ui"}

    for arquivo in pasta.glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            else:
                continue
            for nome in nomes:
                raiz = nome.split(".")[0]
                assert nome not in proibidos and raiz != "tkinter", (
                    f"{arquivo.name} importa {nome}"
                )


def test_so_as_fontes_conhecem_o_banco():
    """Toda a leitura do banco passa por analytics/fontes.py."""
    from pathlib import Path

    pasta = Path(__file__).resolve().parent.parent / "src" / "analytics"
    for arquivo in pasta.glob("*.py"):
        if arquivo.name == "fontes.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        assert "import database" not in texto, f"{arquivo.name} importa database"
