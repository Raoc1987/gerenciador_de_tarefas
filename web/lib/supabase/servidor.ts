import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { configSupabase } from "./config";

/**
 * Cliente Supabase para Server Components, Server Actions e Route Handlers.
 * Fala com a base **como a pessoa em sessão**: a RLS aplica-se a tudo o que
 * passa por aqui. Não há, de propósito, nenhum cliente com a chave de
 * serviço nesta aplicação.
 */
export async function clienteServidor() {
  const { url, chave } = configSupabase();
  const jar = await cookies();
  return createServerClient(url, chave, {
    cookies: {
      getAll: () => jar.getAll(),
      setAll(lista) {
        try {
          for (const { name, value, options } of lista) jar.set(name, value, options);
        } catch {
          // Num Server Component não se escrevem cookies; o proxy renova a
          // sessão no pedido seguinte.
        }
      },
    },
  });
}
