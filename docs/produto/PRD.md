# PRD — Gerenciador de Tarefas Enterprise

Especificação técnica e de produto da plataforma que consolida o que o
ClickUp faz bem (hierarquia e granularidade), o Notion (bases relacionais e
documentos), o Jira e o Asana (governança, dependências em escala) e o Motion
(agenda calculada), sem herdar o que cada um faz mal.

Data: 2026-10-03 · Estado: proposta para aprovação · Dono: produto e
arquitetura · Decisões já tomadas e não reabertas aqui: ADR-0017 a ADR-0022.

Como ler: cada secção separa **o que existe hoje** (com o ficheiro onde vive),
**o que se constrói** e **o que se recusa e porquê**. Os números de desempenho
são objetivos de serviço com o método de medição; não são promessas sem
instrumento.

---

## 1. Manifesto de produto e modelo de dados core

### 1.1 Manifesto

1. **Quem decide é a base de dados.** Permissões, segregação de funções,
   auditoria e limites vivem em Postgres (RLS, funções, gatilhos). A interface
   esconde; a IA propõe; a base recusa. Esta regra (ADR-0017) é o que permite
   abrir a plataforma a integrações, agentes e clientes offline sem abrir a
   segurança: todos chegam à mesma porta.
2. **A IA propõe, as pessoas aplicam — até a empresa decidir o contrário,
   explicitamente e por âmbito.** Autonomia é uma definição auditada, não um
   efeito secundário de um prompt (secção 2.5).
3. **Uma entidade, muitas lentes.** Tarefa, subtarefa, documento, marco,
   objetivo, projeto e portfólio são o mesmo tipo de nó. O que muda é o
   esquema de campos e a lente com que se olha.
4. **Densidade sem caos.** Cada pessoa vê o que a sua função precisa naquele
   momento; a profundidade está a um gesto de distância, nunca à frente.
5. **Rápido é uma funcionalidade.** Orçamentos de latência medidos no CI e em
   produção; uma regressão de desempenho falha como um teste.
6. **Portugal primeiro, mundo a seguir.** Fuso, idioma e RGPD por omissão
   (ADR-0022); tudo o que é local (fuso, feriados, moeda) é dado da empresa.

### 1.2 O que existe hoje

| Peça | Onde | Notas |
|---|---|---|
| Empresas, membros, papéis, convites | `supabase/migrations/20261001000000_nucleo.sql` | papéis leitor → proprietário; RLS em tudo |
| Tarefas, comentários, auditoria imutável | `…000100_tarefas.sql` | auditoria com empresa do momento |
| Copiloto (propõe, não escreve) | `…20261002000000_copiloto.sql`, `web/lib/copiloto/` | ADR-0018 |
| Fila de emails decidida na base | `…20261002010000_notificacoes_email.sql` | ADR-0019 |
| Importação do desktop | `…20261002020000_importacao_desktop.sql` | ADR-0020 |
| Postura de segurança como teste | `supabase/tests/80_postura_seguranca.sql` | nenhuma função aberta a `anon` |

A tabela `tarefas` é plana. O modelo abaixo generaliza-a sem a deitar fora:
`tarefas` passa a ser uma vista de compatibilidade sobre `nos` durante a
transição (secção 5.4).

### 1.3 O nó: uma entidade para tudo

```sql
create table nos (
  id           uuid primary key default gen_random_uuid(),   -- UUIDv7 quando o PG 18 o der nativo
  empresa_id   uuid not null references empresas on delete cascade,
  tipo_id      uuid not null references tipos_no,              -- tarefa, documento, marco, objetivo, projeto…
  pai_id       uuid references nos on delete cascade,
  caminho      ltree not null,                                -- materializado: <raiz>.<…>.<id>
  profundidade smallint not null,
  ordem        double precision not null,                     -- fracionária, como o quadro de hoje
  titulo       text not null,
  estado_id    uuid references estados,                       -- máquina de estados por tipo
  responsavel_id uuid references auth.users,
  inicio       timestamptz, fim timestamptz, esforco_min integer,
  campos       jsonb not null default '{}',                   -- valores dos campos personalizados
  derivados    jsonb not null default '{}',                   -- rollups e fórmulas guardadas
  versao       bigint not null default 1,                     -- concorrência otimista e sync
  criado_por   uuid not null default auth.uid(),
  criado_em    timestamptz not null default now(),
  alterado_em  timestamptz not null default now(),
  apagado_em   timestamptz                                     -- apagar é lógico; ver 3.5
) partition by hash (empresa_id);
```

