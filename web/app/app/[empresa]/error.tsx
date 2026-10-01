"use client";

import { Botao } from "@/components/ui";

export default function Erro({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-xl font-semibold">Algo correu mal</h1>
      <p className="mt-2 text-sm text-texto-2">
        Não foi possível carregar esta página. Os seus dados não foram afetados.
      </p>
      <Botao variante="secundario" className="mt-6" onClick={reset}>
        Tentar outra vez
      </Botao>
    </div>
  );
}
