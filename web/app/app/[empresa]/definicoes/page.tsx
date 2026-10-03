import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { contextoDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import Link from "next/link";
import { Cabecalho, Cartao, classeBotao } from "@/components/ui";
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
      <Cartao className="mt-4 max-w-xl p-6">
        <h2 className="font-medium">Dados da aplicação de secretária</h2>
        <p className="mt-1 text-sm text-texto-2">Traga as tarefas do tarefas.db, com prazos e datas de conclusão.</p>
        <Link href={`/app/${id}/importar`} className={classeBotao("secundario", "mt-4")}>Importar do desktop</Link>
      </Cartao>
    </>
  );
}
