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
| Auditoria, com antes/depois | Core | `core/auditoria.py` |
| Estrutura da organizacao | Core | `core/organizacao.py` |
| Copia de seguranca e restauro | Core | `core/backup.py` |
| Visibilidade por unidade | Service | `src/tarefas_servico.py` |
| Plugin Engine | Core | `core/plugin_*.py` |
| Posse dos plugins (embutido vs. do utilizador) | Core | `core/plugin_manager.py`, `core/plugin_registry.py` |
| SDK: permissões declaradas e dados próprios | Core (contrato) | `core/plugin_api.py`, `core/plugin_dados.py` |
| Persistência | Infra | `src/banco_de_dados.py` |
| Regra de quem vê que tarefas | Service | `src/tarefas_servico.py` |
| Análise (métricas, séries, insights) | Service | `src/analitica/` |
| Relatórios e exportação | Service | `src/relatorios/` |
| **Automação por regras** | **Service** | `src/regras/` |
| **Pesquisa global** | **Service** | `src/pesquisa.py` |
| **Indicadores declarados** | **Service** | `src/indicadores.py` |
| **Importação de ficheiros** | **Service** | `src/importacao/` |
| **Vigilância (análise -> alerta)** | **Service** | `src/alertas.py` |
| **Caixa de notificações (alerta -> pessoa)** | **Service** | `src/notificacoes.py` |
| Ações que a aplicação oferece às regras | Ligação | `src/automacoes.py` |
| Tela das automações | UI | `src/regras_ui.py` |
| Sino e centro de notificações | UI | `src/notificacoes_ui.py` |
| Gráficos | Service (UI) | `src/componentes/` |
| **Aparência (tokens e tema)** | **Service (UI)** | `src/aparencia/` |
| **Concha de navegação (sidebar, topbar)** | **Service (UI)** | `src/navegacao/` |
| **Motor do painel (widgets, grelha, filtros)** | **Service (UI)** | `src/painel/` |
| Interface | UI | `src/*_ui.py`, `gui.py` |
| Calendar Integration | Plugin | `plugins/available/calendar/` |
| Verificação de atualizações | Plugin | `plugins/available/atualizacoes/` |
| **Estoque** (inventário) | **Module** | `plugins/available/estoque/` |
| **Calculadora** (simples, científica, conversões, financeira) | **Plugin** | `plugins/available/calculadora/` |
| Permissões trazidas por um módulo | Core (contrato) | `core/permissoes.py`, `core/plugin_api.py` |
| **Políticas por atributo (ABAC)** | **Core (contrato)** | `core/permissoes.py`, `src/politicas_incluidas.py` |

## O que foi proposto

Ordenado por **valor sobre custo**, não pela ordem em que foi proposto.

### Faz-se a seguir

**A fila está vazia.** Não é um convite a inventar: o que resta está na
lista de baixo, e cada item tem escrito o que falta acontecer antes de
valer a pena. Quando nada tem a condição cumprida, a resposta certa é
consolidar o que existe, não abrir mais uma frente.

| # | Bloco | Categoria | Porquê agora | Depende de |
|---|---|---|---|---|
| 3 | ABAC (regras por atributo) | **feito** | Uma política decide sobre o objeto, não só sobre o verbo, e **só pode recusar** — é o que torna seguro um plugin registar uma. Entrou com uma regra a sério a usá-la (segregação de funções), para não ser um motor à espera de utilizador. Ver ADR-0007 | hierarquia |

### Faz-se depois, por esta ordem

