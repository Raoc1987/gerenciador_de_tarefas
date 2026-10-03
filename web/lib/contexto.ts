import { cache } from "react";
import { notFound, redirect } from "next/navigation";
import { clienteServidor } from "@/lib/supabase/servidor";
import type { Papel } from "@/lib/dominio/papeis";

export interface Empresa {
  id: string;
  nome: string;
  segregacao_funcoes: boolean;
}

export interface Pessoa {
  id: string;
  nome: string;
  email: string;
}

/** Quem está em sessão. Sem sessão, vai para o login. */
export const exigirSessao = cache(async () => {
  const supabase = await clienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/entrar");
  return { supabase, user };
});

/**
 * A empresa do URL e o papel de quem está em sessão nela. Uma empresa de
 * que a pessoa não é membro dá 404 — não 403: nem se confirma que existe.
 */
export const contextoDaEmpresa = cache(async (empresaId: string) => {
  const { supabase, user } = await exigirSessao();
  const [{ data: empresa }, { data: membro }] = await Promise.all([
    supabase.from("empresas").select("id, nome, segregacao_funcoes").eq("id", empresaId).maybeSingle(),
    supabase.from("membros").select("papel").eq("empresa_id", empresaId).eq("user_id", user.id).maybeSingle(),
  ]);
  if (!empresa || !membro) notFound();
  return { supabase, user, empresa: empresa as Empresa, papel: membro.papel as Papel };
});

export interface Membro extends Pessoa {
  papel: Papel;
  entrou_em: string;
}

export const pessoasDaEmpresa = cache(async (empresaId: string): Promise<Membro[]> => {
  const { supabase } = await exigirSessao();
  const { data: membros } = await supabase
    .from("membros")
    .select("user_id, papel, entrou_em")
    .eq("empresa_id", empresaId);
  const ids = (membros ?? []).map((m) => m.user_id as string);
  const { data: perfis } = ids.length
    ? await supabase.from("perfis").select("id, nome, email").in("id", ids)
    : { data: [] };
  const porId = new Map<string, Pessoa>((perfis ?? []).map((p: Pessoa) => [p.id, p]));
  return (membros ?? [])
    .map((m) => ({
      id: m.user_id as string,
      papel: m.papel as Papel,
      entrou_em: m.entrou_em as string,
      nome: porId.get(m.user_id)?.nome ?? "",
      email: porId.get(m.user_id)?.email ?? "",
    }))
    .sort((a, b) => (a.nome || a.email).localeCompare(b.nome || b.email, "pt"));
});
