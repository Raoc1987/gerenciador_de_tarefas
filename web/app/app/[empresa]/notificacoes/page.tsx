import type { Metadata } from "next";
import { contextoDaEmpresa } from "@/lib/contexto";
import { emailsLigados } from "@/lib/emails/configuracao";
import { Aviso, Cabecalho, Cartao } from "@/components/ui";
import { FormularioPreferencias } from "./formulario";

export const metadata: Metadata = { title: "Notificações" };

export default async function Notificacoes({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { supabase, user } = await contextoDaEmpresa(id);
  const { data } = await supabase
    .from("preferencias_notificacao")
    .select("atribuicoes, comentarios, resumo_diario")
    .eq("user_id", user.id)
    .maybeSingle();

  return (
    <>
      <Cabecalho
        titulo="Notificações"
        descricao={`Que emails recebe em ${user.email}. Vale para todas as suas empresas.`}
      />
      <Cartao className="max-w-xl space-y-5 p-6">
        {!emailsLigados() && (
          <Aviso tom="aviso">O envio de emails ainda não está ligado nesta instalação. As suas escolhas ficam guardadas.</Aviso>
        )}
        <FormularioPreferencias
          empresaId={id}
          valores={{
            atribuicoes: data?.atribuicoes ?? true,
            comentarios: data?.comentarios ?? true,
            resumo_diario: data?.resumo_diario ?? true,
          }}
        />
      </Cartao>
    </>
  );
}