Porque é assim:

- **Um só tipo de linha** dá uma só RLS, uma só auditoria, uma só API e uma
  só sincronização. O custo — consultas que distinguem por tipo — paga-se com
  índices parciais por `tipo_id` nos tipos quentes.
- **Hierarquia infinita com `ltree` + `pai_id`.** O `pai_id` é a verdade; o
  `caminho` é o índice. Subárvores leem-se com `caminho <@ 'a.b'` sobre um
  índice GiST, sem recursão. Mover uma subárvore é um `update` em lote do
  prefixo, feito por uma função que bloqueia a raiz movida (`for update`) para
  não haver dois movimentos cruzados. Ciclos ficam impossíveis por
  construção: a função recusa um destino que esteja dentro do próprio caminho.
- **Partição por empresa** (hash, 32 partições, multiplicável por divisão):
  o isolamento entre clientes é também um isolamento físico de índices e de
  vacuum, e as consultas levam sempre `empresa_id` (a RLS já o exige).
- **`campos` em JSONB, não EAV.** EAV multiplica linhas e junções por dez;
  JSONB guarda o nó numa linha, aceita índices de expressão nos campos quentes
  (`create index … ((campos->>'cliente'))`) e índices GIN para filtros ad hoc.
  A validação de tipo é feita na escrita contra `definicoes_campo`, por um
  gatilho, não confiada ao cliente.
- **`derivados` separado de `campos`**: o que é calculado nunca se confunde
  com o que alguém escreveu, e a auditoria distingue os dois.

Tabelas à volta do nó:

| Tabela | Para quê |
|---|---|
| `tipos_no` | o esquema de cada tipo: campos, estados permitidos, ícone, lente por omissão |
| `definicoes_campo` | nome, tipo (texto, número, data, pessoa, relação, seleção, moeda, fórmula, rollup), validação, quem pode ler/escrever (ver 3.2) |
| `relacoes` | arestas tipadas entre nós: `depende_de` (FS/SS/FF/SF + desfasamento), `bloqueia`, `relaciona`, `duplica`, `pertence_a_objetivo`; índice nos dois sentidos |
| `blocos` | conteúdo de documentos (Notion): árvore de blocos por nó, guardada como estado CRDT (ver 3.6) |
| `eventos` | o diário de tudo o que mudou (substitui e generaliza `auditoria`) |
| `vistas` | lentes guardadas: filtros, agrupamentos, colunas, por pessoa ou partilhadas |

### 1.4 Rollups e fórmulas sem matar a escrita

Um rollup (soma do esforço das subtarefas, % concluído de um projeto, custo
de um portfólio) é um agregado sobre uma subárvore ou sobre relações. Três
regras:

1. **Incremental, nunca recalculado do zero.** Cada escrita num nó gera um
   evento; um trabalhador consome os eventos por empresa, em ordem, e aplica
   deltas aos antepassados (`caminho` dá-os sem recursão). Agregados
   associativos (soma, contagem, mín/máx com contadores) atualizam-se em
   O(profundidade). Não associativos (mediana, percentis) recalculam-se só no
   nó afetado, com teto de tamanho e degradação explícita para "aproximado".
2. **Consistência eventual com prazo.** O rollup traz `derivados._atualizado_em`;
   a interface mostra "a calcular" se passarem mais de 2 s. Objetivo: p99 do
   atraso < 1 s com 10 mil escritas/min por empresa.
3. **Fórmulas são uma linguagem nossa, não `eval`.** Gramática pequena
   (aritmética, datas, texto, condicionais, referências a campos e a
   `pai`/`filhos`/`relacionados`), tipada, sem efeitos, com limite de passos.
   O mesmo avaliador corre em TypeScript (interface, pré-visualização) e em
   PL/pgSQL gerado (fórmulas guardadas), testado com os mesmos casos nos dois
   lados. Fórmulas voláteis (`hoje()`) avaliam-se na leitura; as estáveis
   guardam-se em `derivados`. Dependências entre fórmulas formam um grafo; um
   ciclo é recusado na gravação da definição.