| # | Bloco | Categoria | Nota honesta |
|---|---|---|---|
| 5 | KPI Engine (indicadores declarativos) | **feito** | A condição cumpriu-se: com o Estoque, passou a haver mais do que um domínio a medir |
| 1 | Decision Engine — ~~insight → recomendação → ação~~ | **feito** | A cadeia está fechada: a análise publica alertas, uma regra age. O que falta é a recomendação ser gerada em vez de escrita à mão na regra |
| 12 | Pesquisa global | ~~Core~~ → **Service** | Feito. A classificação estava errada: um registo destes vive bem fora do núcleo, como o das ações já tinha mostrado, e o núcleo não precisava de crescer para isto existir |
| 22 | Entitlement engine | **Core** | Licenciamento a sério. As feature flags já estão feitas; falta haver módulos que valha a pena licenciar |
| 8 | Import Wizard | **feito** | CSV e XLSX, com deteção de codificação e separador, mapeamento de colunas e pré-visualização antes de escrever |
| 6 | OKR / metas | **Module** | Liga tarefas à estratégia; precisa do KPI Engine para não ser uma lista bonita |
| 11 | Gestão documental | **Module** | Precisa de armazenamento de ficheiros no SDK, além de dados |
| 16 / 17 | Previsão e anomalias avançadas | **Service** ou **Plugin** | O básico já existe (regressão, MAD). Modelos pesados entram como plugin com as suas dependências |
| 10 | Integrações (Calendar, Outlook, ERP…) | **Plugin**, uma a uma | Nunca no Core. Cada integração é um plugin, e morre sozinha se falhar |
| 15 | Laboratório de dados | **Module** | O caso perfeito para o escape do ADR-0002: traz numpy/pandas como dependência **sua** |
| 23 | Telemetria | **Service**, opt-in | Só faz sentido com utilizadores reais para medir |

### O que o primeiro módulo de negócio ensinou

O **Estoque** foi escrito para testar a arquitetura, não para encher o
produto. Correu bem em quase tudo: dados próprios, eventos próprios, aba
própria, zero linhas no núcleo a saber que ele existe, e **nada pedido ao
núcleo** — não toca em tarefas.

Falhou num ponto, e valeu a pena: um módulo de negócio tem permissões do seu
domínio (`estoque.ler`, `estoque.escrever`) que o núcleo não pode conhecer, e
o contrato só aceitava as permissões do núcleo. A resposta certa era melhorar
o contrato, não abrir uma exceção (ADR-0004). Um módulo passa a poder
declarar permissões **no seu próprio espaço de nomes** — o pior que consegue
conceder é acesso aos seus próprios dados.

### Porque é que a caixa de notificações é Service e não Core

As quatro perguntas do ADR-0004, respondidas antes de escrever: nenhum módulo
precisa dela para funcionar (não é Core); o produto funciona sem ela — os
alertas continuavam a ser publicados e as regras a agir (não é Core); não
decide nada, entrega (não é Agent); e não tem domínio de negócio nem dados de
ninguém, só o que outros anunciaram (não é Module).

Fica ao lado da vigilância, dos indicadores e da pesquisa: um registo
transversal, sem interface, que liga duas peças que não se conhecem. O núcleo
não cresceu para isto existir, que é a mesma resposta que a pesquisa global já
tinha dado quando a classificação dela estava errada.

### Porque é que a Calculadora é Plugin e não Module

As quatro perguntas do ADR-0004, respondidas antes de escrever: nenhum módulo
precisa dela (não é Core); o produto funciona sem ela (não é Core); só calcula,
não decide (não é Agent); e não tem domínio de negócio nem dados de ninguém —
é uma ferramenta, não um Module como o Estoque.

Não pede **nenhuma** permissão e não traz nenhuma. A única coisa que guarda é
a preferência de graus/radianos, na sua própria configuração. Desinstalar não
deixa nada.

Duas fronteiras deliberadas: **sem `eval()`**, porque uma caixa de texto ligada
ao `eval` numa aplicação com dados de empresa é um buraco por onde entra tudo;
e **sem moedas**, porque taxas de câmbio exigem rede e um fornecedor, e uma
taxa gravada no código daria um número errado com ar de certo.

### Fica em espera — e porquê

| # | Bloco | Categoria | A razão de esperar |
|---|---|---|---|
| 9 | API | **Service** | Uma API precisa de um consumidor. Hoje não há nenhum, e uma API sem cliente envelhece mal. O que interessava já está feito: a lógica de negócio **não vive na interface**, por isso a API será um invólucro, não uma reescrita |
| 19 | Cloud | Constraint | O que bloquearia a nuvem era lógica dentro da GUI e SQL espalhado. Nada disso existe. O passo real, quando chegar, é trocar `banco_de_dados.py` por um porto de repositório — uma peça, não o produto |
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
