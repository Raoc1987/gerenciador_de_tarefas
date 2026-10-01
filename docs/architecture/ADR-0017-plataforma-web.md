# ADR-0017 — A plataforma passa a ser web, e a autoridade passa para a base de dados

Data: 2026-10-01 · Estado: aceite

## Contexto

Até aqui, o produto foi uma aplicação de secretária: Python com a biblioteca
padrão, Tkinter e SQLite, instalada máquina a máquina. O
[MANUTENCAO.md](../MANUTENCAO.md) dizia-o sem rodeios: *"não há servidor, API
nem telemetria … introduzir isso seria mudar o produto, não fazer-lhe
manutenção"*.

É exatamente isso que se decidiu fazer. O objetivo passou a ser um produto
para o dia a dia de **empresas** — equipas que trabalham ao mesmo tempo, de
vários dispositivos, e que precisam de ver o trabalho umas das outras em
tempo real. Isso não se resolve numa aplicação que vive num só computador:

- **duas pessoas não partilham uma base SQLite** num disco local;
- o isolamento entre empresas do desktop (ADR-0011, 0012, 0015) é feito pela
  aplicação — quem tem o ficheiro `tarefas.db` tem tudo;
- o Tk 8.6 não chega aos leitores de ecrã (ADR-0016), e não há nada a fazer
  dentro do Tk para o mudar.

A alternativa de pôr uma API por cima do núcleo Python e manter o desktop
como cliente foi considerada e posta de lado: ficavam dois clientes para
manter, e a regra de segurança continuaria a viver no código da aplicação.

## Decisão

**O produto passa a ser uma plataforma web**, em `web/` neste repositório,
com o mesmo stack que já usamos em produção noutros projetos:

| Camada | Escolha |
|---|---|
| Interface e servidor | Next.js 16 (App Router, Server Components, Server Actions), React 19, TypeScript estrito |
| Estilo | Tailwind CSS 4, tokens em `app/globals.css`, modo claro e escuro |
| Dados, contas e tempo real | Supabase: Postgres, Auth e Realtime |
| Alojamento | Vercel (a aplicação) e Supabase (a base) |

E a decisão que importa mais do que o stack: **a autoridade é a base de
dados.** Quem vê que tarefa, quem atribui a quem, quem gere quem, a
segregação de funções e a imutabilidade da auditoria são regras do Postgres —
RLS, funções `security definer` e gatilhos em `supabase/migrations/`. A
interface esconde o que não se pode fazer (`web/lib/dominio/papeis.ts`), mas
não decide nada: um pedido feito à mão à API recebe a mesma recusa que um
clique. Não há, de propósito, nenhum uso da chave de serviço na aplicação.

O que se portou do desktop, e de onde:

| Regra | Desktop | Web |
|---|---|---|
| Papéis | `core/permissoes.py` | enum `papel` + `proprietario`, que um SaaS precisa |
| Quem vê que tarefas | `tarefas_servico.py` (`TAREFAS_VER_TODAS`) | policy `tarefas_ler` |
| Segregação de funções | ADR-0007 | gatilho `antes_de_gravar_tarefa` |
| Isolamento entre empresas | ADR-0011, 0012, 0015 | RLS em todas as tabelas |
| Auditoria com empresa do momento | ADR-0015 | `auditoria` + gatilhos; imutável |
| Indicadores do que se pode ver | `analitica/` | `indicadores_painel`, `security invoker` |
| Paleta de comandos | ADR-0009 (`Ctrl+K`) | `components/paleta-comandos.tsx` |
| Gráficos sem biblioteca | ADR-0002 | `components/graficos.tsx`, SVG à mão |

## Como se prova

`supabase/tests/correr.sh` levanta um Postgres efémero, aplica **as
migrações reais** e corre os testes em `supabase/tests/NN_*.sql` — sem Docker
nem npm, só com os binários do Postgres. Cada regra da tabela acima tem
testes dos dois lados: o que deve passar e o que deve ser recusado, **com o
motivo da recusa verificado** (uma recusa por erro de sintaxe não conta).

O shim (`00_shim_supabase.sql`) só cria o que o Supabase traz e as migrações
não: o schema `auth`, os papéis `anon`/`authenticated` e a publicação do
Realtime. Não é o Supabase: valida a lógica SQL e a RLS, não a plataforma.

## Consequências

- **O desktop congela.** Fica em `src/` com os seus 1438 testes, recebe
  correções de segurança e de perda de dados, e não recebe funcionalidades.
  Quem o usa continua a poder usá-lo; o caminho de migração dos dados para a
  web é trabalho por fazer (importação do `tarefas.db`).
- **O ADR-0002 deixa de valer para o produto web.** "Só a biblioteca padrão"
  era a resposta certa para um executável instalado máquina a máquina; numa
  aplicação servida, as dependências são a forma normal de não reescrever um
  cliente de autenticação. Continua a valer para `src/`, e o espírito fica:
  cada dependência entra com uma razão, e os gráficos continuam a ser SVG
  nosso.
- **Passa a haver servidor e dados de terceiros.** O que o MANUTENCAO.md
  dizia não existir — operação, cópias de segurança da base, RGPD/LGPD,
  incidentes — passa a existir, e esse documento tem de o cobrir antes do
  primeiro cliente real.
- **A primeira versão é só português.** O desktop tem três idiomas; a web
  guarda os textos em constantes (`ROTULO_*`) para a tradução entrar sem
  reescrever páginas, mas ainda não a tem.
- **O "hoje" é de quem pergunta.** `indicadores_painel` recebe `p_hoje` no
  fuso de quem usa (`America/Sao_Paulo` por omissão). A série diária ainda
  agrupa por dia UTC; com equipas noutros fusos, isso tem de passar a ser
  definição da empresa.
- **Fica por fazer**, por ordem: Copiloto (Claude) para criar e priorizar
  tarefas em linguagem natural; notificações (email e push); importação do
  desktop; relatórios exportáveis; dashboards por perfil; os módulos ERP do
  plano, agora como esquemas próprios com a mesma disciplina de RLS.
