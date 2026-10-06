"use server";

import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { mensagemDeErro } from "@/lib/dominio/erros";
import { configuracaoStripe, fornecedorStripe, PLANOS_PAGOS, type PlanoPago } from "@/lib/faturacao/stripe";
import { urlDoSite } from "@/lib/supabase/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Quem pode pagar decide-o a base (preparar_faturacao: só a pessoa
// proprietária). Daqui só sai o pedido ao fornecedor e o redirecionamento
// para a página dele; o plano muda quando o webhook confirmar o pagamento.
async function preparar(empresaId: string) {
  if (!UUID.test(empresaId)) return { erro: "Empresa inválida." } as const;
  const config = configuracaoStripe();
  if (!config) return { erro: "A faturação ainda não está ligada nesta instalação." } as const;
  const { supabase } = await exigirSessao();
  const { data, error } = await supabase.rpc("preparar_faturacao", { p_empresa: empresaId });
  if (error) return { erro: mensagemDeErro(error) } as const;
  const dados = data as { cliente: string | null; email: string | null };
  return { config, dados, voltar: `${urlDoSite()}/app/${empresaId}/plano` } as const;
}

export async function assinar(empresaId: string, plano: string): Promise<{ erro?: string }> {
  if (!(PLANOS_PAGOS as readonly string[]).includes(plano)) return { erro: "Plano desconhecido." };
  const p = await preparar(empresaId);
  if ("erro" in p) return { erro: p.erro };
  let url: string;
  try {
    url = await fornecedorStripe(p.config.chave, p.config.precos).checkout({
      empresa: empresaId, plano: plano as PlanoPago, email: p.dados.email, cliente: p.dados.cliente, voltar: p.voltar,
    });
  } catch {
    return { erro: "Não foi possível abrir o pagamento. Tente daqui a pouco." };
  }
  redirect(url);
}

export async function gerirFaturacao(empresaId: string): Promise<{ erro?: string }> {
  const p = await preparar(empresaId);
  if ("erro" in p) return { erro: p.erro };
  if (!p.dados.cliente) return { erro: "Esta empresa ainda não tem faturação." };
  let url: string;
  try {
    url = await fornecedorStripe(p.config.chave, p.config.precos).portal({ cliente: p.dados.cliente, voltar: p.voltar });
  } catch {
    return { erro: "Não foi possível abrir a faturação. Tente daqui a pouco." };
  }
  redirect(url);
}
