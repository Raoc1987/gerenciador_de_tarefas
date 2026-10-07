"use client";

import { useState, useTransition } from "react";
import { assinar, gerirFaturacao } from "./acoes";
import { Aviso, Botao } from "@/components/ui";

export function BotaoAssinar({ empresaId, plano, rotulo }: { empresaId: string; plano: string; rotulo: string }) {
  const [aEnviar, iniciar] = useTransition();
  const [erro, setErro] = useState<string>();
  return (
    <div className="space-y-2">
      <Botao className="w-full" disabled={aEnviar} onClick={() => iniciar(async () => setErro((await assinar(empresaId, plano)).erro))}>
        {aEnviar ? "A abrir o pagamento…" : rotulo}
      </Botao>
      <Aviso>{erro}</Aviso>
    </div>
  );
}

export function BotaoGerir({ empresaId }: { empresaId: string }) {
  const [aEnviar, iniciar] = useTransition();
  const [erro, setErro] = useState<string>();
  return (
    <div className="space-y-2">
      <Botao variante="secundario" disabled={aEnviar} onClick={() => iniciar(async () => setErro((await gerirFaturacao(empresaId)).erro))}>
        {aEnviar ? "A abrir…" : "Faturas, cartão e cancelamento"}
      </Botao>
      <Aviso>{erro}</Aviso>
    </div>
  );
}
