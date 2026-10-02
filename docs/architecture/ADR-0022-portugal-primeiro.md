# ADR-0022 — Portugal primeiro: fuso de Lisboa, português europeu e Frankfurt

Data: 2026-10-02 · Estado: aceite · Substitui as referências a Brasília dos ADR-0017 e ADR-0020

## Contexto

A plataforma web nasceu com predefinições do Brasil: fuso `America/Sao_Paulo`,
datas em `pt-BR`, o Copiloto a responder em português do Brasil, o resumo
da manhã às 8h de Brasília, e a importação do desktop a assumir `-03:00`.

Os primeiros clientes são em **Portugal**. Com o fuso errado, uma tarefa que
vence hoje aparece atrasada (ou não) consoante a hora; o resumo chega a meio
da manhã; e as datas importadas ficam deslocadas três ou quatro horas.

## Decisão

- **Fuso por omissão: `Europe/Lisbon`** (`FUSO_PADRAO`), usado no "hoje" do
  painel, nos prazos, no limite diário do Copiloto e na importação.
- **Português europeu**: `pt-PT` nas datas, no `<html lang>` das páginas e dos
  emails, e o Copiloto responde em português de Portugal. Os textos da
  interface já estavam em português europeu.
- **Infraestrutura em Frankfurt**: a base no Supabase em `eu-central-1` e as
  funções do Vercel em `fra1` (`vercel.json`). Os dados ficam na UE, e cada
  pedido não atravessa o Atlântico entre a função e a base — por omissão o
  Vercel corre as funções nos EUA.
- **O resumo da manhã às 7h UTC** nos dias úteis: 8h em Lisboa no verão, 7h no
  inverno. Um cron em UTC não acompanha a hora de verão.
- **A importação do desktop deixa de usar um desvio fixo.** Portugal muda de
  hora duas vezes por ano: `+00:00` em janeiro, `+01:00` em julho. O browser
  passa a enviar a hora local tal como estava no desktop, e
  `importar_tarefas(…, p_fuso)` converte-a com as regras do fuso (o teste
  verifica uma data de inverno e uma de verão). Um fuso desconhecido é recusado.

## Consequências

- **O fuso é da instalação, não da empresa nem da pessoa.** Uma equipa
  noutro fuso vê "hoje" como Lisboa o vê. Passá-lo a definição da empresa é
  o passo seguinte quando houver o primeiro cliente fora de Portugal; os
  sítios que o usam já recebem o fuso como parâmetro.
- A série diária do painel continua a agrupar por dia UTC; em Lisboa a
  diferença é de no máximo uma hora, e só no verão.