### 1.5 Escala: milhões de nós ativos

| Alavanca | Decisão |
|---|---|
| Leituras quentes | índices parciais por `(empresa_id, responsavel_id) where apagado_em is null and estado não terminal` — "as minhas tarefas" é uma busca de índice |
| Subárvores | GiST em `caminho`; paginação por cursor (`ordem`, `id`), nunca `offset` |
| Escritas | gatilhos curtos e sem rede; tudo o que é caro (rollups, notificações, IA) sai pelo diário de eventos para trabalhadores (padrão outbox, já usado em `emails_pendentes`) |
| Ligações | PgBouncer em modo transação (o "session pooler" do Supabase só para migrações) |
| Leituras analíticas | réplica de leitura + vistas materializadas por empresa, renovadas por evento, para painéis de portfólio |
| Pesquisa | `tsvector` com dicionário português por omissão; pgvector para semelhança semântica (deduplicação de triagem, 2.2) |
| Tempo real | Realtime do Supabase por empresa, filtrado pela RLS; para empresas muito grandes, canal por subárvore |

Medição: um gerador de carga com 5 milhões de nós em 2 000 empresas sintéticas
corre num ambiente efémero (o mesmo Supabase local que o CI já monta, fase 1)
e falha se: abrir "as minhas tarefas" > 50 ms p95 na base, mover uma
subárvore de 10 mil nós > 2 s, atraso de rollup > 1 s p99.

---

## 2. Motor de IA e heurísticas de agendamento

### 2.1 Arquitetura comum

Todos os agentes partilham quatro peças, e nenhum tem atalhos:

- **Identidade própria.** Cada agente corre como um membro técnico da empresa
  (`papel = 'agente'`, com âmbito), e passa pela mesma RLS. Um agente de
  triagem não lê a área de RH porque o seu papel não a lê — não porque o
  prompt lhe pede para não ler.
- **Ferramentas tipadas e só estas.** Leitura pela API normal; escrita só por
  `propor_*` (como o Copiloto de hoje, ADR-0018), que cria propostas
  validadas pelo mesmo código de um formulário.
- **Fila e orçamento.** Cada execução tem custo estimado, limite por empresa
  e por dia (generaliza `copiloto_uso`), e é retomável.
- **Rasto completo.** Entrada, ferramentas chamadas, propostas, decisão humana
  e resultado ficam em `eventos`, ligados à proposta. Sem rasto, não há ação.

Modelos: o mais capaz disponível para raciocínio e planeamento, um rápido
para classificação em volume; escolha por tarefa e por custo, configurável. O
texto que vem de fora (emails, Slack, issues) é **dado não confiável**: entra
delimitado, nunca no prompt de sistema, e nenhuma instrução nele tem
autoridade. Uma proposta que cite uma instrução embutida é marcada para revisão
humana obrigatória.

### 2.2 Camada 1 — Triagem (captura passiva)

Entradas: webhooks do GitHub (issues, PRs, CI), Slack (mensagens marcadas,
reações combinadas), Salesforce (oportunidades em fase X), Figma (comentários
e alterações de estado), email (endereço por projeto), formulários públicos.

Pipeline:

1. **Receber** — cada integração tem uma rota com verificação de assinatura
   sobre os bytes crus e proteção de repetição (janela + identificador).
   Guarda o evento cru em `sinais` (fila na base, como os emails).
2. **Normalizar** — extração determinística primeiro (autor, ligação, título,
   datas explícitas); só o resto vai ao modelo.
3. **Deduplicar** — semelhança por embeddings dentro da empresa e janela de
   tempo; acima do limiar, propõe "juntar ao nó X" em vez de criar.
4. **Estruturar** — o modelo classifica tipo, projeto provável, prioridade,
   responsável sugerido (pela carga, 2.3), prazo inferido com a frase que o
   justifica.
5. **Propor** — uma proposta por sinal, com confiança. Acima de um limiar
   configurado e num âmbito em autonomia L2+ (2.5), aplica-se sozinha e fica
   reversível durante 24 h.

