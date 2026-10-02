import { enviarComResend, type Enviar } from "./carteiro.ts";

/** O envio configurado, ou `null` se faltar a chave ou o remetente. */
export function envioConfigurado(): Enviar | null {
  const chave = process.env.RESEND_API_KEY;
  const remetente = process.env.EMAIL_REMETENTE;
  if (!chave || !remetente) return null;
  return enviarComResend({ chave, remetente });
}

/** Se há fornecedor configurado. A chave de serviço verifica-a o próprio carteiro. */
export function emailsLigados(): boolean {
  return !!(process.env.RESEND_API_KEY && process.env.EMAIL_REMETENTE);
}
