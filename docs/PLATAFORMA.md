# Auditoria do plano de plataforma — o que existe, o que falta

Data: 2026-09-19 · Atualizado a cada etapa concluída

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
| 42 | **Notification Center** — caixa por pessoa, sino na barra de topo, centro onde se lê | `src/notificacoes.py`, `src/notificacoes_ui.py`, [ADR-0013](architecture/ADR-0013-caixa-de-notificacoes.md) |
| 84–85 | Instalador; dados fora de `Program Files` | Inno Setup; `core/paths.py` |
| 86 | Testes | 1400, mais o autoteste do binário congelado |
| 101 | ADR para decisões relevantes | 13 ADRs |
| 6–7, 10, 12 | Sidebar com grupos, barra de topo, **Command Palette** (`Ctrl+K`) | `src/navegacao/`, ADR-0009 |
| 44 | **Isolamento entre empresas** — para as tarefas | `tarefas_servico.py`, ADR-0011 |

## Implementado em parte

| § | Estado real |
|---|---|
| 10 | **Top bar** com nome da secção, pesquisa, Command Palette, **notificações** e sessão. Falta o seletor de contexto |
| 19 | **Dashboard Builder** (escolher e guardar arranjos por pessoa) não existe |
| 25 | **Visualization Engine**: há linhas, barras e KPI. Faltam os restantes tipos |
| 44 | **Multiempresa**: tarefas isoladas ([ADR-0011](architecture/ADR-0011-isolamento-entre-empresas.md)) e **dados de módulo também** ([ADR-0012](architecture/ADR-0012-dados-de-modulo-por-empresa.md)), com o Estoque migrado como exemplo. Falta: **seletor de empresa** na interface, e auditoria/contas/configuração continuam por isolar |
| 56–58 | **Estados**: há vazio e erro em vários sítios, mas não é sistemático |
| 59 | **Trabalho fora da linha da interface**: não existe. Com 20 000 tarefas, atualizar o painel demora 229 ms e bloqueia a janela — medido. Abaixo de 5 000 não se nota |
| 60 | **Acessibilidade**: contraste medido e garantido por teste, navegação por teclado e visibilidade do foco **medidas** ([MEDICOES.md](MEDICOES.md)). Falta a passagem com leitor de ecrã |
| 36 | **ERP modular**: a infraestrutura está feita e provada por um módulo (Estoque). Faltam os outros |

## Não implementado

Por ordem do plano: dashboards por perfil (§16–18), drill-down e
drill-through (§23–24), Data Science Lab (§29–32), BI Center e camada
analítica separada (§33–34), Report Builder (§78),
gestão documental (§48), DataTable empresarial (§55), workers fora da UI
(§59), atalhos além de `Ctrl+F` e `Ctrl+K` (§61), Copilot e agentes (§62–66),
Licensing (§69), API (§71), Command Center (§80).

## Medido — ver [MEDICOES.md](MEDICOES.md)

O que estava aqui como "não validado" foi medido a 2026-09-20. Os números,
o método e as duas armadilhas que quase estragaram as medições estão no
documento; o resumo é este:

- **1366×768 (§81) e DPI a 125% e 150% (§82)**: a aplicação mostra tudo nas
  três escalas. Validado;
- **navegação por teclado (§60)**: todos os controlos visíveis se alcançam
  com Tab (10 no painel, 15 nas tarefas), e o foco vê-se — medido a contar
  píxeis, não a olhar;
- **desempenho (§68)**: arranque do executável em 1,7 s; 53 MB de memória;
  o painel atualiza em 66 ms com 5 000 tarefas. **Não há nada para otimizar**,
  e agora há um número para o dizer.

**A medição encontrou dois defeitos, ambos corrigidos**, e nenhum deles dava
erro: o painel não tinha deslocamento vertical — a 940×620, que era o mínimo
que a aplicação declarava, a caixa "Análise" era **inalcançável** — e o
tamanho mínimo era em píxeis, pelo que a 150% a barra de topo se sobrepunha a
si própria e o seletor de idioma desaparecia sem aviso.

## Continua por validar

- **leitor de ecrã**: os controlos alcançam-se e o foco vê-se, mas ninguém
  verificou o que é **anunciado**;
- **escalas acima de 150%** e dois monitores com escalas diferentes;
- **desempenho do executável congelado sob carga** — só o arranque foi medido
  congelado.

---

## O desvio que proponho ao plano

O plano manda implementar os módulos ERP (§36) e os dashboards especializados
(§16–18). **A recomendação final do próprio plano contradiz isso**, e tem
razão: primeiro o DNA — Core, dados, eventos, plugins, serviços, UI, analytics,
segurança — e só depois os módulos.

Essa parte está feita, e a ordem seguida foi esta:

1. ~~**Design System**~~ — feito (ADR-0008). Tudo o que viesse depois herdava
   o aspeto sem fazer nada.
2. ~~**Concha de navegação**~~ (§6, 7, 10, 12) — feito (ADR-0009). Um módulo
   declara onde vive, em vez de ser uma linha à mão em `gui.py`.
3. **Dashboard Engine** (§19–22) — em revisão. Um módulo põe um gráfico no
   painel, e não só um número.
4. ~~**Isolamento entre empresas**~~ (§44) — feito **para as tarefas**
   (ADR-0011). **Não** para os dados dos plugins, que é a peça seguinte e
   maior: mexe no contrato.
5. O resto, um de cada vez, classificado antes de escrito (§37).

**A seguir**, por ordem de valor sobre custo:

- ~~**isolamento dos dados de plugin por empresa**~~ — feito (ADR-0012);
- ~~**Notification Center**~~ (§42) — feito (ADR-0013). Fechar a cadeia
  obrigou a corrigir a montante um defeito **medido**: a memória da vigilância
  era da instalação e não de quem foi avisado, e com duas empresas quem
  entrasse a seguir anunciava `analise.resolvido` por um problema que
  continuava por resolver;
- ~~**medir o que nunca foi medido**~~ — feito ([MEDICOES.md](MEDICOES.md)).
  O que se segue está em aberto de propósito: o que resta da lista de baixo
  tem, cada item, uma condição escrita para valer a pena. Quando nenhuma
  está cumprida, a resposta certa é consolidar, não abrir outra frente.

  **medir o que nunca foi medido** (§68, §81, §82) — desempenho, 1366×768,
  DPI a 125%, navegação por teclado. A regra 68 do plano diz "não otimizar sem
  medir"; a consequência simétrica é não afirmar que está bom sem medir.

O que **não** proponho fazer tão cedo, e porquê: Copilot e agentes (§62–66)
precisam de um fornecedor de LLM — rede, chave, custo por pergunta e dados da
empresa a sair da máquina. É uma decisão comercial e de privacidade antes de
ser técnica. Licensing (§69) espera por haver módulos que valha a pena
licenciar. API (§71) espera por um consumidor.
