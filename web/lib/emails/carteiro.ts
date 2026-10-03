// Entrega o que está na fila de emails. A fila e o envio são injetados: os
// testes correm sem base nem rede, e o fornecedor de email troca-se aqui.

import { montarEmail, type EmailPendente, type EmailPronto } from "../dominio/emails.ts";

export interface Fila {
  reclamar(limite: number): Promise<EmailPendente[]>;
  marcar(id: number, ok: boolean, erro?: string): Promise<void>;
}

export type Enviar = (email: EmailPronto, chaveIdempotencia: string) => Promise<void>;

export interface Balanco {
  enviados: number;
  falhados: number;
  sem_conteudo: number;
}

export async function entregar(o: { fila: Fila; enviar: Enviar; site: string; limite?: number }): Promise<Balanco> {
  const lote = await o.fila.reclamar(o.limite ?? 50);
  const balanco: Balanco = { enviados: 0, falhados: 0, sem_conteudo: 0 };
  for (const pendente of lote) {
    const pronto = montarEmail(pendente, o.site);
    if (!pronto) {
      // Nada a dizer (ex.: resumo sem tarefas): sai da fila sem ser enviado.
      await o.fila.marcar(pendente.id, true);
      balanco.sem_conteudo++;
      continue;
    }
    try {
      // A chave de idempotência é o id da fila: se o envio der timeout e for
      // repetido, o fornecedor não manda o mesmo email duas vezes.
      await o.enviar(pronto, `email-${pendente.id}`);
      await o.fila.marcar(pendente.id, true);
      balanco.enviados++;
    } catch (e) {
      await o.fila.marcar(pendente.id, false, e instanceof Error ? e.message : String(e));
      balanco.falhados++;
    }
  }
  return balanco;
}

/** Envio pela API REST do Resend (https://resend.com/docs/api-reference/emails/send-email). */
export function enviarComResend(o: { chave: string; remetente: string; fetch?: typeof fetch }): Enviar {
  const f = o.fetch ?? fetch;
  return async (email, chaveIdempotencia) => {
    const r = await f("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${o.chave}`,
        "Content-Type": "application/json",
        "Idempotency-Key": chaveIdempotencia,
      },
      body: JSON.stringify({
        from: o.remetente,
        to: [email.para],
        subject: email.assunto,
        html: email.html,
        text: email.texto,
      }),
    });
    if (!r.ok) {
      let detalhe = "";
      try {
        detalhe = ((await r.json()) as { message?: string }).message ?? "";
      } catch {
        // corpo sem JSON: fica só o código
      }
      throw new Error(`Resend ${r.status}${detalhe ? `: ${detalhe}` : ""}`);
    }
  };
}
