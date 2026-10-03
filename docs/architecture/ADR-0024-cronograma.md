# ADR-0024 — Caminho crítico e nivelamento: domínio puro, no pedido, em dias úteis

Data: 2026-10-03 · Estado: aceite

## Contexto

Com as dependências (ADR-0023, primeira fatia), as tarefas já formam uma
rede. O PRD pede o caminho crítico e o nivelamento de recursos. É preciso
decidir onde corre o cálculo, em que unidade de tempo, e que algoritmo de
nivelamento usar.

## Decisão

1. **Domínio puro** em `web/lib/dominio/cronograma.ts`, sem base nem rede,
   com testes próprios. A base guarda só a entrada (`duracao_dias`,
   `inicio_minimo`) e os limites dela; o cálculo não é uma regra de acesso e
   não precisa da autoridade da base.
2. **Corre no pedido**, sobre o que a RLS deixa ver: o plano de um
   colaborador é o das suas tarefas, e uma ligação a uma tarefa que não vê
   não entra. Até 1500 tarefas abertas; acima disso a página avisa. Quando
   houver empresas com mais do que isso, o mesmo código passa para um
   trabalhador que guarda o resultado.
3. **Dias úteis**: segunda a sexta, sem os feriados nacionais obrigatórios
   (art. 234.º do Código do Trabalho, incluindo os móveis, calculados a
   partir da Páscoa). Os feriados municipais e o Carnaval ficam para um
   calendário por empresa.
4. **Nivelamento em série** por prioridade (início cedo, menos folga, mais
   peso). Cada pessoa faz uma tarefa de cada vez. É a heurística das
   ferramentas de cronograma: previsível e explicável. O problema ótimo é
   NP-difícil.
5. **Tarefas com subtarefas são resumos**: não têm duração própria, e uma
   ligação a um resumo vale para todas as folhas dele.

## Consequências

- O plano é sempre coerente com o que a pessoa vê, mas duas pessoas com
  vistas diferentes podem ver datas diferentes para a mesma tarefa. Para
  quem gere (que vê tudo) o plano é o da empresa.
- Uma tarefa sem duração conta como 1 dia, e a página diz quantas estão
  assim.
- Não há ainda capacidade parcial (meio tempo), calendários por pessoa nem
  férias. O modelo de `TarefaPlano` aceita-os sem mudar a interface do
  cálculo.
