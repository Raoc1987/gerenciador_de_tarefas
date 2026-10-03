"use client";

import { useActionState } from "react";
import type { Empresa } from "@/lib/contexto";
import { gravarDefinicoes } from "./acoes";
import { Aviso, Botao, Campo, classeEntrada } from "@/components/ui";

export function FormularioDefinicoes({ empresa }: { empresa: Empresa }) {
  const [estado, submeter, aEnviar] = useActionState(gravarDefinicoes.bind(null, empresa.id), {});
  return (
    <form action={submeter} className="space-y-5">
      <Campo rotulo="Nome da empresa">
        <input name="nome" defaultValue={empresa.nome} required minLength={2} maxLength={120} className={classeEntrada} />
      </Campo>
      <label className="flex gap-3">
        <input type="checkbox" name="segregacao_funcoes" defaultChecked={empresa.segregacao_funcoes} className="mt-1" />
        <span>
          <span className="block text-sm font-medium">Segregação de funções</span>
          <span className="block text-sm text-texto-2">
            Quem cria uma tarefa não a pode dar por concluída — nem um administrador. Útil para aprovações e
            controlo interno.
          </span>
        </span>
      </label>
      <Aviso>{estado.erro}</Aviso>
      {estado.ok && <Aviso tom="sucesso">Definições gravadas.</Aviso>}
      <Botao type="submit" disabled={aEnviar}>{aEnviar ? "A gravar…" : "Gravar"}</Botao>
    </form>
  );
}
