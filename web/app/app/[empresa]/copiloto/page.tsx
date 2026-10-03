import type { Metadata } from "next";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { Cabecalho } from "@/components/ui";
import { Conversa } from "./conversa";

export const metadata: Metadata = { title: "Copiloto" };
// Uma pergunta pode precisar de várias voltas ao modelo.
export const maxDuration = 120;

export default async function Copiloto({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { papel } = await contextoDaEmpresa(id);
  const pessoas = await pessoasDaEmpresa(id);

  return (
    <>
      <Cabecalho
        titulo="Copiloto"
        descricao="Pergunte em linguagem natural. O Copiloto vê o mesmo que você, e não muda nada sem o seu clique."
      />
      <Conversa
        empresaId={id}
        podeAplicar={pode(papel, "tarefas.criar")}
        configurado={!!process.env.ANTHROPIC_API_KEY}
        nomes={Object.fromEntries(pessoas.map((p) => [p.id, p.nome || p.email]))}
      />
    </>
  );
}
