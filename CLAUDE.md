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
cd web && npm run test:cobertura      # o mesmo, com o mínimo de cobertura do CI
cd web && npm run typecheck && npm run build
python -m pytest                      # desktop
cd web && npm run ensaio:fumo -- <url>   # um deploy publicado
```

O que corre em cada camada, e o mínimo que a guarda, está em `docs/METODO.md`
§7. O workflow `ensaio-publicado.yml` ensaia cada deploy pronto e, com a
variável `PRODUCAO_URL` definida no repositório, a produção de hora a hora.

Nas sessões de agente na cloud não há acesso ao registo npm: o build e o
typecheck reais correm no CI (`.github/workflows/tests.yml`), e esperar por ele
verde faz parte de verificar.

## Método

`docs/METODO.md` é vinculativo: níveis de verificação (implementado ≠ integrado
≠ aplicado ≠ verificado em produção), o protocolo de seis passos (medir,
propor com o rejeitado, decidir o que é do autor, executar, provar que a prova
falha, registar) e as regras com cicatriz. Vem do ALKMIA, só o que serve aos
dois produtos; o que se trouxe e recusou está em
`docs/conhecimento/catalogo.json`, validado por `python tools/conhecimento.py
validar` e pelo `tests/test_conhecimento.py`.

Agentes (`.claude/agents/`): `medidor` (números com data e fonte, só leitura,
nunca no ALKMIA), `escrutinador-de-promessas` (o que se afirma em público vs. o
que o código sustenta), `avaliador-de-tecnologia` (sete filtros antes de
adotar). Hook: depois de editar `web/**/x.ts`, corre o `x.test.ts` colocado.

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
| `reconciliar-esquema` | comparar o esquema de produção com as migrações, por assinaturas (só lê) |
| `refletir` | aprender com trabalho repetido e propor a melhoria mais pequena |
| `humanizar` | tirar o ar de IA da prosa, em português europeu |

Do próprio Claude Code: `/code-review`, `/security-review`, `/simplify`.
