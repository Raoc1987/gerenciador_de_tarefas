"""Guardas de desempenho — travões, não referências.

A regra 68 do plano diz "não otimizar sem medir". Os números medidos estão em
``docs/MEDICOES.md``; isto é a outra metade: impedir que piorem uma ordem de
grandeza sem ninguém dar por isso.

**Os limites são folgados de propósito.** Uma máquina de integração partilhada
é várias vezes mais lenta do que um portátil, e um teste de desempenho
apertado reprova por causa do vizinho — e um teste que reprova por causa do
vizinho é desligado, que é o pior fim possível para um travão. O que estes
limites apanham é uma regressão de ordem de grandeza: alguém a pôr uma
consulta dentro de um ciclo, a análise a passar a quadrática. Medido no
portátil de desenvolvimento, o painel a 5 000 tarefas atualiza em 66 ms; o
limite aqui é 4 000.
"""

import statistics
import time
from datetime import date, timedelta

import pytest

import banco_de_dados as db
from core import permissoes

#: Quantas tarefas usar. Cinco mil é muito mais do que uma equipa cria num
#: ano, e pouco o suficiente para a suíte não ficar mais lenta por causa disto.
TAREFAS = 5_000

#: Repetições depois de uma de aquecimento. A primeira paga caches de SQLite
#: e de fontes, e não é a que alguém sente ao repetir a operação.
REPETICOES = 3


def mediana_ms(funcao) -> float:
    funcao()
    tempos = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        funcao()
        tempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(tempos)


@pytest.fixture
def muitas_tarefas():
    permissoes.definir_sessao("ana", "administrador", persistir=False)
    db.criar_tabela()
    hoje = date.today()
    with db.conectar() as conexao:
        conexao.executemany(
            "INSERT INTO tarefas (descricao, data_vencimento, concluida, "
            "criada_em, concluida_em, criada_por) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    f"Tarefa numero {i} com uma descricao de comprimento normal",
                    (hoje - timedelta(days=i % 60)).isoformat(),
                    i % 3 == 0,
                    (hoje - timedelta(days=i % 90)).isoformat(),
                    (hoje - timedelta(days=i % 60)).isoformat() if i % 3 == 0 else None,
                    "ana",
                )
                for i in range(TAREFAS)
            ],
        )
    return TAREFAS


def test_ler_as_tarefas_nao_e_uma_consulta_por_linha(muitas_tarefas):
    """13 ms medidos; o travão está em 2 000.

    O que isto apanha é uma consulta por tarefa — o erro clássico, e o que
    transforma um ecrã instantâneo num ecrã de dez segundos sem uma linha de
    código com ar de lenta.
    """
    from analitica import fontes

    assert mediana_ms(fontes.carregar_tarefas) < 2_000


def test_o_panorama_nao_e_quadratico(muitas_tarefas):
    """21 ms medidos; o travão está em 3 000."""
    from analitica import fontes

    assert mediana_ms(lambda: fontes.panorama(dias=30)) < 3_000


def test_os_insights_continuam_a_percorrer_a_lista_uma_vez(muitas_tarefas):
    """3 ms medidos; o travão está em 2 000."""
    from analitica import fontes
    from analitica.insights import gerar

    tarefas = fontes.carregar_tarefas()
    assert mediana_ms(lambda: gerar(tarefas)) < 2_000


def test_o_esforco_cresce_com_as_tarefas_e_nao_com_o_seu_quadrado(muitas_tarefas):
    """Cinco vezes mais tarefas não podem custar vinte e cinco vezes mais.

    É a forma de apanhar uma regressão de complexidade sem depender da
    velocidade da máquina: compara-se o programa consigo próprio, e a razão
    entre dois tempos não se importa com o processador onde correm.
    """
    from analitica import fontes
    from analitica.insights import gerar

    todas = fontes.carregar_tarefas()
    poucas = todas[: TAREFAS // 5]

    # Cada medição corre o trabalho várias vezes. Uma passagem só sobre mil
    # tarefas demora menos de um milissegundo nesta máquina, e uma razão
    # entre dois números abaixo da resolução do relógio não diz nada — a
    # primeira versão deste teste limitava-se a ser saltada.
    def vezes(tarefas, quantas=20):
        def correr():
            for _ in range(quantas):
                gerar(tarefas)
        return correr

    com_poucas = mediana_ms(vezes(poucas))
    com_todas = mediana_ms(vezes(todas))
    assert com_poucas >= 1.0, "a medição continua abaixo da resolução do relógio"

    # Linear daria 5x. O limite é 15x: deixa passar o ruído de medição e a
    # parte que não escala, e apanha 25x, que é o que um algoritmo
    # quadrático daria.
    assert com_todas / com_poucas < 15, (
        f"{com_poucas:.1f} ms com {len(poucas)} tarefas e "
        f"{com_todas:.1f} ms com {len(todas)} — cresce depressa de mais"
    )
