import { NextResponse, type NextRequest } from "next/server";
import { clienteServidor } from "@/lib/supabase/servidor";
import { caminhoSeguro } from "@/lib/dominio/erros";

// Destino das ligações de email (confirmação de conta e entrada sem
// palavra-passe): troca o código por uma sessão e segue.
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const codigo = searchParams.get("code");
  const seguinte = caminhoSeguro(searchParams.get("seguinte"));

  if (codigo) {
    const supabase = await clienteServidor();
    const { error } = await supabase.auth.exchangeCodeForSession(codigo);
    if (!error) return NextResponse.redirect(`${origin}${seguinte}`);
  }
  return NextResponse.redirect(`${origin}/entrar?erro=ligacao`);
}
