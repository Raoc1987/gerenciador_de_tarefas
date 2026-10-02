import { NextResponse, type NextRequest } from "next/server";
import { entregar } from "@/lib/emails/carteiro";
import { envioConfigurado } from "@/lib/emails/configuracao";
import { pedidoAutorizado } from "@/lib/emails/cron";
import { filaDeEmails } from "@/lib/supabase/servico";
import { urlDoSite } from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

// Chamada pelo Vercel Cron (vercel.json): entrega um lote da fila.
export async function GET(request: NextRequest) {
  if (!pedidoAutorizado(request.headers.get("authorization"), process.env.CRON_SECRET)) {
    return NextResponse.json({ erro: "não autorizado" }, { status: 401 });
  }
  const enviar = envioConfigurado();
  if (!enviar) {
    // Sem fornecedor, não se reclama nada: a fila espera intacta.
    return NextResponse.json({ erro: "envio de email não configurado" }, { status: 503 });
  }
  const balanco = await entregar({ fila: filaDeEmails(), enviar, site: urlDoSite(), limite: 50 });
  return NextResponse.json(balanco);
}
