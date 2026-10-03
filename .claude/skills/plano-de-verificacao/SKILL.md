---
name: plano-de-verificacao
description: Planear como provar uma mudança não trivial antes de a fazer — a alegação, o que a pode tornar falsa, o caminho de prova mais direto neste sistema, o critério de sucesso e o limite de tentativas. Usar antes de uma funcionalidade, correção, refatoração ou mudança que atravessa sistemas (base, web, desktop, CI) quando os testes habituais não chegam para ter confiança.
---

# Plano de verificação

Antes de mudar um sistema não trivial, constrói um **caminho de prova**: uma
rota, própria deste projeto, da alegação até a prova que a estabelece, limita
ou refuta. O objetivo não é escolher uma técnica conhecida; é decidir como
**este** sistema pode revelar a verdade **desta** mudança.

Adaptada de `verification-planning` e da ideia de `loop-engineering`
(akitaonrails/my-skills).

## 1. Enquadrar a alegação

O comportamento que tem de passar a ser verdade, e as condições que tornariam
uma conclusão confiante errada: o que muda, o que tem de continuar igual, onde
o comportamento atravessa uma fronteira (base ↔ web, servidor ↔ browser,
fila ↔ carteiro, desktop ↔ importação), e que falha importaria mais.

*Feito quando* a alegação, a incerteza e as falhas importantes estão
concretas o bastante para investigar.

## 2. Desenhar o caminho

Tira as alternativas do próprio sistema — o que se controla, o que se observa,
transições de estado, invariantes, fronteiras, artefactos, e a capacidade de
repetir ou desfazer um cenário. Os instrumentos que este repositório já tem:

| Para provar | Instrumento |
|---|---|
| uma regra de acesso, papel, gatilho ou função | `supabase/tests/NN_*.sql` no Postgres efémero, com `t.ok` e `t.recusa` (motivo verificado) |
| que nenhuma tabela ou função escapou às regras gerais | `supabase/tests/80_postura_seguranca.sql` (catálogo) |
| lógica pura da web | `node --test` em `web/lib/**/*.test.ts`, dependências injetadas |
| uma regra de arquitetura da web | `web/lib/arquitetura.test.ts` |
| o desktop | `pytest` (e `tests/test_arquitetura.py` para as regras do CONTRIBUTING) |
| o deploy publicado | `npm run ensaio:fumo -- <url>` (skill **ensaio-de-fumo**) |
| a interface | Playwright com o Chromium instalado |
| migrações a sério | `supabase db push` contra um Postgres local com o shim (como se validou o workflow `base-de-dados.yml`) |
| o instalador | `workflow_dispatch` da Release (ensaio) |

Gera alternativas antes de escolher. Prefere a que dá uma conclusão confiável
com custo, segurança e esforço proporcionais.

*Feito quando* há um caminho preferido, as suas limitações são conhecidas, e
há uma alternativa mais fraca ou mais forte se as circunstâncias mudarem.

## 3. Orçamento de prova

No estado final: as alegações distintas; um dono para estabelecer ou refutar
cada uma; a prova mínima, sem duplicar, que cobre as alegações e as fronteiras
importantes. Reutiliza prova só enquanto o código, as entradas, o ambiente e o
estado relevantes forem os mesmos. Os gates do repositório e do CI aplicam-se
sempre; alargar ou repetir só com uma razão dita.

## 4. Critério de sucesso e limite de tentativas

Para trabalho que itera até passar (corrigir um CI, afinar uma consulta, um
fluxo de interface), fixa **antes** de começar:

- **Critério** — um comando com código de saída (`teste`, `build`, `ensaio`),
  um ficheiro que tem de existir, ou uma verificação manual com o que se vai
  olhar. "Parece bem" não é critério.
- **Limite** — 3 tentativas por omissão. Esgotado, pára e escala à pessoa com
  o que se tentou e o que falhou; não tentes uma quarta em silêncio.
- **Verificação manual** — quando o critério é humano, pausa e pergunta.
  Nunca a resolvas tu.

## 5. Criar um instrumento quando falta

Quando o sistema deixa a verdade demasiado indireta, acrescenta o **menor**
instrumento que torna o estado controlável, observável, repetível e
diagnosticável — um teste de catálogo, uma função de ajuda nos testes, um
modo de ensaio. Decide se é temporário ou permanente antes de o construir; os
permanentes entram com teste, os temporários saem quando cumpriram.
Pergunta antes de acrescentar dependências, superfícies de diagnóstico
persistentes ou mudanças estruturais só para recolher prova.

## 6. Investigar quando o caminho é desconhecido

Quando a prova depende de uma dependência, serviço externo ou capacidade que
muda depressa (Next 16, Supabase, a API do Claude, o Vercel), confirma na fonte
primária ou no código-fonte (skill **clonar-dependencias**) antes de escolher —
nunca de memória.

## 7. Fechar o caminho

Depois de implementar, segue o caminho planeado e interpreta o resultado
contra a alegação original: **estabelecida, limitada ou refutada**, com o que
se sabe separado do que fica incerto. Um leitor futuro tem de ver o que
sustenta a conclusão e o que fica fora do seu alcance.

## Proporção

Mudanças pequenas e mecânicas seguem os gates normais diretamente. Em trabalho
grande, por fases (skill **trabalho-profundo**), este plano define a prova que
cada portão segue.
