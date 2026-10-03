"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { importarLote } from "./acoes";
import { emLotes, lerBaseDoDesktop, prepararImportacao, type LeituraDesktop } from "@/lib/importacao/desktop";
import { formatarData } from "@/lib/dominio/datas";
import { Aviso, Botao, Cartao, classeEntrada } from "@/components/ui";

interface Membro {
  id: string;
  nome: string;
  email: string;
}

type Fase =
  | { tipo: "escolher" }
  | { tipo: "rever"; ficheiro: string; leitura: LeituraDesktop }
  | { tipo: "a_importar"; feitas: number; total: number }
  | { tipo: "fim"; inseridas: number; repetidas: number; recusadas: number; motivos: { origem: string; motivo: string }[] };

/** Sugere o membro da web para um utilizador do desktop: pelo nome, ou pelo início do email. */
function sugerir(login: string, nome: string, membros: Membro[]): string {
  const n = nome.trim().toLowerCase();
  const m =
    (n && membros.find((x) => x.nome.trim().toLowerCase() === n)) ||
    membros.find((x) => x.email.split("@")[0].toLowerCase() === login.toLowerCase());
  return m?.id ?? "";
}

export function Importador({ empresaId, membros }: { empresaId: string; membros: Membro[] }) {
  const [fase, setFase] = useState<Fase>({ tipo: "escolher" });
  const [erro, setErro] = useState<string>();
  const [mapa, setMapa] = useState<Record<string, string>>({});

  async function abrir(ficheiro: File | undefined) {
    setErro(undefined);
    if (!ficheiro) return;
    try {
      const leitura = lerBaseDoDesktop(new Uint8Array(await ficheiro.arrayBuffer()));
      if (!leitura.tarefas.length) {
        setErro("Este ficheiro não tem tarefas para importar.");
        return;
      }
      setMapa(Object.fromEntries(leitura.pessoas.map((p) => [p.login, sugerir(p.login, p.nome, membros)])));
      setFase({ tipo: "rever", ficheiro: ficheiro.name, leitura });
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível ler o ficheiro.");
    }
  }

  async function importar(leitura: LeituraDesktop) {
    const tarefas = prepararImportacao(
      leitura,
      Object.fromEntries(Object.entries(mapa).map(([k, v]) => [k, v || null])),
    );
    const lotes = emLotes(tarefas, 500);
    const total = { inseridas: 0, repetidas: 0, recusadas: 0, motivos: [] as { origem: string; motivo: string }[] };
    setFase({ tipo: "a_importar", feitas: 0, total: tarefas.length });
    for (const lote of lotes) {
      const r = await importarLote(empresaId, lote);
      if (r.erro) {
        setErro(r.erro);
        break;
      }
      total.inseridas += r.inseridas ?? 0;
      total.repetidas += r.repetidas ?? 0;
      total.recusadas += r.recusadas ?? 0;
      total.motivos.push(...(r.motivos ?? []));
      setFase({ tipo: "a_importar", feitas: total.inseridas + total.repetidas + total.recusadas, total: tarefas.length });
    }
    setFase({ tipo: "fim", ...total });
  }

  const intervalo = useMemo(() => {
    if (fase.tipo !== "rever") return null;
    const datas = fase.leitura.tarefas.map((t) => t.criada_em?.slice(0, 10)).filter(Boolean).sort() as string[];
    return datas.length ? `${formatarData(datas[0])} a ${formatarData(datas[datas.length - 1])}` : null;
  }, [fase]);

  return (
    <div className="max-w-3xl space-y-6">
      {fase.tipo === "escolher" && (
        <Cartao className="space-y-4 p-6">
          <div className="space-y-2 text-sm">
            <p className="font-medium">1. Encontre o ficheiro da aplicação de secretária</p>
            <p className="text-texto-2">
              No Windows, é <code>tarefas.db</code> em <code>%APPDATA%\GerenciadorDeTarefas\</code> (cole isto na barra
              do Explorador). Feche a aplicação antes, para o ficheiro estar completo.
            </p>
          </div>
          <div className="space-y-2">
            <label htmlFor="ficheiro" className="block text-sm font-medium">2. Escolha-o aqui</label>
            <input id="ficheiro" type="file" accept=".db,.sqlite,application/x-sqlite3" onChange={(e) => abrir(e.target.files?.[0])} className={classeEntrada} />
            <p className="text-xs text-texto-2">
              O ficheiro é lido neste browser e não é enviado: só seguem as tarefas. As contas, palavras-passe e a
              auditoria do desktop ficam onde estão.
            </p>
          </div>
        </Cartao>
      )}

      {fase.tipo === "rever" && (
        <>
          <Cartao className="p-6 text-sm">
            <p className="font-medium">{fase.ficheiro}</p>
            <p className="mt-1 text-texto-2">
              {fase.leitura.tarefas.length} tarefas, {fase.leitura.concluidas} concluídas
              {intervalo && `, criadas de ${intervalo}`}.
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-texto-2">
              <li>O texto de cada tarefa vira título (e descrição, quando é longo).</li>
              <li>Prazos, estado e as datas de criação e conclusão mantêm-se.</li>
              <li>Todas levam a etiqueta <strong>importado</strong>, e ficam na auditoria em seu nome.</li>
              <li>Importar o mesmo ficheiro outra vez não duplica nada.</li>
            </ul>
          </Cartao>

          {fase.leitura.pessoas.length > 0 && (
            <Cartao className="p-6">
              <h2 className="font-medium">Quem fica responsável</h2>
              <p className="mt-1 text-sm text-texto-2">
                Para cada pessoa do desktop, escolha quem fica com as tarefas que ela criou. Sem escolha, ficam sem
                responsável.
              </p>
              <div className="mt-4 divide-y divide-borda">
                {fase.leitura.pessoas.map((p) => (
                  <div key={p.login} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{p.nome || p.login}</p>
                      <p className="text-xs text-texto-2">{p.login} · {p.tarefas} {p.tarefas === 1 ? "tarefa" : "tarefas"}</p>
                    </div>
                    <select
                      aria-label={`Responsável pelas tarefas de ${p.nome || p.login}`}
                      value={mapa[p.login] ?? ""}
                      onChange={(e) => setMapa((m) => ({ ...m, [p.login]: e.target.value }))}
                      className={`${classeEntrada} w-auto`}
                    >
                      <option value="">Ninguém</option>
                      {membros.map((m) => <option key={m.id} value={m.id}>{m.nome}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </Cartao>
          )}

          <div className="flex gap-2">
            <Botao onClick={() => importar(fase.leitura)}>Importar {fase.leitura.tarefas.length} tarefas</Botao>
            <Botao variante="secundario" onClick={() => setFase({ tipo: "escolher" })}>Escolher outro ficheiro</Botao>
          </div>
        </>
      )}

      {fase.tipo === "a_importar" && (
        <Cartao className="space-y-3 p-6" aria-live="polite">
          <p className="text-sm font-medium">A importar… {fase.feitas} de {fase.total}</p>
          <div className="h-2 overflow-hidden rounded-full bg-superficie-2" role="progressbar" aria-valuemin={0} aria-valuemax={fase.total} aria-valuenow={fase.feitas}>
            <div className="h-full bg-marca transition-all" style={{ width: `${(fase.feitas / Math.max(fase.total, 1)) * 100}%` }} />
          </div>
        </Cartao>
      )}

      {fase.tipo === "fim" && (
        <Cartao className="space-y-3 p-6 text-sm" aria-live="polite">
          <p className="text-base font-medium">Importação concluída</p>
          <ul className="space-y-1">
            <li><strong>{fase.inseridas}</strong> tarefas novas</li>
            {fase.repetidas > 0 && <li><strong>{fase.repetidas}</strong> já tinham sido importadas antes e ficaram como estavam</li>}
            {fase.recusadas > 0 && <li className="text-perigo"><strong>{fase.recusadas}</strong> não puderam entrar</li>}
          </ul>
          {fase.motivos.length > 0 && (
            <details className="text-xs text-texto-2">
              <summary className="cursor-pointer">Porquê</summary>
              <ul className="mt-2 space-y-1">
                {fase.motivos.map((m) => <li key={m.origem}><code>{m.origem}</code>: {m.motivo}</li>)}
              </ul>
            </details>
          )}
          <Link href={`/app/${empresaId}/tarefas`} className="inline-block font-medium text-marca hover:underline">
            Ver as tarefas →
          </Link>
        </Cartao>
      )}

      {erro && <Aviso>{erro}</Aviso>}
    </div>
  );
}
