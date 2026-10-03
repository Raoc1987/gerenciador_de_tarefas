# ADR-0023 — Tudo é um nó, e chega-se lá por fatias

Data: 2026-10-03 · Estado: aceite como direção; cada fatia aceita no seu PR

## Contexto

O PRD (`docs/produto/PRD.md`) pede uma plataforma onde tarefa, subtarefa,
documento, marco, objetivo, projeto e portfólio sejam a mesma entidade, com
hierarquia infinita, relações tipadas, campos personalizados, rollups e
fórmulas, a aguentar milhões de linhas ativas. Hoje há uma tabela `tarefas`
plana (`supabase/migrations/20261001000100_tarefas.sql`), com RLS, auditoria
e um quadro que já está em uso.

Reescrever o modelo de uma vez parava o produto e misturava num só PR
decisões de esquema, de RLS, de interface e de migração de dados.

## Decisão

1. A direção é o **nó único** descrito no PRD 1.3: `pai_id` como verdade,
   `caminho` em `ltree` como índice, `campos` e `derivados` em JSONB
   validados na base, relações tipadas numa tabela própria, partição por
   empresa quando o volume o justificar.
2. Chega-se lá **por fatias que entregam valor sozinhas**, na ordem do PRD
   5.4. A primeira fatia acrescenta a `tarefas` o que é comum a todas as
   lentes — hierarquia (subtarefas) e dependências tipadas — sem mudar o
   que já existe. Quando `nos` existir, `tarefas` passa a vista de
   compatibilidade.
3. As regras continuam na base: ciclos de hierarquia e de dependências são
   recusados por funções e gatilhos, não pela interface; a RLS dos nós
   filhos é a do nó raiz da empresa, sem exceções por tipo.
4. O cálculo pesado (caminho crítico, carga, rollups) vive em domínio puro
   testado (`web/lib/dominio/`) e, mais tarde, num trabalhador que consome o
   diário de eventos. Os gatilhos ficam curtos e sem rede.

## Consequências

- Cada fatia tem o seu PR, com testes dos dois lados e, quando decide algo
  com custo, o seu ADR.
- Durante a transição há dois sítios onde uma tarefa "é": a tabela de hoje e,
  mais tarde, `nos`. A vista de compatibilidade tem de passar todos os testes
  existentes antes de a tabela antiga deixar de ser escrita.
- A hierarquia em `tarefas` usa só `pai_id` (sem `ltree`) enquanto as árvores
  forem pequenas; o `caminho` materializado entra com `nos`, quando os
  índices de subárvore passarem a pagar o custo de o manter.
