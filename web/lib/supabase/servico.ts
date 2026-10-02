// A ÚNICA utilização da chave de serviço nesta aplicação (ADR-0019).
//
// Os emails entregam-se fora de qualquer sessão, por isso o carteiro não pode
// usar a sessão de ninguém. Em vez de expor um cliente com a chave — que
// contorna a RLS para tudo —, este módulo só oferece as três operações de que
// o carteiro precisa, e as três são funções da base que só `service_role`
// pode chamar. `lib/arquitetura.test.ts` falha se a chave aparecer noutro
// ficheiro, ou se este módulo for importado fora de app/api/cron/.

import { createClient } from "@supabase/supabase-js";
import type { Fila } from "@/lib/emails/carteiro";
import type { EmailPendente } from "@/lib/dominio/emails";
import { configSupabase } from "./config";

function cliente() {
  const chave = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!chave) throw new Error("Falta SUPABASE_SERVICE_ROLE_KEY (só no servidor; ver web/README.md).");
  return createClient(configSupabase().url, chave, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export function filaDeEmails(): Fila {
  const c = cliente();
  return {
    async reclamar(limite) {
      const { data, error } = await c.rpc("reclamar_emails", { p_limite: limite });
      if (error) throw new Error(`reclamar_emails: ${error.message}`);
      return (data ?? []) as EmailPendente[];
    },
    async marcar(id, ok, erro) {
      const { error } = await c.rpc("marcar_email", { p_id: id, p_ok: ok, p_erro: erro ?? null });
      if (error) throw new Error(`marcar_email: ${error.message}`);
    },
  };
}

export async function enfileirarResumos(hoje: string): Promise<number> {
  const { data, error } = await cliente().rpc("enfileirar_resumos", { p_hoje: hoje });
  if (error) throw new Error(`enfileirar_resumos: ${error.message}`);
  return (data as number) ?? 0;
}
