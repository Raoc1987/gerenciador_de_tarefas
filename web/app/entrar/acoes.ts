"use server";

import { redirect } from "next/navigation";
import { clienteServidor } from "@/lib/supabase/servidor";
import { urlDoSite } from "@/lib/supabase/config";
import { caminhoSeguro } from "@/lib/dominio/erros";

export interface EstadoEntrada {
  erro?: string;
  aviso?: string;
}

const texto = (f: FormData, k: string) => String(f.get(k) ?? "").trim();

export async function entrar(_: EstadoEntrada, form: FormData): Promise<EstadoEntrada> {
  const email = texto(form, "email");
  const senha = String(form.get("senha") ?? "");
  if (!email || !senha) return { erro: "Indique o email e a palavra-passe." };

  const supabase = await clienteServidor();
  const { error } = await supabase.auth.signInWithPassword({ email, password: senha });
  // A mesma mensagem para email inexistente e palavra-passe errada: não se
  // confirma a ninguém que uma conta existe.
  if (error) return { erro: "Email ou palavra-passe incorretos." };
  redirect(caminhoSeguro(texto(form, "seguinte")));
}

export async function registar(_: EstadoEntrada, form: FormData): Promise<EstadoEntrada> {
  const nome = texto(form, "nome");
  const email = texto(form, "email");
  const senha = String(form.get("senha") ?? "");
  if (!nome || !email) return { erro: "Indique o nome e o email." };
  if (senha.length < 10) return { erro: "A palavra-passe tem de ter pelo menos 10 caracteres." };

  const supabase = await clienteServidor();
  const seguinte = caminhoSeguro(texto(form, "seguinte"));
  const { data, error } = await supabase.auth.signUp({
    email,
    password: senha,
    options: {
      data: { nome },
      emailRedirectTo: `${urlDoSite()}/auth/callback?seguinte=${encodeURIComponent(seguinte)}`,
    },
  });
  if (error) return { erro: "Não foi possível criar a conta. Verifique o email e tente outra vez." };
  if (data.session) redirect(seguinte);
  return { aviso: "Enviámos um email de confirmação. Abra a ligação para entrar." };
}

export async function ligacaoMagica(_: EstadoEntrada, form: FormData): Promise<EstadoEntrada> {
  const email = texto(form, "email");
  if (!email) return { erro: "Indique o email." };
  const supabase = await clienteServidor();
  const seguinte = caminhoSeguro(texto(form, "seguinte"));
  await supabase.auth.signInWithOtp({
    email,
    options: {
      shouldCreateUser: false,
      emailRedirectTo: `${urlDoSite()}/auth/callback?seguinte=${encodeURIComponent(seguinte)}`,
    },
  });
  // Sempre a mesma resposta, exista a conta ou não.
  return { aviso: "Se houver uma conta com esse email, a ligação de entrada está a caminho." };
}
