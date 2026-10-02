import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { Cabecalho } from "@/components/ui";
import { Importador } from "./importador";

export const metadata: Metadata = { title: "Importar do desktop" };

export default async function Importar({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { empresa, papel } = await contextoDaEmpresa(id);
  if (!pode(papel, "pessoas.gerir")) notFound();
  const pessoas = await pessoasDaEmpresa(id);

  return (
    <>
      <Cabecalho
        titulo="Importar do desktop"
        descricao={`Traga as tarefas da aplicação de secretária para ${empresa.nome}.`}
      />
      <Importador
        empresaId={id}
        membros={pessoas.map((p) => ({ id: p.id, nome: p.nome || p.email, email: p.email }))}
      />
    </>
  );
}