Métrica de qualidade: taxa de propostas aceites sem edição, por integração,
visível ao administrador. Abaixo de 60%, a integração volta a L0
automaticamente e avisa.

### 2.3 Camada 2 — Otimização (CPM e balanceamento)

**Caminho crítico.** O grafo de `relacoes` do tipo `depende_de` de um projeto
é um DAG (ciclos recusados na criação da aresta). O cálculo:

- passagem para a frente (ES/EF) e para trás (LS/LF) em ordem topológica,
  com os quatro tipos de ligação (FS, SS, FF, SF) e desfasamentos;
- durações em **minutos úteis** sobre o calendário da pessoa responsável
  (horário, feriados de Portugal por omissão, ausências);
- folga total e livre por nó; crítico = folga total ≤ 0;
- **incremental**: uma mudança num nó só recalcula o seu fecho para a frente
  e para trás, não o projeto inteiro. Projetos de 10 mil nós recalculam em
  < 100 ms no trabalhador.

**Balanceamento de recursos.** Heurística de escalonamento por regras de
prioridade (série), porque é previsível e explicável:

1. capacidade diária por pessoa (calendário − reuniões − tarefas fixas);
2. ordem de agendamento: menor folga total, depois prioridade, depois prazo;
3. cada tarefa entra no primeiro intervalo em que cabe sem exceder a
   capacidade; se não cabe antes do prazo, marca "em risco" e propõe:
   reatribuir a quem tem folga e competência, partir a tarefa, ou mover o
   prazo — com o impacto no caminho crítico calculado para cada opção.

Recalcula-se a cada evento relevante (mudança de esforço, prazo, ausência,
nova dependência). O resultado não muda dados sozinho: atualiza
`derivados.agenda` e gera propostas. A "agenda calculada" que o Motion vende
é aqui uma lente sobre esses derivados.

