# Gerenciador de Tarefas

Dois produtos no mesmo repositório: a aplicação **desktop** (Python, só
biblioteca padrão, Tkinter, SQLite — `src/`, `plugins/`, `tools/`), congelada
para funcionalidades (ADR-0017), e a **plataforma web** multiempresa (Next.js
16, React 19, Supabase, Vercel — `web/`, `supabase/`).

## Regras que não se dobram

- **Nunca alterar nada do ALKMIA**: nem o repositório, nem o projeto Supabase
  `alkmia.app`, nem o projeto Vercel `site`, nem a organização ALKMIA no
  Supabase. Serve só de referência. Este produto vive na organização Supabase
  "Gerenciador de Tarefas" e no projeto Vercel `gerenciador-de-tarefas`.
- **A autoridade é a base de dados** (ADR-0017): quem vê e faz o quê decide-se
  em RLS, funções e gatilhos em `supabase/migrations/`. A interface esconde,
  não protege. A chave de serviço só existe em `web/lib/supabase/servico.ts`,
  só para as rotas de cron (ADR-0019) — há teste.
- **Migrações aplicadas não se editam**: corrige-se com uma migração nova. A
  produção recebe-as pelo workflow `base-de-dados.yml`, nunca pelo editor SQL.
- **Português europeu** em tudo o que o utilizador vê, fuso `Europe/Lisbon`
  (ADR-0022). Código, comentários, commits e docs também em português.
- **As regras do CONTRIBUTING.md têm testes**; uma regra nova entra com um
  teste que a guarda, não só com texto.

## Verificar

```bash
supabase/tests/correr.sh              # migrações reais + RLS + postura, num Postgres efémero
cd web && npm test                    # domínio, arquitetura, ensaio (node:test)
cd web && npm run typecheck && npm run build
python -m pytest                      # desktop
cd web && npm run ensaio:fumo -- <url>   # um deploy publicado
```

Nas sessões de agente na cloud não há acesso ao registo npm: o build e o
typecheck reais correm no CI (`.github/workflows/tests.yml`), e esperar por ele
verde faz parte de verificar.

## Convenções

- Uma regra de base de dados tem testes **dos dois lados** — o que passa e o
  que é recusado, com o motivo da recusa verificado (`t.recusa`).
- Uma decisão com custo dá um ADR em `docs/architecture/`.
- O `CHANGELOG.md` acompanha cada mudança visível, em **[Não lançado]**, na
  categoria certa.
- Actions do CI fixadas por SHA; binários descarregados fixados por versão e
  SHA-256.
- Prosa sem tiques de IA (skill `humanizar`).

## Skills do projeto (`.claude/skills/`)

| Skill | Para quê |
|---|---|
| `trabalho-profundo` | trabalho grande por fases, com estado persistente e portão de revisão (só a pedido) |
| `plano-de-verificacao` | decidir como provar uma mudança antes de a fazer |
| `auditoria-seguranca` | auditoria com o modelo de ameaças do produto |
| `auditoria-pr` | rever um PR antes do merge, ou a main antes de publicar |
| `auditoria-issue` | triar e validar issues antes de implementar |
| `resolucao` | executar o que uma auditoria aprovou e fechar os tickets |
| `dependencias` | PRs do Dependabot, consolidados e verificados de uma vez |
| `lancamento` | lançar o desktop (etiqueta `v*`) ou a web (produção) |
| `ensaio-de-fumo` | ensaiar um deploy publicado |
| `pos-refatoracao` | verificação focada depois de refatorações |
| `arquitetura` | encontrar aprofundamentos e consolidações que valem a pena |
| `mapa-do-codigo` | mapas do código para pessoas e agentes |
| `clonar-dependencias` | ler o código-fonte das dependências na versão usada |
| `verificar-factos` | verificar os factos das docs contra fontes primárias |
| `refletir` | aprender com trabalho repetido e propor a melhoria mais pequena |
| `humanizar` | tirar o ar de IA da prosa, em português europeu |

Do próprio Claude Code: `/code-review`, `/security-review`, `/simplify`.
