"use client";
import { createBrowserClient } from "@supabase/ssr";

let cliente: ReturnType<typeof createBrowserClient> | undefined;

/** Cliente do browser — usado só para o tempo real. Escrever passa por Server Actions. */
export function clienteBrowser() {
  if (!cliente) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
    const chave =
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
    cliente = createBrowserClient(url, chave);
  }
  return cliente;
}
