---
name: mapa-do-codigo
description: Criar ou atualizar os mapas do código (MAPA.md por pasta e um atlas na raiz) para pessoas e agentes perceberem o repositório depressa — responsabilidade, desenho, fluxo e integração de cada pasta — usando o git para saber que mapas ficaram desatualizados. Operação cara: só quando a pessoa pede documentação do código, o mapeamento inicial, ou a atualização dos mapas depois de mudanças grandes.
---

# Mapa do código

Mapas hierárquicos: um `MAPA.md` nas pastas que importam e um atlas
`MAPA.md` na raiz que os junta. Servem para entrar no repositório sem o ler
todo.

Adaptada de `codemap` (akitaonrails/my-skills). A diferença: em vez de um
ficheiro de estado com hashes de cada ficheiro, o atlas guarda o **commit** em
que os mapas foram revistos, e o git diz o que mudou desde então —
`scripts/mapa.sh`.

## 1. Estado

```bash
bash .claude/skills/mapa-do-codigo/scripts/mapa.sh estado
```

- saída `3` — ainda não há mapas (ou falta a marca): vai para o passo 2.
- saída `0` — em dia; nada a fazer.
- saída `1` — lista os ficheiros mudados, agrupados pela pasta cujo mapa é
  responsável por eles: atualiza **só esses** mapas (passo 3).

## 2. Primeiro mapeamento

Escolhe as pastas pela responsabilidade, não pela árvore inteira. Neste
repositório, um bom ponto de partida:

| Pasta | Porquê |
|---|---|
| `supabase/` | onde mora a autoridade (migrações, RLS, testes) |
| `web/app/` | rotas, Server Actions, crons |
| `web/lib/` | domínio, Copiloto, emails, importação, relatórios |
| `src/core/`, `src/` (restantes pacotes) | o desktop |
| `plugins/` | plugins embutidos e o contrato |
| `tools/` | build, instalador, release |
| `.github/` | CI, release, base de dados, Dependabot |

Exclui sempre: testes, docs, traduções, dependências e artefactos de build
(`node_modules/`, `.next/`, `build/`, `dist/`), e o que o `.gitignore` ignora.
As pastas `docs/` e os ADRs não levam mapa: **são** a documentação, e o atlas
liga para eles.

Lê o código de cada pasta e escreve o seu `MAPA.md` (formato abaixo). Com
muitas pastas e a pessoa de acordo, um subagente por pasta, cada um só com a
sua pasta; reconcilia tu o resultado.

## 3. Atualizar

Para cada pasta listada pelo `estado`: relê os ficheiros mudados e o mapa
atual, e corrige só o que deixou de ser verdade — responsabilidades, fluxos,
pontos de integração. Se a responsabilidade de uma pasta mudou, atualiza
também a linha dela no atlas.

## 4. O atlas da raiz

`MAPA.md` na raiz: o propósito do projeto (desktop e plataforma web), os
pontos de entrada (`src/main.py`, `web/app/layout.tsx`, `web/proxy.ts`,
`supabase/migrations/`, os workflows), uma tabela com cada pasta mapeada — a
responsabilidade numa linha e a ligação para o seu `MAPA.md` — e ligações para
`docs/architecture/` (ADRs), `CONTRIBUTING.md` e `web/README.md`.

## 5. Marcar e registar

Commita os mapas, depois:

```bash
bash .claude/skills/mapa-do-codigo/scripts/mapa.sh marcar   # recusa se houver código por commitar
git commit -am "docs: mapas do código em dia"
```

Se o `CLAUDE.md` ainda não tiver a secção **Mapa do repositório**,
acrescenta-a (uma vez; não dupliques):

```markdown
## Mapa do repositório

`MAPA.md` na raiz é o atlas do código; cada pasta mapeada tem o seu. Antes de
trabalhar numa área, lê o atlas e o mapa dessa pasta.
```

## Conteúdo de um MAPA.md

Termos técnicos precisos; nada de prosa genérica (skill **humanizar**).

```markdown
# web/lib/emails/

## Responsabilidade
Entregar a fila de emails que a base decidiu enviar (ADR-0019).

## Desenho
- `carteiro.ts`: reclama um lote, envia pela função `enviar` injetada, marca o resultado.
- `cron.ts`: `pedidoAutorizado` — Bearer CRON_SECRET em tempo constante.

## Fluxo
Vercel Cron → `app/api/cron/emails` → `pedidoAutorizado` → `entregar` →
`reclamar_emails` (skip locked) → Resend → `marcar_email`.

## Integração
- Usado por: `app/api/cron/*`.
- Depende de: `lib/supabase/servico.ts` (chave de serviço — só aqui), `lib/dominio/emails.ts`.
```

Responsabilidade, desenho (padrões e abstrações com nome), fluxo de dados e
de controlo, integração (quem usa, de quem depende). Um mapa é curto: se
ultrapassa uma página, a pasta provavelmente tem duas responsabilidades — e
isso é um candidato para a skill **arquitetura**.
