import { NextResponse, type NextRequest } from "next/server";
import { entregar } from "@/lib/emails/carteiro";
import { envioConfigurado } from "@/lib/emails/configuracao";
import { pedidoAutorizado } from "@/lib/emails/cron";
import { hojeNoFuso } from "@/lib/dominio/datas";
import { enfileirarResumos, filaDeEmails } from "@/lib/supabase/servico";
import { urlDoSite } from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

// Uma vez por dia de manhã: põe na fila o resumo de cada pessoa com tarefas
// atrasadas ou a vencer hoje, e entrega logo um primeiro lote.
export async function GET(request: NextRequest) {
  if (!pedidoAutorizado(request.headers.get("authorization"), process.env.CRON_SECRET)) {
    return NextResponse.json({ erro: "não autorizado" }, { status: 401 });
  }
  const enviar = envioConfigurado();
  if (!enviar) return NextResponse.json({ erro: "envio de email não configurado" }, { status: 503 });
  const enfileirados = await enfileirarResumos(hojeNoFuso());
  const balanco = await entregar({ fila: filaDeEmails(), enviar, site: urlDoSite(), limite: 100 });
  return NextResponse.json({ enfileirados, ...balanco });
}
