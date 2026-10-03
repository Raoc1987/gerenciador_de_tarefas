import type { Metadata } from "next";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { DESCRICAO_PAPEL, PAPEIS, papeisAtribuiveis, papeisConvidaveis, pode, ROTULO_PAPEL, type Papel } from "@/lib/dominio/papeis";
import { formatarData } from "@/lib/dominio/datas";
import { urlDoSite } from "@/lib/supabase/config";
import { emailsLigados } from "@/lib/emails/configuracao";
import { Cabecalho, Cartao } from "@/components/ui";
import { Convidar, LinhaConvite, LinhaMembro } from "./gestao";

export const metadata: Metadata = { title: "Equipa" };

export default async function Equipa({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { supabase, papel, user } = await contextoDaEmpresa(id);
  const pessoas = await pessoasDaEmpresa(id);
  const gere = pode(papel, "pessoas.gerir");

  // A RLS só devolve convites a quem administra.
  const { data: convites } = gere
    ? await supabase
        .from("convites")
        .select("id, email, papel, token, expira_em")
        .eq("empresa_id", id)
        .is("aceite_em", null)
        .order("criado_em", { ascending: false })
    : { data: [] };

  return (
    <>
      <Cabecalho titulo="Equipa" descricao={`${pessoas.length} ${pessoas.length === 1 ? "pessoa" : "pessoas"} nesta empresa.`} />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Cartao className="divide-y divide-borda">
            {pessoas.map((p) => (
              <LinhaMembro
                key={p.id}
                empresaId={id}
                pessoa={{ id: p.id, nome: p.nome || p.email, email: p.email, papel: p.papel, desde: formatarData(p.entrou_em) }}
                souEu={p.id === user.id}
                opcoes={papeisAtribuiveis(papel, p.papel)}
                podeRemover={p.id === user.id || papeisAtribuiveis(papel, p.papel).length > 0}
              />
            ))}
          </Cartao>

          {gere && (convites ?? []).length > 0 && (
            <section>
              <h2 className="mb-3 font-medium">Convites pendentes</h2>
              <Cartao className="divide-y divide-borda">
                {(convites ?? []).map((c) => (
                  <LinhaConvite
                    key={c.id as string}
                    empresaId={id}
                    convite={{
                      id: c.id as string,
                      email: c.email as string,
                      papel: ROTULO_PAPEL[c.papel as Papel],
                      expira: formatarData(c.expira_em as string),
                      ligacao: `${urlDoSite()}/convite/${c.token}`,
                    }}
                  />
                ))}
              </Cartao>
            </section>
          )}
        </div>

        <aside className="space-y-6">
          {gere && (
            <Cartao className="p-5">
              <h2 className="mb-1 font-medium">Convidar</h2>
              <p className="mb-4 text-sm text-texto-2">
                {emailsLigados()
                  ? "A pessoa recebe a ligação por email; também a pode copiar da lista. "
                  : "Recebe uma ligação para partilhar. "}
                O convite só serve para a conta com esse email e expira em 7 dias.
              </p>
              <Convidar empresaId={id} papeis={papeisConvidaveis(papel)} porEmail={emailsLigados()} />
            </Cartao>
          )}
          <Cartao className="p-5">
            <h2 className="mb-3 font-medium">Papéis</h2>
            <dl className="space-y-2.5 text-sm">
              {PAPEIS.map((p) => (
                <div key={p}>
                  <dt className="font-medium">{ROTULO_PAPEL[p]}</dt>
                  <dd className="text-texto-2">{DESCRICAO_PAPEL[p]}</dd>
                </div>
              ))}
            </dl>
          </Cartao>
        </aside>
      </div>
    </>
  );
}
