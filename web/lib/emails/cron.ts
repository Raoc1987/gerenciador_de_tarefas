import { timingSafeEqual } from "node:crypto";

/**
 * O Vercel Cron chama as rotas com `Authorization: Bearer <CRON_SECRET>`.
 * Comparação em tempo constante, e sem segredo configurado ninguém entra.
 */
export function pedidoAutorizado(cabecalho: string | null, segredo: string | undefined): boolean {
  if (!segredo || segredo.length < 16 || !cabecalho) return false;
  const esperado = Buffer.from(`Bearer ${segredo}`);
  const recebido = Buffer.from(cabecalho);
  return esperado.length === recebido.length && timingSafeEqual(esperado, recebido);
}
