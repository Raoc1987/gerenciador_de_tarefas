"use client";

import { useActionState } from "react";
import { apagarConta } from "./acoes";
import { Aviso, Botao, Campo, classeEntrada } from "@/components/ui";

export function FormularioApagarConta({ empresaId }: { empresaId: string }) {
  const [estado, submeter, aEnviar] = useActionState(apagarConta.bind(null, empresaId), {});
  return (
    <form action={submeter} className="space-y-4">
      <Campo rotulo="Para confirmar, escreva o email da sua conta">
        <input name="confirmacao" type="email" required autoComplete="off" className={classeEntrada} />
      </Campo>
      <Aviso>{estado.erro}</Aviso>
      <Botao type="submit" variante="perigo" disabled={aEnviar}>
        {aEnviar ? "A apagar…" : "Apagar a minha conta"}
      </Botao>
    </form>
  );
}
