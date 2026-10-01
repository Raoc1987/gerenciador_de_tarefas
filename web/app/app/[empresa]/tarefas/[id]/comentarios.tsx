"use client";

import { useActionState, useEffect, useRef } from "react";
import { comentar } from "../acoes";
import { Aviso, Botao, Cartao, classeEntrada } from "@/components/ui";

interface Comentario {
  id: string;
  autor: string;
  corpo: string;
  quando: string;
}

export function Comentarios({
  empresaId, tarefaId, comentarios, podeComentar,
}: {
  empresaId: string;
  tarefaId: string;
  comentarios: Comentario[];
  podeComentar: boolean;
}) {
  const [estado, submeter, aEnviar] = useActionState(comentar.bind(null, empresaId, tarefaId), {});
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (estado.ok) form.current?.reset();
  }, [estado.ok]);

  return (
    <section aria-labelledby="comentarios-titulo">
      <h2 id="comentarios-titulo" className="mb-3 font-medium">
        Comentários <span className="text-sm font-normal text-texto-2">({comentarios.length})</span>
      </h2>
      <ol className="space-y-3">
        {comentarios.map((c) => (
          <li key={c.id}>
            <Cartao className="p-4">
              <p className="text-xs text-texto-2">
                <span className="font-medium text-texto">{c.autor}</span> · {c.quando}
              </p>
              <p className="mt-1.5 whitespace-pre-wrap text-sm">{c.corpo}</p>
            </Cartao>
          </li>
        ))}
      </ol>
      {podeComentar && (
        <form ref={form} action={submeter} className="mt-4 space-y-2">
          <label htmlFor="novo-comentario" className="sr-only">Novo comentário</label>
          <textarea id="novo-comentario" name="corpo" rows={3} maxLength={5000} required placeholder="Escreva um comentário…" className={classeEntrada} />
          <Aviso>{estado.erro}</Aviso>
          <div className="flex justify-end">
            <Botao type="submit" disabled={aEnviar}>{aEnviar ? "A enviar…" : "Comentar"}</Botao>
          </div>
        </form>
      )}
    </section>
  );
}
