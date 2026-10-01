"use client";

import { useActionState, useState } from "react";
import { entrar, ligacaoMagica, registar, type EstadoEntrada } from "./acoes";
import { Aviso, Botao, Campo, classeEntrada } from "@/components/ui";

type Modo = "entrar" | "registar" | "magica";

export function Formularios({ seguinte, modoInicial }: { seguinte: string; modoInicial: Modo }) {
  const [modo, setModo] = useState<Modo>(modoInicial);

  return (
    <div className="space-y-6">
      <div role="tablist" aria-label="Forma de entrar" className="grid grid-cols-2 gap-1 rounded-lg bg-superficie-2 p-1 text-sm">
        {(["entrar", "registar"] as const).map((m) => (
          <button
            key={m}
            role="tab"
            type="button"
            aria-selected={modo === m || (m === "entrar" && modo === "magica")}
            onClick={() => setModo(m)}
            className={`rounded-md py-1.5 font-medium ${
              modo === m || (m === "entrar" && modo === "magica") ? "bg-superficie shadow-sm" : "text-texto-2"
            }`}
          >
            {m === "entrar" ? "Entrar" : "Criar conta"}
          </button>
        ))}
      </div>

      <Formulario key={modo} modo={modo} seguinte={seguinte} />

      {modo !== "registar" && (
        <button
          type="button"
          onClick={() => setModo(modo === "magica" ? "entrar" : "magica")}
          className="w-full text-center text-sm text-marca hover:underline"
        >
          {modo === "magica" ? "Entrar com palavra-passe" : "Entrar sem palavra-passe (ligação por email)"}
        </button>
      )}
    </div>
  );
}

const ACOES = { entrar, registar, magica: ligacaoMagica } as const;

function Formulario({ modo, seguinte }: { modo: Modo; seguinte: string }) {
  const [estado, submeter, aEnviar] = useActionState<EstadoEntrada, FormData>(ACOES[modo], {});
  return (
      <form action={submeter} className="space-y-4">
        <input type="hidden" name="seguinte" value={seguinte} />
        {modo === "registar" && (
          <Campo rotulo="Nome">
            <input name="nome" autoComplete="name" required className={classeEntrada} />
          </Campo>
        )}
        <Campo rotulo="Email">
          <input name="email" type="email" autoComplete="email" required className={classeEntrada} />
        </Campo>
        {modo !== "magica" && (
          <Campo rotulo="Palavra-passe" ajuda={modo === "registar" ? "Pelo menos 10 caracteres." : undefined}>
            <input
              name="senha"
              type="password"
              autoComplete={modo === "registar" ? "new-password" : "current-password"}
              required
              minLength={modo === "registar" ? 10 : undefined}
              className={classeEntrada}
            />
          </Campo>
        )}

        <Aviso tom="perigo">{estado.erro}</Aviso>
        <Aviso tom="sucesso">{estado.aviso}</Aviso>

        <Botao type="submit" disabled={aEnviar} className="w-full">
          {aEnviar ? "Um momento…" : modo === "entrar" ? "Entrar" : modo === "registar" ? "Criar conta" : "Enviar ligação"}
        </Botao>
      </form>
  );
}
