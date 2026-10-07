"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef, useState, useTransition } from "react";
import { criarSubtarefa, desligarTarefas, ligarTarefas } from "../acoes";
import { Aviso, Botao, Cartao, Selo, classeEntrada } from "@/components/ui";
import { ROTULO_ESTADO, type Estado } from "@/lib/dominio/tarefas";
import {
  ROTULO_TIPO, ROTULO_TIPO_CURTO, TIPOS_DEPENDENCIA, ligacaoPendente, textoDesfasamento, type TipoDependencia,
} from "@/lib/dominio/ligacoes";

export interface TarefaCurta {
  id: string;
  titulo: string;
  estado: Estado;
}

export interface LigacaoVista {
  id: string;
  outra: TarefaCurta;
  tipo: TipoDependencia;
  desfasamento_dias: number;
}

/**
 * Subtarefas e dependências de uma tarefa. Os botões aparecem a quem pode
 * escrever na tarefa, mas quem decide é a base: uma recusa volta como frase.
 */
export function Ligacoes({
  empresaId, tarefaId, subtarefas, dependeDe, bloqueia, candidatas, podeEditar,
}: {
  empresaId: string;
  tarefaId: string;
  subtarefas: TarefaCurta[];
  dependeDe: LigacaoVista[];
  bloqueia: LigacaoVista[];
  candidatas: TarefaCurta[];
  podeEditar: boolean;
}) {
  const base = `/app/${empresaId}/tarefas`;
  const feitas = subtarefas.filter((s) => s.estado === "concluida").length;

  return (
    <div className="space-y-6">
      <section aria-labelledby="subtarefas-titulo">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 id="subtarefas-titulo" className="font-medium">
            Subtarefas{" "}
            <span className="text-sm font-normal text-texto-2">
              {subtarefas.length ? `(${feitas} de ${subtarefas.length} concluídas)` : "(nenhuma)"}
            </span>
          </h2>
        </div>
        {subtarefas.length > 0 && (
          <>
            <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-superficie-2" aria-hidden>
              <div className="h-full bg-sucesso" style={{ width: `${Math.round((feitas / subtarefas.length) * 100)}%` }} />
            </div>
            <Cartao className="divide-y divide-borda">
              {subtarefas.map((s) => (
                <Link key={s.id} href={`${base}/${s.id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-superficie-2">
                  <span className={s.estado === "concluida" ? "text-texto-2 line-through" : ""}>{s.titulo}</span>
                  <Selo tom={s.estado === "concluida" ? "sucesso" : "neutro"}>{ROTULO_ESTADO[s.estado]}</Selo>
                </Link>
              ))}
            </Cartao>
          </>
        )}
        {podeEditar && <NovaSubtarefa empresaId={empresaId} paiId={tarefaId} />}
      </section>

      <section aria-labelledby="dependencias-titulo">
        <h2 id="dependencias-titulo" className="mb-3 font-medium">Dependências</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <ListaLigacoes
            titulo="Esta tarefa depende de"
            vazio="Não depende de nenhuma."
            ligacoes={dependeDe}
            base={base}
            mostrarPendente
            remover={podeEditar ? (id) => desligarTarefas(empresaId, tarefaId, id) : undefined}
          />
          <ListaLigacoes titulo="Estão à espera desta" vazio="Nenhuma." ligacoes={bloqueia} base={base} />
        </div>
        {podeEditar && <NovaLigacao empresaId={empresaId} tarefaId={tarefaId} candidatas={candidatas} />}
      </section>
    </div>
  );
}

function ListaLigacoes({
  titulo, vazio, ligacoes, base, mostrarPendente = false, remover,
}: {
  titulo: string;
  vazio: string;
  ligacoes: LigacaoVista[];
  base: string;
  mostrarPendente?: boolean;
  remover?: (id: string) => Promise<{ erro?: string }>;
}) {
  const [aRemover, iniciar] = useTransition();
  const [erro, setErro] = useState<string>();
  return (
    <Cartao className="p-4">
      <h3 className="text-xs font-medium text-texto-2">{titulo}</h3>
      {ligacoes.length === 0 ? (
        <p className="mt-2 text-sm text-texto-2">{vazio}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {ligacoes.map((l) => (
            <li key={l.id} className="flex items-start justify-between gap-2 text-sm">
              <div className="min-w-0">
                <Link href={`${base}/${l.outra.id}`} className="font-medium hover:underline">{l.outra.titulo}</Link>
                <p className="text-xs text-texto-2">
                  {ROTULO_TIPO_CURTO[l.tipo]} {textoDesfasamento(l.desfasamento_dias)} · {ROTULO_ESTADO[l.outra.estado]}
                  {mostrarPendente && ligacaoPendente(l.tipo, l.outra.estado) && (
                    <> · <span className="text-aviso">por cumprir</span></>
                  )}
                </p>
              </div>
              {remover && (
                <button
                  type="button"
                  disabled={aRemover}
                  onClick={() => iniciar(async () => setErro((await remover(l.id)).erro))}
                  className="shrink-0 rounded px-1.5 text-texto-2 hover:bg-superficie-2 hover:text-perigo"
                  aria-label={`Desfazer a ligação a ${l.outra.titulo}`}
                >
                  ×
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2"><Aviso>{erro}</Aviso></div>
    </Cartao>
  );
}

function NovaSubtarefa({ empresaId, paiId }: { empresaId: string; paiId: string }) {
  const [estado, submeter, aEnviar] = useActionState(criarSubtarefa.bind(null, empresaId, paiId), {});
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (estado.ok) form.current?.reset();
  }, [estado.ok]);
  return (
    <form ref={form} action={submeter} className="mt-3 space-y-2">
      <div className="flex gap-2">
        <label htmlFor="nova-subtarefa" className="sr-only">Título da subtarefa</label>
        <input id="nova-subtarefa" name="titulo" maxLength={200} required placeholder="Nova subtarefa…" className={classeEntrada} />
        <Botao type="submit" variante="secundario" disabled={aEnviar}>{aEnviar ? "A criar…" : "Adicionar"}</Botao>
      </div>
      <Aviso>{estado.erro}</Aviso>
    </form>
  );
}

function NovaLigacao({ empresaId, tarefaId, candidatas }: { empresaId: string; tarefaId: string; candidatas: TarefaCurta[] }) {
  const [estado, submeter, aEnviar] = useActionState(ligarTarefas.bind(null, empresaId, tarefaId), {});
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (estado.ok) form.current?.reset();
  }, [estado.ok]);
  if (candidatas.length === 0) return null;
  return (
    <form ref={form} action={submeter} className="mt-3 space-y-2">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_6rem_auto]">
        <label className="sr-only" htmlFor="ligar-a">Depende de</label>
        <select id="ligar-a" name="antecessora_id" required defaultValue="" className={classeEntrada}>
          <option value="" disabled>Depende de…</option>
          {candidatas.map((c) => <option key={c.id} value={c.id}>{c.titulo}</option>)}
        </select>
        <label className="sr-only" htmlFor="ligar-tipo">Tipo de ligação</label>
        <select id="ligar-tipo" name="tipo" defaultValue="fim_inicio" className={classeEntrada}>
          {TIPOS_DEPENDENCIA.map((t) => <option key={t} value={t} title={`Esta tarefa ${ROTULO_TIPO[t]}`}>{ROTULO_TIPO_CURTO[t]}</option>)}
        </select>
        <label className="sr-only" htmlFor="ligar-desfasamento">Desfasamento em dias</label>
        <input id="ligar-desfasamento" name="desfasamento_dias" type="number" min={-365} max={365} step={1} placeholder="± dias" className={classeEntrada} />
        <Botao type="submit" variante="secundario" disabled={aEnviar}>{aEnviar ? "A ligar…" : "Ligar"}</Botao>
      </div>
      <Aviso>{estado.erro}</Aviso>
    </form>
  );
}
