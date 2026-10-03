# ADR-0019 — Os emails decidem-se na base e entregam-se com a única chave de serviço da aplicação

Data: 2026-10-02 · Estado: aceite

## Contexto

Uma equipa precisa de saber, sem abrir a aplicação, quando lhe atribuem uma
tarefa, quando alguém comenta uma das suas, e de manhã o que tem atrasado. E
um convite que só existe como ligação para copiar é um convite que se perde.

Enviar emails tem duas partes com exigências opostas:

- **decidir** o que se envia, a quem, e se a pessoa o quer — tem de acontecer
  no momento em que a coisa acontece, com as regras da empresa, e não pode
  depender de a pessoa que fez a ação ter a aplicação aberta;
- **entregar** — fala com um fornecedor externo, falha, repete, e corre fora
  de qualquer sessão (um cron não é ninguém).

O [ADR-0017](ADR-0017-plataforma-web.md) diz que a aplicação não usa a chave
de serviço. A entrega não tem sessão de ninguém para usar.

## Decisão

**Decidir é da base.** Gatilhos em `tarefas`, `comentarios` e `convites`
põem emails numa fila (`emails_pendentes`) na mesma transação do que os
causou:

| Aviso | Para quem | Quando não vai |
|---|---|---|
| Atribuição | o novo responsável | se se atribuiu a si próprio; se o responsável não mudou; se desligou o aviso |
| Comentário | o responsável e o autor da tarefa | nunca a quem comentou; se desligou o aviso |
| Convite | o email convidado | — |
| Resumo da manhã | quem tem tarefas atrasadas ou a vencer hoje, por empresa | se não tem nenhuma; se desligou; uma vez por dia (a chave inclui o dia) |

Cada pessoa escolhe em `preferencias_notificacao` (RLS: só as suas). Uma
chave única por aviso impede repetidos.

**A fila é invisível a quem está em sessão.** Guarda tokens de convite, que
são credenciais. Não tem policies, e os grants foram retirados a `anon` e
`authenticated`: nem a proprietária a lê.

**Entregar é de um carteiro, com a única chave de serviço da aplicação — e
mesmo essa estreitada.** As rotas `app/api/cron/emails` e
`app/api/cron/resumos` (chamadas pelo Vercel Cron com `CRON_SECRET`) usam
`lib/supabase/servico.ts`, que **não expõe um cliente**: oferece três
operações, cada uma uma função da base que só `service_role` pode executar —
`reclamar_emails`, `marcar_email` e `enfileirar_resumos`. A chave contorna a
RLS para tudo; este desenho faz com que o código só a consiga usar para isto.
`web/lib/arquitetura.test.ts` falha se a chave aparecer noutro ficheiro, ou
se `servico.ts` for importado fora de `app/api/cron/`.

**A entrega aguenta falhas:**

- `reclamar_emails` usa `for update skip locked`: dois carteiros ao mesmo
  tempo não enviam o mesmo email;
- um lote reclamado e não marcado (o carteiro morreu a meio) volta à fila ao
  fim de 10 minutos;
- cada falha conta e guarda o erro; ao fim de 5, o email deixa de ser tentado;
- a chave de idempotência enviada ao fornecedor é o id da fila: se um envio
  der timeout e se repetir, a pessoa não recebe dois.

**Fornecedor: Resend, pela API REST**, sem SDK — é um único pedido HTTP, e o
envio é injetado no carteiro (`enviarComResend`), o que permite testá-lo com
um `fetch` falso e trocar de fornecedor num só sítio.

**Os modelos de email são puros** (`lib/dominio/emails.ts`) e **escapam tudo**
o que as pessoas escreveram — títulos, comentários, nomes. Um assunto nunca
tem quebras de linha.

## Como se prova

- `supabase/tests/60_notificacoes_email.sql`: o que entra e o que não entra
  na fila, preferências, ninguém em sessão a lê nem chama as funções do
  carteiro, resumo uma vez por dia, lotes sem repetidos, falhas contadas e
  emails esquecidos que voltam;
- `web/lib/dominio/emails.test.ts`: escape de HTML, assunto sem quebras,
  ligações certas, tokens de convite estranhos recusados;
- `web/lib/emails/carteiro.test.ts`: uma falha não trava o lote, chave de
  idempotência, pedido ao Resend, segredo do cron em tempo constante;
- `web/lib/arquitetura.test.ts`: onde a chave de serviço pode estar.

## Consequências

- **Há uma chave de serviço no servidor** (`SUPABASE_SERVICE_ROLE_KEY`). Se
  vazar, dá acesso a tudo, com ou sem este desenho — o que o desenho garante é
  que o *código* não a usa para mais nada. Fica só nas variáveis de ambiente
  do alojamento e roda-se se houver suspeita.
- **O cron de 5 em 5 minutos precisa de um plano pago do Vercel** (o gratuito
  só corre crons diários). Alternativa: qualquer agendador externo a chamar a
  rota com o `CRON_SECRET`. Sem nenhum, os emails ficam na fila à espera.
- **Os emails chegam com até 5 minutos de atraso.** Para um convite é o
  bastante; a ligação continua também a poder ser copiada.
- **Um email que não se consegue montar sai da fila sem ser enviado** (ex.: um
  resumo que, entretanto, não tem tarefas) e conta como `sem_conteudo`.
- Notificações push e no próprio browser ficam por fazer; a fila e as
  preferências já servem de base para elas.
