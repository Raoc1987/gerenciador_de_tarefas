# Auditoria do plano de plataforma — o que existe, o que falta

Data: 2026-09-18 · Commit base: `main` depois do PR #23

Este documento responde à **Regra 4** ("não reescrever cegamente") e à
**Regra 104** ("indicar claramente IMPLEMENTADO / NÃO IMPLEMENTADO / NÃO
VALIDADO") do plano de evolução para plataforma empresarial.

Existe por uma razão concreta: o plano descreve o projeto a partir de um
baseline que já não é o atual. Fala de `database.py` e `test_database.py`,
que deixaram de existir no [ADR-0005](architecture/ADR-0005-nomes-de-topo.md);
e trata Calculadora, Calendário e Atualizações como abas, quando são plugins
instaláveis e atualizáveis desde o [ADR-0006](architecture/ADR-0006-posse-dos-plugins.md).

**Cerca de metade do que o plano pede já está construído e testado.** Construí-lo
outra vez não seria só desperdício: seria pôr duas implementações da mesma
coisa a competir dentro do produto — exatamente o "Frankenstein" contra o qual
a regra 37 do próprio plano avisa.

---

## Já implementado, e verificado

| § do plano | O que pede | Onde está |
|---|---|---|
| 37 | Classificar Core/Module/Plugin/Service/Agent/Skill antes de implementar | ADR-0004 + `CLASSIFICACAO.md`, com um teste que falha se algo existir sem classificação |
| 38 | Plugin System: install, validate, enable, disable, update, rollback, remove; built-in e local | `core/plugin_*.py` (6 módulos), ADR-0006 |
| 39 | Event Bus com eventos nomeados | `core/eventos.py`, com padrões, donos e isolamento de falhas |
| 40 | Workflow Engine: EVENT → CONDITION → ACTION | `src/regras/` |
| 41 | Automações (notificações, alertas, tarefas automáticas) | `automacoes.py` + `regras/acoes.py` |
| 45 | RBAC | `core/permissoes.py`, 6 papéis |
| 46 | ABAC — regras por atributo | ADR-0007: `Pedido(ação, objeto)`, políticas que **só recusam** |
| 47 | Auditoria: quem, o quê, quando, valor anterior, novo valor | `core/auditoria.py`, persistida, com retenção |
| 49 | Backup, Restore, Integrity Check, Export | `core/backup.py` |
| 50–54 | Design System, light/dark, cores semânticas, tipografia | `src/aparencia/`, ADR-0008. Contraste **medido** contra a WCAG 2.1 |
| 70 | Feature flags | `core/funcionalidades.py`, com interruptor por instalação |
| 75 | Migrações, índices, integridade | `banco_de_dados.py`, `PRAGMA user_version`, v12 |
| 76 | Import Wizard: ficheiro → deteção → mapeamento → validação → duplicados → preview → importação | `src/importacao/` — é exatamente este fluxo |
| 77 | Export Engine PDF/XLSX/CSV | `src/relatorios/exportadores/`, escritos à mão (ADR-0002) |
| 11 | Pesquisa global | `src/pesquisa.py` — registo de fontes, cada módulo declara a sua |
| 15 | KPI Engine com KPIs declarativos | `src/indicadores.py` — um módulo declara o que sabe medir |
| 27–28 | Tendência, média móvel, forecast, anomalias, insights | `analitica/series.py`, `analitica/insights.py`, `alertas.py` |
| 79 | Sistema de alertas por regra | `src/alertas.py` |
| 84–85 | Instalador; dados fora de `Program Files` | Inno Setup; `core/paths.py` |
| 86 | Testes | 1275, mais o autoteste do binário congelado |
| 101 | ADR para decisões relevantes | 8 ADRs |

## Implementado em parte

| § | Estado real |
|---|---|
| 10 | **Top bar** existe, mas só com identidade, sessão e idioma. Falta pesquisa, notificações e seletor de contexto |
| 25 | **Visualization Engine**: há linhas, barras e KPI. Faltam os restantes tipos |
| 44 | **Multiempresa**: a estrutura suporta várias raízes (uma empresa é uma raiz), mas **não há isolamento** — quem tem `tarefas.ver_todas` vê todas as raízes, e os dados de plugin não têm noção de inquilino |
| 56–58 | **Estados**: há vazio e erro em vários sítios, mas não é sistemático |
| 60 | **Acessibilidade**: contraste medido e garantido por teste. Navegação por teclado **não verificada** |
| 36 | **ERP modular**: a infraestrutura está feita e provada por um módulo (Estoque). Faltam os outros |

## Não implementado

Por ordem do plano: sidebar (§6–7), Command Palette (§12), dashboards por
perfil (§16–18), Dashboard Builder (§19), Widget System (§20), grid (§21),
filtros globais (§22), drill-down e drill-through (§23–24), Data Science Lab
(§29–32), BI Center e camada analítica separada (§33–34), Report Builder
(§78), Notification Center (§42), gestão documental (§48), DataTable
empresarial (§55), workers fora da UI (§59), atalhos (§61), Copilot e agentes
(§62–66), Licensing (§69), API (§71), Command Center (§80).

## Não validado

Coisas que existem mas nunca foram medidas — e que por isso **não devem ser
declaradas prontas**:

- **comportamento em 1366×768** (§81). A janela abre a 1180×740 com mínimo de
  940×620; ninguém verificou o que acontece abaixo disso;
- **DPI scaling** (§82) em ecrãs a 125% e 150%;
- **navegação só por teclado** (§60) em qualquer ecrã;
- **desempenho** (§68) — não há medição de arranque, memória, ou tempo de
  desenho do painel. A regra 68 do próprio plano diz "não otimizar sem medir";
  a consequência simétrica é não afirmar que está rápido sem medir.

---

## O desvio que proponho ao plano

O plano manda implementar os módulos ERP (§36) e os dashboards especializados
(§16–18). **A recomendação final do próprio plano contradiz isso**, e tem
razão: primeiro o DNA — Core, dados, eventos, plugins, serviços, UI, analytics,
segurança — e só depois os módulos.

Essa parte está feita. O que falta do DNA, e que bloqueia tudo o resto, é a
**concha de navegação**: sem sidebar, sem Command Palette e sem um sítio onde
um módulo se registe para aparecer, cada módulo novo volta a ser uma aba
acrescentada à mão em `gui.py` — e a `gui.py` passa a saber de todos eles, que
é o monólito de volta pela porta das traseiras.

Por isso a ordem é:

1. **Concha de navegação** (§6, 7, 10, 12) — sidebar, top bar, Command Palette,
   e o registo por onde um módulo declara onde vive. Um plugin passa a poder
   pôr-se na barra lateral sem que a aplicação o conheça.
2. **Dashboard Engine** (§19–21) — widgets registados, grelha, filtros.
3. **Isolamento entre empresas** (§44) — o único cujo custo cresce com a espera.
4. O resto, um de cada vez, classificado antes de escrito (§37).

O que **não** proponho fazer tão cedo, e porquê: Copilot e agentes (§62–66)
precisam de um fornecedor de LLM — rede, chave, custo por pergunta e dados da
empresa a sair da máquina. É uma decisão comercial e de privacidade antes de
ser técnica. Licensing (§69) espera por haver módulos que valha a pena
licenciar. API (§71) espera por um consumidor.
