import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { configSupabase } from "./config";

/**
 * Cliente Supabase para Server Components, Server Actions e Route Handlers.
 * Fala com a base **como a pessoa em sessão**: a RLS aplica-se a tudo o que
 * passa por aqui. (A chave de serviço só existe em lib/supabase/servico.ts,
 * para o carteiro de emails — ADR-0019.)
 */
export async function clienteServidor() {
  // Os cookies primeiro: é isto que diz ao Next que a página depende do
  // pedido e não pode ser gerada no build. Ao contrário, sem as variáveis do
  // Supabase o build tentava pré-gerar /app e rebentava com o erro de
  // configuração — que deve aparecer quando a página é aberta, não no build.
  const jar = await cookies();
  const { url, chave } = configSupabase();
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
