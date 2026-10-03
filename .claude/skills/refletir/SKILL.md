---
name: refletir
description: Olhar para o trabalho recente, encontrar fluxos que se repetem e propor a melhoria mais pequena que os resolve — uma skill, uma regra no CLAUDE.md, um teste que guarda uma regra, um script, um passo de CI, uma página de docs, ou nada. Usar quando a pessoa pede para aprender com sessões passadas, melhorar um processo recorrente, ou perceber o que devia virar instrução reutilizável.
---

# Refletir

Aprende com trabalho repetido e recomenda a melhoria mais pequena com prova.
"Não criar nada" é um resultado bem-sucedido quando a prova é fraca.

Adaptada de `reflect` (akitaonrails/my-skills).

## Contrato

- Inventaria o que já existe antes de propor algo novo.
- Prefere atrito recente, repetido e visível a incidentes isolados.
- Recomenda a forma mais pequena que serve.
- Pergunta antes de mudar skills, `CLAUDE.md`, configuração, permissões ou CI.
- Não duplica o que já existe.

## Fontes de prova, por ordem

1. A conversa atual e as instruções explícitas da pessoa.
2. As regras do projeto: `CLAUDE.md`, `CONTRIBUTING.md`, ADRs em
   `docs/architecture/`, `docs/MANUTENCAO.md`, `codemap.md` se existir, e o
   estado de trabalho em `.trabalho/`.
3. As skills de `.claude/skills/` e as do próprio Claude Code (`/code-review`,
   `/security-review`, `/simplify`, `/init`, `/loop`, …).
4. O histórico: `git log` (mensagens de `fix:` repetidas na mesma área são
   sinal), PRs e os comentários de revisão que se repetem, falhas de CI que
   voltam, o CHANGELOG.
5. Documentação externa, só quando a proposta depende de uma ferramenta de
   terceiros cujo comportamento precisa de confirmação.

Não inspeciones ficheiros pessoais, credenciais ou contas externas sem pedido
explícito.

## Fluxo

### 1. Inventário

Que skills, regras, testes de arquitetura, scripts e workflows já cobrem a
área? Se um já cobre o candidato, recomenda estendê-lo em vez de criar um
quase-duplicado.

### 2. Padrões repetidos

- a mesma sequência de comandos em várias sessões ou PRs;
- a pessoa pede repetidamente a mesma revisão, configuração ou depuração;
- a mesma regra do projeto é re-explicada (sinal forte: devia estar no
  `CLAUDE.md` ou, melhor, num teste);
- a mesma classe de bug volta (`fix:` na mesma área) porque falta uma
  instrução estável ou uma verificação;
- o mesmo achado de revisão em PRs diferentes.

Candidatos fortes têm pelo menos duas ocorrências, entradas estáveis,
resultado claro e ponto de paragem claro.

### 3. Pontuar

Frequência · custo (tempo, contexto, dinheiro, atenção) · risco (execução
inconsistente causa bugs ou mudanças inseguras?) · estabilidade (entradas e
saída previsíveis?) · cobertura (já há algo que trata bem?). Só recomenda com
confiança alta.

### 4. A forma mais pequena

Por ordem de preferência neste projeto:

1. **Um teste que guarda a regra** — "uma regra que não falha um teste é uma
   sugestão" (ADR-0004). Se a repetição é alguém a esquecer uma regra, o
   remédio é um teste (`tests/test_arquitetura.py`, `web/lib/arquitetura.test.ts`,
   `supabase/tests/80_postura_seguranca.sql`), não mais texto.
2. **Uma linha no `CLAUDE.md`** — comportamento pequeno e estável.
3. **Um script** em `tools/` ou `web/scripts/` — passos mecânicos repetidos.
4. **Uma skill** — um fluxo com julgamento, entradas e paragem claras.
5. **Um passo de CI** — o que tem de acontecer sempre, sem depender de alguém
   se lembrar.
6. **Uma página de docs** — quando automatizar é pesado demais.
7. **Nada** — fraco, isolado, ambíguo, sensível ou já coberto.

### 5. Propor antes de mudar

```text
Encontrei 2 fluxos repetidos fortes e 1 fraco.

Recomendo:
- <forma> para <fluxo>, porque <prova>.
- Estender <skill/teste existente> em vez de criar outro, porque <sobreposição>.

Não recomendo:
- <candidato>, porque só aconteceu uma vez.

Avanço com estas alterações?
```

Ao aplicar: alterações estreitas, preservando o que a pessoa configurou.
Skills novas ou alteradas valem na sessão seguinte do Claude Code.

## Relatório

```text
Achados
- <fluxo>: prova, frequência/confiança, forma recomendada.

Alterações recomendadas
- <ativo>: propósito numa linha e porque é a forma mais pequena.

Não vale a pena agora
- <candidato>: porquê.

Falta prova
- <candidato>: o que o tornaria acionável.
```

Sem nada qualificado: "Não encontrei fluxos repetidos fortes. Não
acrescentava nem mudava nada por agora."

## Guardas

- Não fabriques ativos para justificar a reflexão.
- Não crie skills que se sobrepõem.
- Não acrescentes instruções largas que tornem o agente mais ansioso, caro ou
  invasivo sem benefício claro.
- Não sobre-ajustes a uma única sessão, a menos que a pessoa peça esse fluxo.
- Nada de material privado ou sensível como exemplo num ativo.
