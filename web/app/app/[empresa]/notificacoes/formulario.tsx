"use client";

import { useActionState } from "react";
import { gravarPreferencias } from "./acoes";
import { Aviso, Botao } from "@/components/ui";

const OPCOES = [
  ["atribuicoes", "Quando me atribuem uma tarefa", "Um email com o título, o prazo e a ligação para a tarefa."],
  ["comentarios", "Quando comentam uma tarefa minha", "Tarefas que lhe estão atribuídas ou que criou. Os seus próprios comentários não geram aviso."],
  ["resumo_diario", "Resumo da manhã", "Nos dias úteis, só se tiver tarefas atrasadas ou a vencer nesse dia."],
] as const;

export function FormularioPreferencias({
  empresaId,
  valores,
}: {
  empresaId: string;
  valores: Record<(typeof OPCOES)[number][0], boolean>;
}) {
  const [estado, submeter, aEnviar] = useActionState(gravarPreferencias.bind(null, empresaId), {});
  return (
    <form action={submeter} className="space-y-5">
      {OPCOES.map(([nome, rotulo, ajuda]) => (
        <label key={nome} className="flex gap-3">
          <input type="checkbox" name={nome} defaultChecked={valores[nome]} className="mt-1" />
          <span>
            <span className="block text-sm font-medium">{rotulo}</span>
            <span className="block text-sm text-texto-2">{ajuda}</span>
          </span>
        </label>
      ))}
      <Aviso>{estado.erro}</Aviso>
      {estado.ok && <Aviso tom="sucesso">Preferências gravadas.</Aviso>}
      <Botao type="submit" disabled={aEnviar}>{aEnviar ? "A gravar…" : "Gravar"}</Botao>
    </form>
  );
}
