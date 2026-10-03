import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { contextoDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { Cabecalho, Cartao } from "@/components/ui";
import { FormularioDefinicoes } from "./formulario";

export const metadata: Metadata = { title: "Definições" };

export default async function Definicoes({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { empresa, papel } = await contextoDaEmpresa(id);
  if (!pode(papel, "definicoes.editar")) notFound();
  return (
    <>
      <Cabecalho titulo="Definições" descricao="O que vale para toda a empresa." />
      <Cartao className="max-w-xl p-6">
        <FormularioDefinicoes empresa={empresa} />
      </Cartao>
    </>
  );
}
