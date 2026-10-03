---
name: trabalho-profundo
description: Modo de trabalho por fases com ficheiro de estado persistente e portão de revisão independente no fim de cada fase. Só quando a pessoa o pede ("trabalho profundo", /trabalho-profundo) para trabalho grande e arriscado — várias fases dependentes, migrações que não se podem entregar a meio, mudanças de arquitetura. Não usar em correções, ajustes ou funcionalidades pequenas.
---

# Trabalho profundo

Adaptado da skill `deepwork` de akitaonrails/my-skills, sem os agentes do
OpenCode: os portões usam as skills `/code-review` e `/security-review` do
Claude Code. Custa mais tempo e tokens do que trabalhar direto — por isso só
entra quando a pessoa o pede.

## 1. Ficheiro de estado

Antes de planear, cria `.trabalho/<tema-curto>.md` (o `.gitignore` já ignora
`.trabalho/`). É a memória do trabalho: quando o contexto é resumido ou a
sessão retoma, **lê-se este ficheiro primeiro** e continua-se dele, em vez de
reconstruir de memória.

Sem modelo rígido; deve ter, conforme se aplicar:

- objetivo e o que se percebeu do pedido, com as restrições da pessoa
  palavra por palavra (por exemplo: "não alterar nada em ALKMIA");
- factos apurados, com caminhos de ficheiros em vez de cópias do conteúdo;
- o plano: fases, ordem, e o risco que o portão de cada fase vai rever;
- estado de cada fase, validações corridas e o resultado;
- decisões tomadas e porquê; bloqueios, perguntas em aberto, o que fica para
  depois; IDs externos que custam a reencontrar (PRs, deploys, projetos).

Atualiza-o depois de cada decisão, portão, validação ou mudança de âmbito.

**Sessões na cloud:** o contentor é efémero e o ficheiro morre com ele. No fim
de cada fase, a versão compacta do estado vai também para a descrição do PR,
que sobrevive.

## 2. Plano

- Poucas fases coerentes, cortadas pelas dependências e pelas fronteiras
  naturais de entrega — nunca para encolher uma revisão.
- Cada fase termina numa entrega válida por si: testes verdes, e um commit
  (ou PR, se o trabalho for em PRs encadeados).
- Para cada fase regista: objetivo, o que valida, e a decisão ou o risco que
  o portão deve olhar.
- A prova de cada fase planeia-se com a skill **plano-de-verificacao**:
  alegação, caminho de prova, critério de sucesso e limite de tentativas.
- Mostra à pessoa uma versão compacta do plano antes de começar.

## 3. Execução de cada fase

- No início da fase, a lista de tarefas (TaskCreate) passa a ter só as
  tarefas dessa fase.
- Corre em paralelo só o que é independente; não avances de fase com
  trabalho em curso ou resultados por reconciliar.
- As regras do projeto continuam a mandar: a autoridade é a base de dados
  (RLS, funções, gatilhos — ADR-0017); cada regra de base de dados tem testes
  dos dois lados com o motivo da recusa verificado; decisões com custo dão
  um ADR em `docs/architecture/`; o `CHANGELOG.md` acompanha.

## 4. Portão no fim de cada fase

1. **Validação do projeto**, a que se aplicar:
   `supabase/tests/correr.sh`; em `web/`, `npm test`, `npm run typecheck`,
   `npm run build` (sem registo npm no ambiente, o CI faz este papel — espera
   por ele verde); `pytest` se tocou em `src/`.
2. **Regista no ficheiro de estado** o objetivo da fase, os caminhos
   alterados, a prova da validação e o risco a rever — para a revisão olhar
   para contexto estabelecido em vez de redescobrir.
3. **Revisão independente:** `/code-review high` sobre o diff da fase. Se a
   fase toca em migrações, RLS, autenticação, segredos, rotas de cron ou na
   chave de serviço, também `/security-review` — e, numa fase grande nessas
   áreas, a skill **auditoria-seguranca**, com o modelo de ameaças do produto.
   No fim do trabalho todo, antes do merge, a **auditoria-pr** em modo
   conjunto sobre as fases juntas.
4. **Uma passagem de correção** para o que for material, validada com prova
   focada. O que for opcional fica registado, não bloqueia.
5. **Commit** da fase quando é uma entrega válida por si; só depois a fase
   seguinte.

### Re-revisões

Cada portão tem uma revisão inicial e **no máximo duas re-revisões**. Pede-se
re-revisão só quando a correção muda materialmente a decisão ou o risco
revisto, ou quando a preocupação não se consegue verificar com prova focada —
nunca por uma mudança mecânica ou já verificada. Marca cada pedido:

```text
Portão 2 — revisão 2 de 3 (resta 1 re-revisão)
```

Na re-revisão, olha-se primeiro para os achados materiais por resolver e
para riscos que a correção tenha trazido; o que já foi aceite, resolvido ou
não mudou não se reabre. Esgotadas as re-revisões, regista o risco que
sobra e pergunta à pessoa: aceitar o risco, mudar o âmbito, ou autorizar uma
revisão extra.

## 5. Fim

Validação final do conjunto, resumo curto para a pessoa (o que mudou, o que
foi provado, o que fica por fazer) e o estado final copiado para o PR.
