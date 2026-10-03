-- Planeamento: duração e "não começa antes de", para o caminho crítico e o
-- nivelamento de recursos (web/lib/dominio/cronograma.ts).
--
-- O cálculo não vive aqui: é domínio puro, testado à parte, e corre sobre o
-- que a RLS deixa a pessoa ver. A base guarda só os dados de entrada e os
-- limites deles; quem os escreve é quem já pode escrever na tarefa
-- (tarefas_editar), sem regra nova.

alter table public.tarefas
  -- Em dias úteis. null = ainda não estimada; o cronograma conta-a como 1.
  -- 0 é um marco.
  add column duracao_dias integer check (duracao_dias between 0 and 1000),
  add column inicio_minimo date;
