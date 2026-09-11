# Classificação das funcionalidades

Aplicação da regra do [ADR-0004](ADR-0004-classificacao-obrigatoria.md): nada
se escreve antes de se saber **o que é** e **onde vive**.

Categorias: **Core** (todos precisam) · **Service** (transversal, sem
interface) · **Module** (domínio de negócio, como plugin) · **Plugin**
(opcional) · **Agent** (decide) · **Skill** (procedimento de um agente) ·
**Constraint** (restrição de desenho, não é funcionalidade).

## O que já existe

| Peça | Categoria | Onde |
|---|---|---|
| Versão, caminhos, config, log | Core | `src/core/` |
| Barramento de eventos | Core | `core/eventos.py` |
| Permissões (RBAC) | Core | `core/permissoes.py` |
| Funcionalidades da instalacao | Core | `core/funcionalidades.py` |
| Contas e autenticação | Core | `core/utilizadores.py`, `core/seguranca.py` |
| Auditoria | Core | `core/auditoria.py` |
| Estrutura da organizacao | Core | `core/organizacao.py` |
| Copia de seguranca e restauro | Core | `core/backup.py` |
| Visibilidade por unidade | Service | `src/tarefas_servico.py` |
| Plugin Engine | Core | `core/plugin_*.py` |
| SDK: permissões declaradas e dados próprios | Core (contrato) | `core/plugin_api.py`, `core/plugin_dados.py` |
| Persistência | Infra | `src/database.py` |
| Regra de quem vê que tarefas | Service | `src/tarefas_servico.py` |
| Análise (métricas, séries, insights) | Service | `src/analytics/` |
| Relatórios e exportação | Service | `src/reporting/` |
| Gráficos | Service (UI) | `src/widgets/` |
| Interface | UI | `src/*_ui.py`, `gui.py` |
| Calendar Integration | Plugin | `plugins/available/calendar/` |
| Verificação de atualizações | Plugin | `plugins/available/atualizacoes/` |

## O que foi proposto

Ordenado por **valor sobre custo**, não pela ordem em que foi proposto.

### Faz-se a seguir

| # | Bloco | Categoria | Porquê agora | Depende de |
|---|---|---|---|---|
| 3 | ABAC (regras por atributo) | **Core** | O caso que mais pesava — "o gestor vê o seu departamento" — já está feito com a hierarquia. O que falta do ABAC é o caso geral: regras por atributo arbitrário | hierarquia |
| 7 | Workflow Engine | **Service** | O diferencial que nomeou, e o barramento de eventos já dá a base. Nada de novo é preciso | eventos |
| 4 | Auditoria com antes/depois | Core (extensão) | A trilha existe; falta o valor anterior e o novo | — |

### Faz-se depois, por esta ordem

| # | Bloco | Categoria | Nota honesta |
|---|---|---|---|
| 5 | KPI Engine (indicadores declarativos) | **Service** | Bom desenho. Só compensa quando houver mais do que um domínio a medir |
| 1 | Decision Engine (insight → recomendação → ação) | **Service** | Metade existe (insights). A outra metade *é* o Workflow: fazer os dois juntos |
| 12 | Pesquisa global | **Core** (registo) + UI | Cada módulo regista o que sabe pesquisar. Barato e muito visível |
| 22 | Entitlement engine | **Core** | Licenciamento a sério. As feature flags já estão feitas; falta haver módulos que valha a pena licenciar |
| 8 | Import Wizard | **Service** + UI | Muito útil a PMEs. Independente de tudo o resto |
| 6 | OKR / metas | **Module** | Liga tarefas à estratégia; precisa do KPI Engine para não ser uma lista bonita |
| 11 | Gestão documental | **Module** | Precisa de armazenamento de ficheiros no SDK, além de dados |
| 16 / 17 | Previsão e anomalias avançadas | **Service** ou **Plugin** | O básico já existe (regressão, MAD). Modelos pesados entram como plugin com as suas dependências |
| 10 | Integrações (Calendar, Outlook, ERP…) | **Plugin**, uma a uma | Nunca no Core. Cada integração é um plugin, e morre sozinha se falhar |
| 15 | Laboratório de dados | **Module** | O caso perfeito para o escape do ADR-0002: traz numpy/pandas como dependência **sua** |
| 23 | Telemetria | **Service**, opt-in | Só faz sentido com utilizadores reais para medir |

### Fica em espera — e porquê

| # | Bloco | Categoria | A razão de esperar |
|---|---|---|---|
| 9 | API | **Service** | Uma API precisa de um consumidor. Hoje não há nenhum, e uma API sem cliente envelhece mal. O que interessava já está feito: a lógica de negócio **não vive na interface**, por isso a API será um invólucro, não uma reescrita |
| 19 | Cloud | Constraint | O que bloquearia a nuvem era lógica dentro da GUI e SQL espalhado. Nada disso existe. O passo real, quando chegar, é trocar `database.py` por um porto de repositório — uma peça, não o produto |
| 13 | Copiloto empresarial | **Agent** (plugin) | Precisa de um fornecedor de LLM: rede, chave, custo por pergunta e dados da empresa a sair da máquina. É uma decisão comercial e de privacidade, não técnica. Como plugin opt-in, é viável; no Core, seria impor a todos os clientes uma dependência externa |
| 14 | Orquestração de agentes | **Agent** | Só depois de **um** agente provar que vale a pena. Uma hierarquia de agentes sem um caso real é organograma, não software |

### Não são funcionalidades

| # | Bloco | O que é | Estado |
|---|---|---|---|
| 18 | Multiplataforma | Constraint | Já respeitada: só Tkinter e `pathlib`. O que prende ao Windows é o **instalador**, não o código. Correr em Linux hoje precisa de `python3-tk` e mais nada — a suíte de testes já corre lá |
| 24 | RGPD / privacidade desde o início | Constraint | Parcialmente cumprida: a auditoria não guarda o conteúdo das tarefas, tem retenção explícita, e o plugin de atualizações pede consentimento antes de contactar a rede. Falta: exportar e apagar os dados de uma pessoa |

## Duas coisas em que discordo da proposta

**Renomear o projeto agora.** O nome interno `GerenciadorDeTarefas` é a
identidade dos dados instalados: é o `AppId` do instalador, a pasta em
`%APPDATA%` e a chave de desinstalação no registo. Mudá-lo **órfã os dados de
quem já instalou** e obriga a escrever uma migração de pastas só para mudar
uma etiqueta. O enquadramento de plataforma que propôs muda como desenhamos —
e isso está nestes documentos — sem custar nada a quem já usa o programa. O
nome comercial pode ser outro sem tocar no `AppId`.

**"API desde cedo".** Concordo com a intenção, discordo do timing. O valor que
queria — não prender a lógica à interface — já está garantido e verificado por
testes de arquitetura. Escrever os *endpoints* antes de existir um consumidor
produz uma superfície pública que ninguém usa e que passa a ser preciso manter
compatível.
