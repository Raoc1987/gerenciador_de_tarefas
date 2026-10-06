# RGPD e operação da plataforma web

Data: 2026-10-03. Aplica-se à plataforma web (`web/`, `supabase/`). A
aplicação desktop não tem servidor e não recolhe dados (ver
[MANUTENCAO.md](MANUTENCAO.md)).

## Os direitos da pessoa, sem pedir a ninguém

Em **A minha conta** (`/app/<empresa>/conta`):

| Direito | Como | Onde está a regra |
|---|---|---|
| Acesso e portabilidade (art. 15.º e 20.º) | "Descarregar os meus dados": um JSON com a conta, o perfil, as empresas e o papel em cada uma, as tarefas que criou, concluiu ou tem atribuídas, os comentários, as preferências de notificação, o uso do copiloto e a auditoria dos seus atos | `exportar_os_meus_dados()` |
| Apagamento (art. 17.º) | "Apagar a minha conta", confirmando com o email | `apagar_a_minha_conta(p_confirmacao)` |

Ambas são funções da base (ADR-0017): a interface só as chama. Os testes estão
em `supabase/tests/90_rgpd.sql` (os dois lados, com o motivo da recusa) e
`web/e2e/rgpd.spec.ts` (pela interface).

### O que o apagamento faz

1. Recusa se a confirmação não for o email da conta.
2. Recusa se a pessoa for a **única proprietária de uma empresa com mais
   gente**: a empresa não pode ficar sem dono. Passa-se a propriedade antes.
3. Apaga as empresas onde a pessoa está sozinha, com tudo o que têm.
4. Nas outras empresas o trabalho fica: tarefas e comentários continuam, com
   o autor, o responsável e quem concluiu a `null`. Os gatilhos de regras
   (autor não muda, segregação de funções) não disparam nesta limpeza, porque
   ela corre em modo `anonimizar` (`interno.modos`, válido só na transação
   corrente e fora do alcance de `authenticated`).
5. Apaga a conta em `auth.users`; perfil, pertenças, preferências, emails por
   enviar e uso do copiloto vão em cascata.

### Limites conhecidos

- **A auditoria é imutável.** As linhas de `public.auditoria` guardam o
  identificador da pessoa e, em convites e comentários, o email convidado e o
  texto. Depois do apagamento o identificador já não aponta para ninguém, mas o
  texto fica. Base legal para o manter: interesse legítimo da empresa no
  registo do que se fez (art. 6.º, n.º 1, al. f); é preciso dizê-lo na
  política de privacidade. Se um titular contestar, a correção é uma migração
  que reescreve essas linhas com a auditoria desligada, nunca o editor SQL.
- **`delete from auth.users` por uma função `security definer`** passa nos
  testes locais, que correm como `postgres`. No Supabase alojado o dono das
  funções também é `postgres`, que tem permissão sobre `auth.users`; ainda
  assim, o primeiro apagamento em produção deve ser ensaiado com uma conta de
  teste antes de se anunciar a funcionalidade.
- As cópias de segurança do Supabase guardam os dados apagados até expirarem
  (7 dias no plano Pro). Diz-se na política de privacidade.

## Subcontratantes

| Quem | Para quê | Onde |
|---|---|---|
| Supabase | base de dados, autenticação | UE, `eu-central-1` (Frankfurt) — ADR-0022 |
| Vercel | alojamento da aplicação | funções na região `fra1`; CDN global |
| Anthropic | copiloto (só o texto que a pessoa pede para analisar) | EUA, com cláusulas contratuais-tipo |
| Resend | envio de emails de notificação | EUA, com cláusulas contratuais-tipo |
| Stripe | pagamentos, faturas e dados de faturação da empresa | Irlanda (Stripe Payments Europe), com transferências para os EUA ao abrigo de cláusulas contratuais-tipo |

Cada um precisa de um acordo de subcontratação (DPA) assinado antes de haver
clientes pagantes. Um subcontratante novo entra nesta tabela e na política de
privacidade no mesmo PR que o introduz.

## Retenção

| Dados | Quanto tempo |
|---|---|
| Conta, tarefas, comentários | enquanto a conta ou a empresa existir |
| Emails por enviar | até serem enviados ou falharem 5 vezes; apagam-se com a conta |
| Uso do copiloto | enquanto a empresa existir (serve para os limites de uso) |
| Auditoria | enquanto a empresa existir |
| Cópias de segurança | as do plano Supabase |

## Incidentes

Uma violação de dados pessoais comunica-se à CNPD em **72 horas** a contar do
conhecimento (art. 33.º), e às pessoas afetadas quando o risco for elevado
(art. 34.º). Ordem de trabalho:

1. Conter: rodar as chaves expostas (Supabase, Resend, Anthropic, segredo dos
   crons) e revogar sessões.
2. Medir: o que saiu, de que empresas, desde quando — a `auditoria` e os
   registos do Supabase e da Vercel.
3. Comunicar à CNPD com o que se sabe; completar depois.
4. Corrigir com uma migração ou um PR, com o teste que teria apanhado a falha.
