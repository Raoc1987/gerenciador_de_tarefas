"use client";

import { useActionState, useEffect, useRef, useState, useTransition } from "react";
import { ROTULO_PAPEL, type Papel } from "@/lib/dominio/papeis";
import { alterarPapel, convidar, removerMembro, revogarConvite } from "./acoes";
import { Aviso, Botao, Campo, Selo, classeEntrada } from "@/components/ui";

export function LinhaMembro({
  empresaId, pessoa, souEu, opcoes, podeRemover,
}: {
  empresaId: string;
  pessoa: { id: string; nome: string; email: string; papel: Papel; desde: string };
  souEu: boolean;
  opcoes: Papel[];
  podeRemover: boolean;
}) {
  const [erro, setErro] = useState<string>();
  const [aGravar, iniciar] = useTransition();

  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">
          {pessoa.nome} {souEu && <span className="text-sm font-normal text-texto-2">(eu)</span>}
        </p>
        <p className="truncate text-xs text-texto-2">{pessoa.email} · desde {pessoa.desde}</p>
        {erro && <p role="alert" className="mt-1 text-xs text-perigo">{erro}</p>}
      </div>
      {opcoes.length > 0 ? (
        <select
          aria-label={`Papel de ${pessoa.nome}`}
          defaultValue={pessoa.papel}
          disabled={aGravar}
          onChange={(e) => {
            const novo = e.target.value as Papel;
            const alvo = e.target;
            setErro(undefined);
            iniciar(async () => {
              const r = await alterarPapel(empresaId, pessoa.id, novo);
              if (r.erro) {
                setErro(r.erro);
                alvo.value = pessoa.papel;
              }
            });
          }}
          className={`${classeEntrada} w-auto`}
        >
          {opcoes.map((p) => <option key={p} value={p}>{ROTULO_PAPEL[p]}</option>)}
        </select>
      ) : (
        <Selo>{ROTULO_PAPEL[pessoa.papel]}</Selo>
      )}
      {podeRemover && (
        <Botao
          variante="fantasma"
          className="text-perigo"
          disabled={aGravar}
          onClick={() => {
            const pergunta = souEu ? "Sair desta empresa? Deixa de ver as suas tarefas." : `Remover ${pessoa.nome} da empresa?`;
            if (!confirm(pergunta)) return;
            iniciar(async () => {
              const r = await removerMembro(empresaId, pessoa.id);
              if (r?.erro) setErro(r.erro);
            });
          }}
        >
          {souEu ? "Sair" : "Remover"}
        </Botao>
      )}
    </div>
  );
}

export function LinhaConvite({
  empresaId, convite,
}: {
  empresaId: string;
  convite: { id: string; email: string; papel: string; expira: string; ligacao: string };
}) {
  const [copiado, setCopiado] = useState(false);
  const [, iniciar] = useTransition();
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{convite.email}</p>
        <p className="text-xs text-texto-2">{convite.papel} · expira a {convite.expira}</p>
      </div>
      <Botao
        variante="secundario"
        onClick={async () => {
          await navigator.clipboard.writeText(convite.ligacao);
          setCopiado(true);
          setTimeout(() => setCopiado(false), 2000);
        }}
      >
        {copiado ? "Copiado ✓" : "Copiar ligação"}
      </Botao>
      <Botao variante="fantasma" className="text-perigo" onClick={() => iniciar(async () => { await revogarConvite(empresaId, convite.id); })}>
        Revogar
      </Botao>
    </div>
  );
}

export function Convidar({ empresaId, papeis, porEmail }: { empresaId: string; papeis: Papel[]; porEmail: boolean }) {
  const [estado, submeter, aEnviar] = useActionState(convidar.bind(null, empresaId), {});
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (estado.ok) form.current?.reset();
  }, [estado.ok]);
  return (
    <form ref={form} action={submeter} className="space-y-3">
      <Campo rotulo="Email">
        <input name="email" type="email" required className={classeEntrada} />
      </Campo>
      <Campo rotulo="Papel">
        <select name="papel" defaultValue="colaborador" className={classeEntrada}>
          {papeis.map((p) => <option key={p} value={p}>{ROTULO_PAPEL[p]}</option>)}
        </select>
      </Campo>
      <Aviso>{estado.erro}</Aviso>
      {estado.ok && (
        <Aviso tom="sucesso">
          {porEmail ? "Convite criado. O email segue nos próximos minutos." : "Convite criado. Copie a ligação na lista e envie-a."}
        </Aviso>
      )}
      <Botao type="submit" disabled={aEnviar} className="w-full">{aEnviar ? "A convidar…" : "Criar convite"}</Botao>
    </form>
  );
}
