import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { clienteServidor } from "@/lib/supabase/servidor";
import { caminhoSeguro } from "@/lib/dominio/erros";
import { Cartao } from "@/components/ui";
import { Formularios } from "./formularios";

export const metadata: Metadata = { title: "Entrar" };

export default async function PaginaEntrar({
  searchParams,
}: {
  searchParams: Promise<{ seguinte?: string; modo?: string; erro?: string; conta?: string }>;
}) {
  const { seguinte, modo, erro, conta } = await searchParams;
  const destino = caminhoSeguro(seguinte);

  const supabase = await clienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect(destino);

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-4 py-12">
      <Link href="/" className="mb-8 text-center text-lg font-semibold tracking-tight">
        Gerenciador de Tarefas
      </Link>
      <Cartao className="p-6">
        {erro && (
          <p role="alert" className="mb-4 rounded-lg bg-perigo-suave px-3 py-2 text-sm text-perigo">
            A ligação expirou ou já foi usada. Peça outra.
          </p>
        )}
        {conta === "apagada" && (
          <p role="status" className="mb-4 rounded-lg bg-superficie-2 px-3 py-2 text-sm">
            A sua conta foi apagada.
          </p>
        )}
        <Formularios seguinte={destino} modoInicial={modo === "registar" ? "registar" : "entrar"} />
      </Cartao>
    </main>
  );
}
