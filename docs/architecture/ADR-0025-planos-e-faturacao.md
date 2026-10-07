# ADR-0025 — Planos na base, pagamentos no Stripe, e a chave de serviço no webhook

Data: 2026-10-06 · Estado: aceite

## Contexto

Para vender o produto são precisos planos com limites e um fornecedor de
pagamentos. Há duas perguntas: onde vivem os limites, e como chega à base a
confirmação de um pagamento, que vem do fornecedor sem a sessão de ninguém.

## Decisão

1. **Os limites são regras da base** (ADR-0017). A tabela `planos` guarda os
   valores. Gatilhos recusam:
   - a pessoa a mais (contando os convites pendentes);
   - a tarefa por concluir a mais (incluindo reabrir uma);
   - a pergunta ao Copiloto a mais no mês.

   Cada gatilho toma um trinco por empresa, para dois pedidos em paralelo não
   passarem juntos pelo último lugar.
2. **O plano não se escreve.** A coluna não se concede a `authenticated`, e um
   gatilho recusa a mudança mesmo que um dia alguém a conceda. Só
   `aplicar_faturacao` muda o plano, e só `service_role` a pode chamar.
3. **Stripe, sem SDK.** A API é HTTP com formulários e o webhook é um
   HMAC-SHA256. O que decide fica em funções puras testadas
   (`web/lib/faturacao/stripe.ts`): se a assinatura é válida (com uma janela
   de 5 minutos contra repetições) e que plano um evento quer dizer. Um preço
   que não está configurado não dá plano pago a ninguém. A rede entra por
   `fetch` injetado, atrás da interface `Faturacao`, para se poder trocar de
   fornecedor sem tocar no resto.
4. **A chave de serviço alarga-se a uma rota**, `app/api/faturacao/webhook`.
   O âmbito é o mesmo do ADR-0019: o módulo `servico.ts` só expõe a operação
   `aplicarFaturacao`, e o teste de arquitetura passa a permitir essa rota
   além dos crons. Exige também que a assinatura seja verificada antes de se
   tocar na base.
5. **Os eventos são idempotentes e ordenados.** Um evento repetido não faz
   nada. Um evento mais antigo do que o último aplicado também não, porque os
   webhooks chegam fora de ordem. Se o aviso de renovação se perder, o
   período pago caduca 3 dias depois do fim e a empresa volta a contar como
   Gratuito.
6. **Só a pessoa proprietária paga** (`preparar_faturacao`). O identificador
   do cliente no fornecedor fica em `interno.faturacao`, fora do alcance da
   API.

## Consequências

- Os valores e os preços em `planos` são uma proposta por decidir. Mudam por
  migração, e o preço cobrado é o do Stripe: a tabela só o mostra.
- Baixar de plano não apaga nada. Uma empresa acima do limite continua a ver
  e a concluir tudo, mas não acrescenta até voltar a caber.
- Configurar a produção exige `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `STRIPE_PRECO_EQUIPA` e `STRIPE_PRECO_EMPRESA` no Vercel, e o webhook
  apontado para `/api/faturacao/webhook` com os eventos
  `checkout.session.completed` e `customer.subscription.*`. Sem eles, a
  página do plano diz que a faturação não está ligada, e os limites do
  Gratuito aplicam-se na mesma.
