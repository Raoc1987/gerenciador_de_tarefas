import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { exigirSessao } from "@/lib/contexto";
import { ROTULO_PAPEL, type Papel } from "@/lib/dominio/papeis";
import { Cartao, Selo } from "@/components/ui";
import { NovaEmpresa } from "./nova-empresa";

export const metadata: Metadata = { title: "As suas empresas" };

export default async function Empresas({ searchParams }: { searchParams: Promise<{ escolher?: string }> }) {
  const { supabase, user } = await exigirSessao();
  const { escolher } = await searchParams;
  const { data } = await supabase
    .from("membros")
    .select("papel, empresas (id, nome)")
    .eq("user_id", user.id);
  const empresas = ((data ?? []) as unknown as { papel: Papel; empresas: { id: string; nome: string } | null }[])
    .filter((m) => m.empresas)
    .map((m) => ({ ...m.empresas!, papel: m.papel }))
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt"));

  // Com uma só empresa não há nada a escolher.
  if (empresas.length === 1 && !escolher) redirect(`/app/${empresas[0].id}`);

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">As suas empresas</h1>
        <form action="/sair" method="post">
          <button className="text-sm text-texto-2 hover:text-texto">Sair</button>
        </form>
      </div>

      {empresas.length > 0 && (
        <ul className="mb-10 space-y-2">
          {empresas.map((e) => (
            <li key={e.id}>
              <Link
                href={`/app/${e.id}`}
                className="flex items-center justify-between rounded-[var(--radius-cartao)] border border-borda bg-superficie px-4 py-3 hover:border-marca"
              >
                <span className="font-medium">{e.nome}</span>
                <Selo>{ROTULO_PAPEL[e.papel]}</Selo>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Cartao className="p-6">
        <h2 className="mb-1 font-medium">{empresas.length ? "Criar outra empresa" : "Comece pela sua empresa"}</h2>
        <p className="mb-4 text-sm text-texto-2">
          Fica como proprietário e pode convidar a equipa a seguir. Se foi convidado para uma empresa, abra a
          ligação do convite.
        </p>
        <NovaEmpresa />
      </Cartao>
    </main>
  );
}
