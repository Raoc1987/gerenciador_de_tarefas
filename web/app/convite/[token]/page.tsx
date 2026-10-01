import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { clienteServidor } from "@/lib/supabase/servidor";
import { mensagemDeErro } from "@/lib/dominio/erros";
import { Cartao, classeBotao } from "@/components/ui";

export const metadata: Metadata = { title: "Convite" };

// Abrir a ligação de um convite: sem sessão, vai criar conta ou entrar e
// volta aqui; com sessão, aceita e entra na empresa.
export default async function Convite({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const supabase = await clienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/entrar?modo=registar&seguinte=${encodeURIComponent(`/convite/${token}`)}`);
  }

  const { data: empresa, error } = await supabase.rpc("aceitar_convite", { p_token: token });
  if (!error && empresa) redirect(`/app/${empresa}`);

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-4">
      <Cartao className="space-y-4 p-6 text-center">
        <h1 className="text-lg font-semibold">Não foi possível aceitar o convite</h1>
        <p className="text-sm text-texto-2">{mensagemDeErro(error)}</p>
        <p className="text-sm text-texto-2">
          Está em sessão como <strong>{user.email}</strong>. O convite tem de ser aberto com a conta do email
          para que foi enviado.
        </p>
        <Link href="/app" className={classeBotao("secundario")}>
          Ir para as minhas empresas
        </Link>
      </Cartao>
    </main>
  );
}
