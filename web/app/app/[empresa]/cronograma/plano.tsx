"use client";

import { useActionState } from "react";
import { definirPlano } from "./acoes";

/** Duração e início mínimo de uma linha do cronograma, editáveis no sítio. */
export function EditarPlano({
  empresaId, tarefaId, duracao, inicioMinimo, titulo,
}: {
  empresaId: string;
  tarefaId: string;
  duracao: number | null;
  inicioMinimo: string | null;
  titulo: string;
}) {
  const [estado, submeter, aEnviar] = useActionState(definirPlano.bind(null, empresaId, tarefaId), {});
  return (
    <form action={submeter} className="flex items-center gap-1.5">
      <label className="sr-only" htmlFor={`dur-${tarefaId}`}>Duração de {titulo}, em dias úteis</label>
      <input
        id={`dur-${tarefaId}`}
        name="duracao_dias"
        type="number"
        min={0}
        max={1000}
        defaultValue={duracao ?? ""}
        placeholder="1"
        title="Dias úteis (0 = marco). Em branco conta como 1."
        className="w-16 rounded-md border border-borda bg-superficie px-2 py-1 text-sm tabular-nums"
      />
      <label className="sr-only" htmlFor={`ini-${tarefaId}`}>{titulo} não começa antes de</label>
      <input
        id={`ini-${tarefaId}`}
        name="inicio_minimo"
        type="date"
        defaultValue={inicioMinimo ?? ""}
        title="Não começa antes de"
        className="w-36 rounded-md border border-borda bg-superficie px-2 py-1 text-sm"
      />
      <button
        type="submit"
        disabled={aEnviar}
        className="rounded-md border border-borda px-2 py-1 text-xs hover:bg-superficie-2 disabled:opacity-50"
      >
        {aEnviar ? "…" : "Gravar"}
      </button>
      {estado.erro && <span role="alert" className="text-xs text-perigo">{estado.erro}</span>}
    </form>
  );
}
