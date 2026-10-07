import { NextResponse } from "next/server";
import { clienteServidor } from "@/lib/supabase/servidor";
import { mensagemDeErro } from "@/lib/dominio/erros";

export const dynamic = "force-dynamic";

// Descarrega os dados da pessoa em sessão (RGPD, direito de acesso e de
// portabilidade). A base escolhe o que entra: exportar_os_meus_dados.
export async function GET() {
  const supabase = await clienteServidor();
  const { data, error } = await supabase.rpc("exportar_os_meus_dados");
  if (error) return NextResponse.json({ erro: mensagemDeErro(error) }, { status: 403 });
  const dia = new Date().toISOString().slice(0, 10);
  return new NextResponse(JSON.stringify(data, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "content-disposition": `attachment; filename="os-meus-dados-${dia}.json"`,
      "cache-control": "no-store",
    },
  });
}