Porque não um otimizador exato (MILP/CP-SAT): escalonamento com recursos é
NP-difícil, o tempo é imprevisível e o resultado salta entre execuções. Uma
heurística determinística, explicável numa frase ("entrou aqui porque tem
menos folga"), ganha a confiança da equipa. Fica a porta aberta: para
portfólios grandes, uma passagem noturna com CP-SAT compara e sugere, sem
substituir.

### 2.4 Camada 3 — Automação auto-gerada

Regras escritas por pessoas ("se mudar para Revisão, atribuir ao Rui") são
úteis mas ninguém as escreve. Aqui:

1. **Observar** — mineração de padrões no diário de eventos: sequências que se
   repetem (≥ 5 vezes, ≥ 80% de consistência) entre um estado e uma ação
   humana.
2. **Propor uma regra** — em linguagem declarativa nossa (gatilho, condição,
   ação), mostrada em português ("Quando uma tarefa de Faturação passa a
   Concluída, criar 'Enviar fatura' para a Inês com prazo de 2 dias úteis.
   Aconteceu 14 vezes em 30 dias.").
3. **Simular** — a regra corre em modo sombra sobre os últimos 30 dias de
   eventos: quantas vezes teria disparado, e onde teria divergido do que as
   pessoas fizeram.
4. **Ativar** — só com aprovação de quem administra a área. Corre no
   trabalhador, como o agente, com identidade e rasto; nunca como gatilho
   arbitrário na base.
5. **Vigiar** — uma regra cujas ações são desfeitas por pessoas acima de um
   limiar desliga-se e avisa.

A linguagem das regras não tem ciclos nem chamadas externas arbitrárias; as
ações são as mesmas operações tipadas das ferramentas dos agentes.

### 2.5 Níveis de autonomia

| Nível | O agente… | Exemplo |
|---|---|---|
| L0 | só responde quando perguntado | o Copiloto de hoje |
| L1 | propõe em segundo plano; aplica quem aceitar | triagem a sugerir tarefas |
| L2 | aplica sozinho acima de um limiar de confiança; reversível 24 h | etiquetar, ligar a projeto |
| L3 | aplica sozinho dentro de regras aprovadas | automações da camada 3 |

O nível é por empresa, por área e por tipo de ação, mudado só por quem
administra, e cada mudança fica no diário. Atribuir trabalho a pessoas,
apagar, e qualquer ação com efeito externo (enviar email a cliente) nunca
passam de L1 sem uma decisão explícita.

---

## 3. Segurança, escala e governança enterprise

### 3.1 Matriz

| Ameaça / requisito | Controlo | Onde vive | Prova |
|---|---|---|---|
| Ver dados de outra empresa | RLS por `empresa_id` em todas as tabelas; partição por empresa | Postgres | `supabase/tests/*`, `80_postura_seguranca.sql` |
| Pedido sem sessão | `anon` sem tabelas nem funções | grants + default privileges | teste de postura |
| Papel errado | RBAC por papel na empresa | policies + funções | testes dos dois lados com motivo |
| Atributo sensível (salário, margem) | ABAC por campo (3.2) | `definicoes_campo` + vistas de leitura | testes de mascaramento |
| Agente fora do âmbito | agente é membro com papel e âmbito | RLS | testes por agente |
| Injeção de instruções | texto externo como dado; propostas validadas | trabalhador + `validarProposta` | casos adversariais |
| Integração falsificada | assinatura sobre bytes crus + anti-repetição | rotas de integração | testes com assinatura errada |
| Perda ou adulteração de histórico | diário de eventos só de acréscimo, encadeado por hash | `eventos` | verificação da cadeia |
| Fuga pela chave de serviço | confinada a módulos nomeados, por teste | `web/lib/arquitetura.test.ts` | já existe |
| Redirecionamentos abertos | `caminhoSeguro` com o parser WHATWG | `web/lib/dominio/erros.ts` | já existe |

### 3.2 RBAC + ABAC até ao atributo

Os papéis de hoje (leitor … proprietário) ficam como RBAC de base. Por cima,
políticas por atributo:

```text
política: quem pode LER o campo "margem" em nós do tipo "projeto"
  quando: papel >= gestor  OU  pessoa ∈ nó.equipa_financeira
  e:      empresa.plano permite "campos sensíveis"
```

Implementação, sem confiar no cliente:

- políticas guardadas como dados (`politicas`), compiladas para funções SQL
  `pode_ler_campo(no, campo)` e `pode_escrever_campo(no, campo)`;
- **escrita**: o gatilho de gravação compara `campos` novo com o antigo e
  recusa a alteração de qualquer chave que a pessoa não pode escrever — com o
  nome da chave na mensagem;
- **leitura**: o cliente lê nós por uma vista `nos_visiveis` que aplica
  `jsonb` menos as chaves não autorizadas (`campos - array[…]`). A tabela base
  não é legível diretamente por `authenticated`;
- avaliação com cache por pedido (as políticas não mudam a meio de uma
  transação) para não pagar a função por linha.

### 3.3 Diário de eventos e time-travel

Cada alteração gera um evento: `(empresa, no, versão, ator, tipo, delta,
hash_anterior, hash)`. O hash encadeado por empresa torna a adulteração
detetável (uma verificação noturna percorre a cadeia).

- **Ver o passado**: estado de um nó ou subárvore em `T` = snapshot mais
  próximo antes de `T` + eventos até `T`. Snapshots por subárvore a cada N
  eventos mantêm a reconstrução abaixo de 200 ms.
- **Restaurar**: nunca se reescreve o passado. Restaurar o projeto para `T`
  gera **eventos compensatórios** que levam o estado atual ao de `T`,
  assinados por quem restaurou. Pode-se restaurar o restauro.
- **Depurar**: "o que mudou entre segunda e hoje neste projeto, e quem" é
  uma consulta ao diário, com diferenças campo a campo.
- Retenção configurável por empresa e por plano; os eventos mais antigos que a
  retenção compactam-se num snapshot, e a compactação também fica registada.

A `auditoria` de hoje já guarda antes/depois com empresa do momento e é
imutável; `eventos` generaliza-a com hash e deltas. A migração copia o
histórico existente para o novo diário.

### 3.4 RGPD

Direitos do titular como funções da base, não como scripts manuais: exportar
os dados de uma pessoa (o que ela criou, comentou, o perfil, os eventos onde é
ator) num ficheiro legível por máquina; apagar uma conta substituindo a
autoria por um pseudónimo estável nos eventos (o histórico da empresa
mantém-se coerente, a pessoa deixa de ser identificável). Retenção por
empresa, registo de tratamentos e subcontratantes (Supabase em Frankfurt,
Vercel, Anthropic, Resend) em `docs/MANUTENCAO.md`.

### 3.5 Apagar

Apagar é lógico (`apagado_em`) durante 30 dias, com reposição; depois um
trabalhador apaga fisicamente e regista a compactação. Apagar uma subárvore
é uma operação, com um evento, não N.

### 3.6 Local-first, sincronização e E2EE

- **Sincronização**: cada cliente mantém uma réplica parcial (as subárvores
  que abriu) em IndexedDB, com fila de alterações offline. Campos escalares
  usam **última escrita por campo com relógio de Lamport** (`versao` + ator);
  o conteúdo de documentos (`blocos`) usa CRDT (Yjs), porque texto
  colaborativo não se resolve com "último ganha".
- **A base continua a decidir**: uma alteração offline sincronizada passa
  pela mesma RLS e validação. Se for recusada (a pessoa perdeu o acesso
  entretanto), o cliente mostra a recusa e a versão do servidor; não há
  "fusão" que contorne a permissão.
- **E2EE é opt-in por espaço, com um custo dito**: num espaço cifrado
  ponta-a-ponta, o servidor guarda só texto cifrado nos campos de conteúdo.
  Consequências assumidas: a IA, a pesquisa no servidor, os rollups sobre
  esses campos e as políticas por atributo deixam de funcionar ali.
  Metadados estruturais (pai, estado, datas) ficam em claro para a RLS e o
  agendamento funcionarem. Chaves por espaço, envolvidas pela chave de cada
  membro; sair do espaço roda a chave.

### 3.7 Federação

Para clientes que exigem dados no seu perímetro: a mesma aplicação contra o
Postgres do cliente (as migrações são o contrato), com o plano de controlo
(faturação, atualizações) separado do plano de dados. Sem federação ativa
entre instâncias na primeira versão — partilha entre empresas faz-se por
convites a convidados, que já cabem no modelo.

---

## 4. UX: densidade sem caos

### 4.1 Focalização dinâmica

A mesma base, lentes diferentes. Uma **lente** é: âmbito (que subárvores),
nível de detalhe (macro → micro), campos visíveis, agrupamento, ações
disponíveis.

| Pessoa | Lente por omissão | O que vê | O que não vê (mas alcança) |
|---|---|---|---|
| CEO | Portfólio | objetivos, saúde dos projetos (no prazo / em risco / atrasado), orçamento consumido vs previsto, caminho crítico agregado | tarefas individuais |
| Gestor | Projeto | caminho crítico, carga da equipa, riscos propostos pelo motor | detalhe de cada subtarefa |
| Colaborador | Hoje | as suas tarefas do dia pela agenda calculada, bloqueios, menções | o resto da empresa |
| Financeiro | Custos | campos monetários e rollups de custo | campos que o ABAC esconde |

A lente escolhe-se pelo papel e pelo contexto (abrir um link de projeto entra
na lente de projeto) e muda-se com um gesto (`Ctrl+K` já existe). Nada se
remove da plataforma para simplificar; esconde-se do caminho.

### 4.2 Regras de contenção

1. **Uma ação primária por ecrã.** O resto vai para a paleta de comandos e
   menus contextuais.
2. **Divulgação progressiva**: campos personalizados aparecem quando têm
   valor ou quando se pede; vazios não ocupam espaço.
3. **Densidade escolhida**: confortável / compacta, por pessoa.
4. **Estados vazios que ensinam**, nunca ecrãs em branco.
5. **Sem configuração antes do valor**: um projeto novo funciona com o tipo
   por omissão; o esquema afina-se depois.
6. **Português europeu e acessibilidade como requisito**, não como acabamento:
   contraste AA, navegação por teclado, leitores de ecrã (a lição do ADR-0016).

### 4.3 Orçamentos de desempenho

| Métrica | Objetivo | Medição |
|---|---|---|
| LCP do painel | < 1,5 s em 4G | ensaio no CI com Playwright + throttling |
| INP | < 100 ms | idem, nas ações do quadro |
| Abrir uma lista de 10 mil nós | < 300 ms até interação | virtualização + paginação por cursor |
| JS inicial | < 150 KB comprimido | orçamento no build |

Técnicas: Server Components para o que é leitura; ilhas de cliente só onde
há interação; listas virtualizadas; atualizações otimistas com reconciliação
pela `versao`; prefetch da lente seguinte provável.

---

## 5. Plano de substituição definitivo

### 5.1 Princípios

Ninguém troca de ferramenta num dia. A migração é **contínua, reversível e
medida**: as duas ferramentas convivem, os dados fluem, e o corte é uma
decisão com números à frente.

### 5.2 Conectores

| Origem | Entidades | Como |
|---|---|---|
| Jira | projetos, épicos, issues, subtarefas, sprints, links, comentários, anexos, workflows | API REST + webhooks |
| Asana | portfólios, projetos, secções, tarefas, dependências | API + webhooks |
| ClickUp | espaços, pastas, listas, tarefas, campos personalizados | API + webhooks |
| Notion | bases, páginas, blocos, relações, rollups | API (blocos → `blocos`) |
| Trello, Monday, MS Project (XML), CSV | genérico | ficheiro + mapeamento assistido |
| Desktop do próprio produto | tarefas | já existe (ADR-0020) |

Cada conector mapeia para o modelo de nós: hierarquias de origem viram
caminhos, campos personalizados viram `definicoes_campo` (com o tipo
inferido e confirmado por pessoa), links viram `relacoes`, workflows viram
máquinas de estados de `tipos_no`. A tabela `origens` guarda
(sistema, id externo) ↔ nó — a mesma ideia da coluna `origem` da importação
do desktop, que torna a reimportação idempotente.

### 5.3 Fases de uma migração enterprise

1. **Descoberta** (1 semana): inventário automático (volumes, campos, workflows,
   integrações, permissões) e relatório de compatibilidade com o que não mapeia.
2. **Espelho** (2–6 semanas): importação inicial + sincronização em sentido
   único por webhooks. A plataforma nova é só de leitura para essas áreas; as
   pessoas comparam lado a lado.
3. **Piloto** (2–4 semanas): uma equipa passa a escrever na plataforma nova;
   sincronização de volta para a origem nas áreas que outros ainda usam.
4. **Corte por área**: cada área corta quando os critérios passam — paridade
   de dados (contagens e amostras verificadas), adoção (≥ 80% das ações na
   nova), zero incidentes de perda.
5. **Desligar**: origem em modo de arquivo; exportação final guardada.

Reversão em qualquer fase até ao desligar: a origem continua viva e a
sincronização inversa repõe o que mudou.

### 5.4 A transição do próprio produto

O modelo de nós entra por fatias, sem parar o produto:

1. hierarquia e dependências sobre `tarefas` (subtarefas e `relacoes`) —
   fase 3 deste trabalho;
2. motor CPM e de carga em domínio puro, testado — fase 4;
3. `nos` + `tipos_no` + `definicoes_campo`, com `tarefas` como vista de
   compatibilidade;
4. `eventos` com hash, migrando o histórico da `auditoria`;
5. políticas por atributo; depois agentes de triagem; depois local-first.

Cada fatia é um ADR quando decide algo com custo, e um PR com testes dos dois
lados.

---

## 6. Fora de âmbito (por agora) e porquê

- **Federação ativa entre instâncias**: custo alto, procura não demonstrada.
- **Otimizador exato de escalonamento em tempo real**: imprevisível em tempo
  e resultado; a heurística explicável serve melhor (2.3).
- **IA que escreve sem rasto ou sem papel**: contraria o manifesto 1 e 2.
- **E2EE por omissão**: desligaria IA, pesquisa e políticas; é escolha por
  espaço, com o custo à vista.

## 7. Métricas de sucesso

- Ativação: empresa com ≥ 3 pessoas ativas em 7 dias.
- Retenção semanal de equipas a 8 semanas.
- Aceitação de propostas da IA sem edição ≥ 60%.
- Tarefas concluídas no prazo previsto pelo motor vs prazo inicial.
- Incidentes de segurança: zero de isolamento entre empresas (provado por
  testes a cada PR e por auditoria trimestral).
