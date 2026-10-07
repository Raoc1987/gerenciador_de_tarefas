import { NextResponse, type NextRequest } from "next/server";
import { assinaturaValida, configuracaoStripe, interpretarEvento } from "@/lib/faturacao/stripe";
import { aplicarFaturacao } from "@/lib/supabase/servico";

export const dynamic = "force-dynamic";

// Avisos do Stripe sobre pagamentos e subscrições (ADR-0025). A assinatura
// verifica-se sobre o corpo exato que chegou, antes de o ler como JSON; só
// depois se toca na base, e só pela função aplicar_faturacao, que ignora
// eventos repetidos ou antigos.
export async function POST(request: NextRequest) {
  const config = configuracaoStripe();
  const corpo = await request.text();
  if (!config || !assinaturaValida(corpo, request.headers.get("stripe-signature"), config.segredoWebhook)) {
    return NextResponse.json({ erro: "assinatura inválida" }, { status: 400 });
  }
  let evento: unknown;
  try {
    evento = JSON.parse(corpo);
  } catch {
    return NextResponse.json({ erro: "corpo inválido" }, { status: 400 });
  }
  const mudanca = interpretarEvento(evento, config.porPreco);
  if (!mudanca) return NextResponse.json({ ignorado: true });
  const aplicado = await aplicarFaturacao(mudanca);
  return NextResponse.json({ aplicado });
}
