# ADR-0002 — Gráficos desenhados em Tk, sem matplotlib nem pandas

Data: 2026-09-11 · Estado: aceite

## Contexto

O produto precisa de dashboards com séries temporais, comparações,
distribuição e indicadores. O caminho habitual em Python é matplotlib, com
pandas e NumPy para os cálculos.

A aplicação não tem hoje **nenhuma** dependência de execução: o executável
ocupa 27 MiB e é construído e validado em menos de um minuto.

## Decisão

Os gráficos do núcleo são desenhados no `tkinter.Canvas`, e as métricas são
calculadas com a biblioteca padrão.

Bibliotecas pesadas (NumPy, pandas, SciPy, scikit-learn) entram **apenas**
quando existir um problema que a estatística simples não resolva — e nessa
altura entram como dependência de um **plugin**, não do núcleo.

## Consequências

**Boas**

- Instalador continua na ordem dos 11 MiB em vez de ~200 MiB.
- Arranque instantâneo: não há import de matplotlib no caminho crítico.
- Os gráficos herdam o tema do sistema, sem embutir uma figura estranha à UI.

**Custos**

- Cada tipo de gráfico é código nosso: começámos com linha, barras e KPI
  cards. Um gráfico novo é trabalho, não um parâmetro.
- Não há interatividade avançada (zoom, seleção) sem a implementarmos.

## Quando reconsiderar

Se um módulo precisar de visualizações que não faça sentido escrever à mão
(boxplots, heatmaps densos, Gantt interativo), esse módulo traz matplotlib
como dependência **sua**, e o núcleo continua limpo.
