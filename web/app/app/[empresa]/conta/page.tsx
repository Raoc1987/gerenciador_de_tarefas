import type { Metadata } from "next";
import { contextoDaEmpresa } from "@/lib/contexto";
import { Cabecalho, Cartao, classeBotao } from "@/components/ui";
import { FormularioApagarConta } from "./formulario";

export const metadata: Metadata = { title: "A minha conta" };

// Os direitos do RGPD sem pedir a ninguém: descarregar os seus dados e
// apagar a conta. Quem decide o que entra e o que se pode apagar é a base
// (exportar_os_meus_dados, apagar_a_minha_conta).
export default async function Conta({ params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: id } = await params;
  const { user } = await contextoDaEmpresa(id);

  return (
    <>
      <Cabecalho titulo="A minha conta" descricao={user.email ?? undefined} />
      <div className="max-w-xl space-y-6">
        <Cartao className="space-y-3 p-6">
          <h2 className="font-medium">Os seus dados</h2>
          <p className="text-sm text-texto-2">
            Um ficheiro JSON com a sua conta, o perfil, as empresas e o papel em cada uma, as tarefas que criou, concluiu
            ou tem atribuídas, os seus comentários e preferências — em todas as empresas, incluindo as que já deixou.
          </p>
          <a href={`/app/${id}/conta/exportar`} download className={classeBotao("secundario")}>
            Descarregar os meus dados
          </a>
        </Cartao>

        <Cartao className="space-y-3 border-perigo/40 p-6">
          <h2 className="font-medium">Apagar a conta</h2>
          <p className="text-sm text-texto-2">
            A conta, o perfil e as suas pertenças a empresas desaparecem. O trabalho fica com as empresas: as tarefas e
            os comentários que escreveu continuam lá, sem o seu nome. Uma empresa onde está sozinha ou sozinho apaga-se
            consigo; se for a única pessoa proprietária de uma empresa com mais gente, passe primeiro a propriedade.
          </p>
          <FormularioApagarConta empresaId={id} />
        </Cartao>
      </div>
    </>
  );
}
