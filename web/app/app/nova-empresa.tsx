"use client";

import { useActionState } from "react";
import { criarEmpresa } from "./acoes";
import { Aviso, Botao, Campo, classeEntrada } from "@/components/ui";

export function NovaEmpresa() {
  const [estado, submeter, aEnviar] = useActionState(criarEmpresa, {});
  return (
    <form action={submeter} className="space-y-3">
      <Campo rotulo="Nome da empresa">
        <input name="nome" required minLength={2} maxLength={120} className={classeEntrada} placeholder="Ex.: Acme Lda." />
      </Campo>
      <Aviso>{estado.erro}</Aviso>
      <Botao type="submit" disabled={aEnviar}>
        {aEnviar ? "A criar…" : "Criar empresa"}
      </Botao>
    </form>
  );
}
