import { NextResponse, type NextRequest } from "next/server";
import { clienteServidor } from "@/lib/supabase/servidor";

// Só POST: um <img src="/sair"> noutro site não termina a sessão de ninguém.
export async function POST(request: NextRequest) {
  const supabase = await clienteServidor();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/entrar", request.url), { status: 303 });
}
