# Gerenciador de Tarefas — plataforma web

A plataforma multiempresa do Gerenciador de Tarefas: tarefas em lista e em
quadro com tempo real, equipas com papéis, painel de indicadores e auditoria
imutável. A decisão e o que ela custa estão no
[ADR-0017](../docs/architecture/ADR-0017-plataforma-web.md).

| Camada | Stack |
|---|---|
| Interface e servidor | Next.js 16 (App Router, Server Actions), React 19, TypeScript |
| Estilo | Tailwind CSS 4, modo claro e escuro |
| Dados, contas, tempo real | Supabase (Postgres + RLS, Auth, Realtime) |
| Alojamento | Vercel |

## A regra que organiza tudo

**Quem decide é a base de dados.** Quem vê que tarefa, quem atribui a quem,
quem gere quem, a segregação de funções e a auditoria vivem em
`../supabase/migrations/` — RLS, funções e gatilhos. A interface esconde os
botões que não servem, mas não protege nada. Não há chave de serviço na
aplicação: tudo chega à base como a pessoa em sessão.

## Pôr a correr

1. **Projeto Supabase.** Crie um em [supabase.com](https://supabase.com)
   (região `eu-central-1`, ver ADR-0022). As migrações chegam à produção pelo
   workflow `.github/workflows/base-de-dados.yml`: corre os testes e depois
   `supabase db push`, sempre que `supabase/migrations/` muda na `main` (ou à
   mão, em *Actions → Base de dados — produção → Run workflow*). Para o ligar,
   em *Settings → Environments* crie o ambiente `producao` com o segredo
   `SUPABASE_DB_URL`: a ligação *Session pooler* do projeto (*Connect*), com
   a palavra-passe da base. Os runners do GitHub não têm IPv6, por isso a
   ligação direta não serve.

   Para aplicar à mão, na raiz do repositório:

   ```bash
   npx supabase db push --db-url "<ligação session pooler>"
   ```

   Nunca cole as migrações no editor SQL: ele não regista o que correu, e a
   base deixa de saber que migrações tem.

2. **Auth.** Em *Authentication → URL Configuration*, ponha o URL do site e
   acrescente `<url-do-site>/auth/callback` aos *Redirect URLs*. É para lá
   que vão as ligações de confirmação de conta e de entrada sem
   palavra-passe.

3. **Variáveis.** `cp .env.example .env.local` e preencha com os valores de
   *Project Settings → API*.

4. **Aplicação.**

   ```bash
   npm install
   npm run dev              # http://localhost:3000
   ```

## Copiloto (Claude)

Pergunta-se em linguagem natural ("o que está atrasado e quem precisa de
ajuda?", "cria tarefas a partir desta lista"). O Copiloto **lê com a sessão de
quem pergunta** — vê o mesmo que a pessoa — e **não escreve nada**: propõe, e a
pessoa aplica com um clique, pelo mesmo caminho de um formulário. Decisão e
custos no [ADR-0018](../docs/architecture/ADR-0018-copiloto.md).

Para o ligar, defina `ANTHROPIC_API_KEY` no servidor (no Vercel, em
*Environment Variables*; nunca com o prefixo `NEXT_PUBLIC_`). Cada pessoa tem um
limite diário de perguntas, e o consumo fica em `copiloto_uso`.

## Notificações por email

Avisos de atribuição e de comentário, convites por email e um resumo da manhã
com o que está atrasado. Cada pessoa escolhe o que recebe em *Notificações*.
Quem decide o que se envia é a base de dados; as rotas de cron só entregam a
fila. Decisão e custos no [ADR-0019](../docs/architecture/ADR-0019-notificacoes-por-email.md).

Para ligar, no servidor: `RESEND_API_KEY` e `EMAIL_REMETENTE` (de um domínio
verificado no Resend), `SUPABASE_SERVICE_ROLE_KEY` (usada **só** pelas rotas de
cron) e `CRON_SECRET` (16+ caracteres). O `vercel.json` agenda a entrega de 5 em
5 minutos (plano pago do Vercel) e o resumo às 7h UTC nos dias úteis (8h em Lisboa no verão, 7h no inverno).

## Importar do desktop

Quem administra uma empresa traz as tarefas da aplicação de secretária em
*Definições → Importar do desktop*: escolhe o `tarefas.db`, diz quem fica com
as tarefas de cada pessoa, e importa. O ficheiro é lido **no browser** — só as
tarefas seguem para o servidor — e reimportar não duplica nada. Decisão e
limites no [ADR-0020](../docs/architecture/ADR-0020-importacao-do-desktop.md).

## Relatórios

Em *Relatórios*, qualquer pessoa exporta as tarefas que pode ver em **PDF**
(A4 deitado), **Excel** ou **CSV**, com os indicadores e a análise do painel e
os filtros que escolher. Os ficheiros são escritos sem bibliotecas, como no
desktop ([ADR-0021](../docs/architecture/ADR-0021-relatorios-na-web.md)).

## Verificar

```bash
npm test                   # domínio (node:test, sem dependências)
npm run typecheck
npm run build
npm run test:bd            # migrações reais + RLS num Postgres efémero
```

`test:bd` (`../supabase/tests/correr.sh`) só precisa dos binários do
PostgreSQL (`initdb`, `pg_ctl`, `psql`): levanta um cluster temporário, aplica
as migrações **reais** e corre os testes SQL. Cada regra tem testes dos dois
lados — o que passa e o que é recusado, **com o motivo verificado**. Com
`VERBOSO=1` mostra cada verificação.

O CI corre os três (`.github/workflows/tests.yml`, jobs `base-de-dados` e
`web`).

Depois de um deploy, o ensaio de fumo prova que o que está no ar responde como
deve — sem criar contas nem dados:

```bash
npm run ensaio:fumo -- https://<deploy>
```

Sai com `1` se uma verificação falhar e com `2` se o pedido nem chegou à
aplicação (Proteção de Deployments do Vercel, ou um proxy pelo caminho).

> **Ainda não há `package-lock.json`.** Esta primeira versão foi escrita num
> ambiente sem acesso ao registo npm. A primeira pessoa a correr
> `npm install` deve fazer commit do lock gerado; a partir daí o CI usa
> `npm ci`.

## Mapa

```
web/
├── app/
│   ├── entrar/                 login, registo, ligação por email
│   ├── auth/callback/          troca do código por sessão
│   ├── convite/[token]/        aceitar um convite
│   └── app/
│       ├── page.tsx            escolher ou criar empresa
│       └── [empresa]/
│           ├── layout.tsx      concha: navegação, Ctrl+K
│           ├── page.tsx        painel
│           ├── tarefas/        lista, quadro, detalhe, comentários
│           ├── copiloto/       conversa com o Claude e propostas
│           ├── notificacoes/   que emails cada pessoa recebe
│           ├── importar/       trazer as tarefas do tarefas.db
│           ├── relatorios/     exportar em PDF, Excel e CSV
│           ├── equipa/         membros, papéis, convites
│           ├── auditoria/      trilha só de leitura
│           └── definicoes/     nome e segregação de funções
├── components/                 ui, gráficos SVG, navegação, paleta
├── lib/
│   ├── dominio/                regras puras + testes (sem React, sem rede)
│   ├── copiloto/               ciclo do Copiloto (cliente injetado, testável)
│   ├── emails/                 carteiro da fila de emails (Resend)
│   ├── ensaio/                 ensaio de fumo de um deploy
│   ├── importacao/             leitor SQLite e conversão do desktop
│   ├── relatorios/             PDF, XLSX e CSV escritos à mão
│   ├── supabase/               clientes servidor e browser
│   └── contexto.ts             sessão, empresa e papel
├── scripts/ensaio-fumo.ts      corre o ensaio contra um URL
└── proxy.ts                    renova a sessão; /app exige login
```

## Papéis

| Papel | Pode |
|---|---|
| Leitor | Ver todas as tarefas. Não altera nada. |
| Colaborador | Ver e trabalhar nas suas tarefas (atribuídas a si ou criadas por si). |
| Supervisor | Ver, atribuir e editar as de toda a equipa. |
| Gestor | Como supervisor, e apagar tarefas. |
| Administrador | Gerir pessoas abaixo de si, convites e definições; ler a auditoria. |
| Proprietário | Tudo, incluindo nomear administradores. A empresa nunca fica sem um. |
