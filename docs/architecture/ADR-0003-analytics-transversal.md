# ADR-0003 — Analytics atravessa o produto, não é uma tela

Data: 2026-09-11 · Estado: aceite

## Contexto

Dashboards costumam nascer como uma tela que faz `SELECT` e desenha. O
resultado é lógica de negócio dentro da interface, métricas que divergem entre
telas e nenhuma reutilização para alertas, relatórios ou previsões.

## Decisão

Criar uma camada `analytics/` independente da interface e da persistência:

```
analytics/metricas.py   KPIs a partir de tarefas (funções puras)
analytics/series.py     séries temporais, média móvel, tendência,
                        previsão linear e deteção de anomalias
analytics/insights.py   frases derivadas dos números, nunca inventadas
analytics/fontes.py     a única peça que conhece o database
```

As funções recebem os dados e devolvem resultados. Não abrem conexões, não
tocam em widgets e não sabem que existe um dashboard.

O fluxo passa a ser:

```
database ──► eventos ──► (auditoria, plugins, notificações)
   │
   └──► analytics.fontes ──► métricas/séries ──► dashboard
                                    │
                                    └──► insights ──► alertas
```

## Consequências

**Boas**

- A mesma métrica serve dashboard, relatório, alerta e plugin — calculada
  num sítio só.
- Testável sem interface: a maior parte dos testes de analytics não abre uma
  janela.
- Trocar SQLite por outra persistência afeta `fontes.py` e mais nada.

**Custos**

- Uma indireção a mais entre o banco e o ecrã.
- É preciso disciplina: a tentação de fazer `SELECT` dentro de um widget
  continua a existir. Há testes que verificam que a camada de analytics não
  importa a interface.

## Regra de honestidade

Um insight só é produzido quando há dados que o sustentem, e diz sempre o
número em que se baseia. Sem dados suficientes, a resposta é "sem dados
suficientes" — não uma frase vaga que pareça inteligente.
