"use client";

import Link from "next/link";
import { useEffect, useMemo, useOptimistic, useRef, useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ESTADOS, PRIORIDADES, ROTULO_ESTADO, ROTULO_PRIORIDADE,
  agruparPorEstado, estaAtrasada, filtrar, ordenarParaLista, posicaoEntre, venceHoje,
  type Estado, type Filtro, type Tarefa,
} from "@/lib/dominio/tarefas";
import { formatarData, relativo } from "@/lib/dominio/datas";
import { clienteBrowser } from "@/lib/supabase/browser";
import { moverTarefa } from "./acoes";
import { FormularioTarefa, type Pessoa } from "./formulario-tarefa";
import { Aviso, Botao, Cabecalho, Selo, Vazio, classeEntrada } from "@/components/ui";

type Vista = "lista" | "quadro";

interface Props {
  empresaId: string;
  eu: string;
  hoje: string;
  tarefas: Tarefa[];
  pessoas: Pessoa[];
  permissoes: { criar: boolean; atribuir: boolean; verTodas: boolean };
  inicial: { vista: Vista; nova: boolean; filtro: Filtro };
}

const TOM_PRIORIDADE = { urgente: "perigo", alta: "aviso", media: "neutro", baixa: "neutro" } as const;

export function AreaTarefas({ empresaId, eu, hoje, tarefas, pessoas, permissoes, inicial }: Props) {
  const router = useRouter();
  const caminho = usePathname();
  const [vista, setVista] = useState<Vista>(inicial.vista);
  const [filtro, setFiltro] = useState<Filtro>(inicial.filtro);
  const [erro, setErro] = useState<string>();
  const [, iniciar] = useTransition();
  const dialogo = useRef<HTMLDialogElement>(null);

  // Mover um cartão aparece logo; se a base recusar, volta ao sítio.
  const [otimistas, aplicar] = useOptimistic(
    tarefas,
    (atual: Tarefa[], m: { id: string; estado: Estado; posicao: number }) =>
      atual.map((t) => (t.id === m.id ? { ...t, estado: m.estado, posicao: m.posicao } : t)),
  );

  const nomes = useMemo(() => new Map(pessoas.map((p) => [p.id, p.nome])), [pessoas]);
  const visiveis = useMemo(() => filtrar(otimistas, filtro, eu, hoje), [otimistas, filtro, eu, hoje]);

  // Tempo real: quando alguém mexe numa tarefa desta empresa, recarrega os
  // dados do servidor. O Realtime respeita a RLS — só chega o que se pode ver.
  useEffect(() => {
    const supabase = clienteBrowser();
    let pendente: ReturnType<typeof setTimeout> | undefined;
    const canal = supabase
      .channel(`tarefas:${empresaId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "tarefas", filter: `empresa_id=eq.${empresaId}` }, () => {
        clearTimeout(pendente);
        pendente = setTimeout(() => router.refresh(), 250);
      })
      .subscribe();
    return () => {
      clearTimeout(pendente);
      supabase.removeChannel(canal);
    };
  }, [empresaId, router]);

  useEffect(() => {
    if (inicial.nova && permissoes.criar) dialogo.current?.showModal();
  }, [inicial.nova, permissoes.criar]);

  // A vista e os filtros vivem no URL: uma lista filtrada partilha-se com um link.
  function sincronizarUrl(v: Vista, f: Filtro) {
    const p = new URLSearchParams();
    if (v === "quadro") p.set("vista", "quadro");
    if (f.texto) p.set("q", f.texto);
    if (f.estado) p.set("estado", f.estado);
    if (f.prioridade) p.set("prioridade", f.prioridade);
    if (f.responsavel) p.set("responsavel", f.responsavel);
    if (f.so_atrasadas) p.set("atrasadas", "1");
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `${caminho}?${qs}` : caminho);
  }

  function mudarFiltro(parcial: Partial<Filtro>) {
    const f = { ...filtro, ...parcial };
    setFiltro(f);
    sincronizarUrl(vista, f);
  }

  function mudarVista(v: Vista) {
    setVista(v);
    sincronizarUrl(v, filtro);
  }

  function mover(t: Tarefa, estado: Estado, posicao: number) {
    setErro(undefined);
    iniciar(async () => {
      aplicar({ id: t.id, estado, posicao });
      const r = await moverTarefa(empresaId, t.id, estado, posicao);
      if (r.erro) setErro(r.erro);
    });
  }

  return (
    <>
      <Cabecalho
        titulo="Tarefas"
        descricao={permissoes.verTodas ? "Todas as tarefas da empresa." : "As tarefas atribuídas a si ou criadas por si."}
        acoes={
          <>
            <div role="group" aria-label="Vista" className="flex rounded-lg border border-borda bg-superficie p-0.5 text-sm">
              {(["lista", "quadro"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={vista === v}
                  onClick={() => mudarVista(v)}
                  className={`rounded-md px-3 py-1 ${vista === v ? "bg-marca-suave font-medium text-marca" : "text-texto-2"}`}
                >
                  {v === "lista" ? "Lista" : "Quadro"}
                </button>
              ))}
            </div>
            {permissoes.criar && <Botao onClick={() => dialogo.current?.showModal()}>Nova tarefa</Botao>}
          </>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2" role="search">
        <input
          type="search"
          value={filtro.texto}
          onChange={(e) => mudarFiltro({ texto: e.target.value })}
          placeholder="Procurar no título, descrição ou etiquetas…"
          aria-label="Procurar tarefas"
          className={`${classeEntrada} max-w-xs`}
        />
        {vista === "lista" && (
          <select aria-label="Estado" value={filtro.estado} onChange={(e) => mudarFiltro({ estado: e.target.value as Estado | "" })} className={`${classeEntrada} w-auto`}>
            <option value="">Todos os estados</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>{ROTULO_ESTADO[e]}</option>
            ))}
          </select>
        )}
        <select aria-label="Prioridade" value={filtro.prioridade} onChange={(e) => mudarFiltro({ prioridade: e.target.value as Filtro["prioridade"] })} className={`${classeEntrada} w-auto`}>
          <option value="">Todas as prioridades</option>
          {PRIORIDADES.map((p) => (
            <option key={p} value={p}>{ROTULO_PRIORIDADE[p]}</option>
          ))}
        </select>
        {permissoes.verTodas && (
          <select aria-label="Responsável" value={filtro.responsavel} onChange={(e) => mudarFiltro({ responsavel: e.target.value })} className={`${classeEntrada} w-auto`}>
            <option value="">Toda a gente</option>
            <option value="eu">As minhas</option>
            {pessoas.filter((p) => p.id !== eu).map((p) => (
              <option key={p.id} value={p.id}>{p.nome}</option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!filtro.so_atrasadas} onChange={(e) => mudarFiltro({ so_atrasadas: e.target.checked })} />
          Só atrasadas
        </label>
      </div>

      {erro && <div className="mb-4"><Aviso>{erro}</Aviso></div>}

      {tarefas.length === 0 ? (
        <Vazio titulo="Ainda não há tarefas">
          {permissoes.criar ? "Crie a primeira com o botão “Nova tarefa”." : "Quando lhe atribuírem tarefas, aparecem aqui."}
        </Vazio>
      ) : vista === "lista" ? (
        <Lista tarefas={ordenarParaLista(visiveis, hoje)} empresaId={empresaId} hoje={hoje} nomes={nomes} />
      ) : (
        <Quadro tarefas={visiveis} empresaId={empresaId} hoje={hoje} nomes={nomes} mover={mover} />
      )}

      <dialog
        ref={dialogo}
        aria-labelledby="nova-titulo"
        className="mx-auto mt-[8vh] w-[min(40rem,calc(100vw-2rem))] rounded-xl border border-borda bg-superficie p-0 text-texto shadow-2xl backdrop:bg-black/40"
      >
        <div className="p-6">
          <h2 id="nova-titulo" className="mb-4 text-lg font-semibold">Nova tarefa</h2>
          <FormularioTarefa
            empresaId={empresaId}
            pessoas={pessoas}
            eu={eu}
            podeAtribuir={permissoes.atribuir}
            aoConcluir={() => {
              dialogo.current?.close();
              router.refresh();
            }}
            aoCancelar={() => dialogo.current?.close()}
          />
        </div>
      </dialog>
    </>
  );
}

function Prazo({ t, hoje }: { t: Tarefa; hoje: string }) {
  if (!t.prazo) return <span className="text-texto-2">—</span>;
  const atrasada = estaAtrasada(t, hoje);
  const hojeMesmo = venceHoje(t, hoje);
  return (
    <span className={atrasada ? "font-medium text-perigo" : hojeMesmo ? "font-medium text-aviso" : ""} title={formatarData(t.prazo)}>
      {t.estado === "concluida" ? formatarData(t.prazo) : relativo(t.prazo, hoje)}
    </span>
  );
}

function Lista({ tarefas, empresaId, hoje, nomes }: { tarefas: Tarefa[]; empresaId: string; hoje: string; nomes: Map<string, string> }) {
  if (!tarefas.length) return <Vazio titulo="Nenhuma tarefa com estes filtros" />;
  return (
    <div className="overflow-x-auto rounded-[var(--radius-cartao)] border border-borda bg-superficie">
      <table className="w-full min-w-[42rem] text-sm">
        <thead className="border-b border-borda text-left text-xs text-texto-2">
          <tr>
            <th className="px-4 py-2.5 font-normal">Tarefa</th>
            <th className="px-4 py-2.5 font-normal">Estado</th>
            <th className="px-4 py-2.5 font-normal">Prioridade</th>
            <th className="px-4 py-2.5 font-normal">Responsável</th>
            <th className="px-4 py-2.5 font-normal">Prazo</th>
          </tr>
        </thead>
        <tbody>
          {tarefas.map((t) => (
            <tr key={t.id} className="border-t border-borda first:border-t-0 hover:bg-superficie-2/60">
              <td className="px-4 py-2.5">
                <Link href={`/app/${empresaId}/tarefas/${t.id}`} className={`font-medium hover:text-marca ${t.estado === "concluida" ? "text-texto-2 line-through" : ""}`}>
                  {t.titulo}
                </Link>
                {t.etiquetas.length > 0 && (
                  <span className="ml-2 inline-flex gap-1 align-middle">
                    {t.etiquetas.slice(0, 3).map((e) => <Selo key={e}>{e}</Selo>)}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5"><Selo tom={t.estado === "concluida" ? "sucesso" : t.estado === "a_fazer" ? "neutro" : "marca"}>{ROTULO_ESTADO[t.estado]}</Selo></td>
              <td className="px-4 py-2.5"><Selo tom={TOM_PRIORIDADE[t.prioridade]}>{ROTULO_PRIORIDADE[t.prioridade]}</Selo></td>
              <td className="px-4 py-2.5">{t.responsavel_id ? nomes.get(t.responsavel_id) ?? "—" : <span className="text-texto-2">—</span>}</td>
              <td className="px-4 py-2.5"><Prazo t={t} hoje={hoje} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Quadro({
  tarefas, empresaId, hoje, nomes, mover,
}: {
  tarefas: Tarefa[];
  empresaId: string;
  hoje: string;
  nomes: Map<string, string>;
  mover: (t: Tarefa, estado: Estado, posicao: number) => void;
}) {
  const colunas = agruparPorEstado(tarefas);
  const [arrastada, setArrastada] = useState<Tarefa | null>(null);
  const [alvo, setAlvo] = useState<Estado | null>(null);

  // Largar sobre um cartão põe antes dele; largar no fundo da coluna põe no fim.
  function largar(estado: Estado, antesDe: Tarefa | null) {
    setAlvo(null);
    if (!arrastada || antesDe?.id === arrastada.id) return;
    const coluna = colunas[estado].filter((t) => t.id !== arrastada.id);
    const i = antesDe ? coluna.findIndex((t) => t.id === antesDe.id) : coluna.length;
    const anterior = coluna[i - 1]?.posicao ?? null;
    const seguinte = coluna[i]?.posicao ?? null;
    mover(arrastada, estado, posicaoEntre(anterior, seguinte));
    setArrastada(null);
  }

  return (
    <div className="grid gap-3 overflow-x-auto pb-2 md:grid-cols-4">
      {ESTADOS.map((estado) => (
        <section
          key={estado}
          aria-label={ROTULO_ESTADO[estado]}
          onDragOver={(e) => {
            e.preventDefault();
            setAlvo(estado);
          }}
          onDragLeave={() => setAlvo((a) => (a === estado ? null : a))}
          onDrop={(e) => {
            e.preventDefault();
            largar(estado, null);
          }}
          className={`min-h-48 rounded-[var(--radius-cartao)] border p-2 transition ${
            alvo === estado ? "border-marca bg-marca-suave/40" : "border-borda bg-superficie-2/50"
          }`}
        >
          <h2 className="flex items-center justify-between px-1.5 pb-2 text-sm font-medium">
            {ROTULO_ESTADO[estado]}
            <span className="text-xs tabular-nums text-texto-2">{colunas[estado].length}</span>
          </h2>
          <ul className="space-y-2">
            {colunas[estado].map((t) => (
              <li
                key={t.id}
                draggable
                onDragStart={(e) => {
                  setArrastada(t);
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragEnd={() => setArrastada(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  largar(estado, t);
                }}
                className={`cursor-grab rounded-lg border border-borda bg-superficie p-3 shadow-sm active:cursor-grabbing ${
                  arrastada?.id === t.id ? "opacity-50" : ""
                }`}
              >
                <Link href={`/app/${empresaId}/tarefas/${t.id}`} className="block text-sm font-medium hover:text-marca">
                  {t.titulo}
                </Link>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                  <Selo tom={TOM_PRIORIDADE[t.prioridade]}>{ROTULO_PRIORIDADE[t.prioridade]}</Selo>
                  {t.prazo && <span className="text-texto-2"><Prazo t={t} hoje={hoje} /></span>}
                  {t.responsavel_id && <span className="ml-auto truncate text-texto-2">{nomes.get(t.responsavel_id)}</span>}
                </div>
                {/* Mover sem rato: o arrastar não é a única forma (acessibilidade). */}
                <label className="sr-only" htmlFor={`mover-${t.id}`}>Mover “{t.titulo}” para</label>
                <select
                  id={`mover-${t.id}`}
                  value={t.estado}
                  onChange={(e) => {
                    const destino = e.target.value as Estado;
                    const ultima = colunas[destino].at(-1)?.posicao ?? null;
                    mover(t, destino, posicaoEntre(ultima, null));
                  }}
                  className="sr-only focus:not-sr-only focus:mt-2 focus:block focus:w-full focus:rounded-md focus:border focus:border-borda focus:bg-superficie focus:p-1 focus:text-xs"
                >
                  {ESTADOS.map((e) => <option key={e} value={e}>{ROTULO_ESTADO[e]}</option>)}
                </select>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
