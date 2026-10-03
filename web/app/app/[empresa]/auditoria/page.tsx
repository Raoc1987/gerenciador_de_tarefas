import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { formatarDataHora } from "@/lib/dominio/datas";
import { camposAlterados, descreverAcao, tituloDaLinha, type LinhaAuditoria } from "@/lib/dominio/auditoria";
import { Cabecalho, Cartao, Vazio, classeBotao } from "@/components/ui";

export const metadata: Metadata = { title: "Auditoria" };

const POR_PAGINA = 50;

function valor(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
  return String(v);
}

export default async function Auditoria({
  params,
  searchParams,
}: {
  params: Promise<{ empresa: string }>;
  searchParams: Promise<{ antes?: string }>;
}) {
  const { empresa: id } = await params;
  const { antes } = await searchParams;
  const { supabase, papel } = await contextoDaEmpresa(id);
  if (!pode(papel, "auditoria.ler")) notFound();

  // Paginação por cursor (o id é crescente): estável mesmo com linhas novas a entrar.
  let consulta = supabase
    .from("auditoria")
    .select("*")
    .eq("empresa_id", id)
    .order("id", { ascending: false })
    .limit(POR_PAGINA + 1);
  if (antes && /^\d+$/.test(antes)) consulta = consulta.lt("id", Number(antes));
  const [{ data }, pessoas] = await Promise.all([consulta, pessoasDaEmpresa(id)]);

  const linhas = (data ?? []) as LinhaAuditoria[];
  const haMais = linhas.length > POR_PAGINA;
  const pagina = linhas.slice(0, POR_PAGINA);
  const nome = (uid: string | null) => {
    if (!uid) return "Sistema";
    const p = pessoas.find((x) => x.id === uid);
    return p ? p.nome || p.email : "Antigo membro";
  };

  return (
    <>
      <Cabecalho
        titulo="Auditoria"
        descricao="Tudo o que aconteceu nesta empresa. Só de leitura: nem um administrador altera ou apaga estas linhas."
      />
      {pagina.length === 0 ? (
        <Vazio titulo="Nada registado ainda" />
      ) : (
        <Cartao className="divide-y divide-borda">
          {pagina.map((l) => {
            const mudancas = l.acao === "update" ? camposAlterados(l) : [];
            return (
              <article key={l.id} className="px-4 py-3 text-sm">
                <p>
                  <span className="font-medium">{nome(l.actor_id)}</span> {descreverAcao(l)}
                  {tituloDaLinha(l) && <> <span className="text-texto-2">“{tituloDaLinha(l)}”</span></>}
                </p>
                <p className="text-xs text-texto-2">
                  <time dateTime={l.em}>{formatarDataHora(l.em)}</time>
                </p>
                {mudancas.length > 0 && (
                  <ul className="mt-2 space-y-0.5 text-xs">
                    {mudancas.map((m) => (
                      <li key={m.campo}>
                        <code className="text-texto-2">{m.campo}</code>: <del className="text-perigo">{valor(m.antes)}</del> →{" "}
                        <ins className="text-sucesso no-underline">{valor(m.depois)}</ins>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            );
          })}
        </Cartao>
      )}
      {haMais && (
        <div className="mt-4 flex justify-center">
          <Link href={`?antes=${pagina.at(-1)!.id}`} className={classeBotao("secundario")}>
            Mais antigas
          </Link>
        </div>
      )}
    </>
  );
}
