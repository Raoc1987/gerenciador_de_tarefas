import type { Metadata } from "next";
import { contextoDaEmpresa, pessoasDaEmpresa } from "@/lib/contexto";
import { pode } from "@/lib/dominio/papeis";
import { ESTADOS, PRIORIDADES, ROTULO_ESTADO, ROTULO_PRIORIDADE } from "@/lib/dominio/tarefas";
import { filtroDoPedido, paraQuery } from "@/lib/relatorios/pedido";
import { Botao, Cabecalho, Cartao, classeBotao, classeEntrada } from "@/components/ui";

export const metadata: Metadata = { title: "Relatórios" };

const FORMATOS = [
  ["pdf", "PDF", "Para ler, imprimir ou enviar. A4 deitado, com indicadores, análise e a lista."],
  ["xlsx", "Excel", "Uma folha por secção; os números vão como números, para somar e filtrar."],
  ["csv", "CSV", "Para outros sistemas. Separado por ponto e vírgula, abre bem no Excel em português."],
] as const;

export default async function Relatorios({
  params,
  searchParams,
}: {
  params: Promise<{ empresa: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { empresa: id } = await params;
  const { papel } = await contextoDaEmpresa(id);
  const filtro = filtroDoPedido(await searchParams);
  const pessoas = pode(papel, "tarefas.ver_todas") ? await pessoasDaEmpresa(id) : [];
  const query = paraQuery(filtro);

  return (
    <>
      <Cabecalho
        titulo="Relatórios"
        descricao={
          pode(papel, "tarefas.ver_todas")
            ? "Exporte as tarefas da empresa, com os indicadores e a análise do painel."
            : "Exporte as suas tarefas, com os seus indicadores e a análise do painel."
        }
      />
      <div className="grid max-w-4xl gap-6 lg:grid-cols-[1fr_18rem]">
        <Cartao className="p-6">
          <h2 className="mb-4 font-medium">Que tarefas entram</h2>
          <form method="get" className="grid gap-3 sm:grid-cols-2">
            <select name="estado" defaultValue={filtro.estado} aria-label="Estado" className={classeEntrada}>
              <option value="">Todos os estados</option>
              {ESTADOS.map((e) => <option key={e} value={e}>{ROTULO_ESTADO[e]}</option>)}
            </select>
            <select name="prioridade" defaultValue={filtro.prioridade} aria-label="Prioridade" className={classeEntrada}>
              <option value="">Todas as prioridades</option>
              {PRIORIDADES.map((p) => <option key={p} value={p}>{ROTULO_PRIORIDADE[p]}</option>)}
            </select>
            {pessoas.length > 0 && (
              <select name="responsavel" defaultValue={filtro.responsavel} aria-label="Responsável" className={classeEntrada}>
                <option value="">Toda a gente</option>
                <option value="eu">As minhas</option>
                {pessoas.map((p) => <option key={p.id} value={p.id}>{p.nome || p.email}</option>)}
              </select>
            )}
            <input name="q" defaultValue={filtro.texto} placeholder="Com este texto…" aria-label="Texto" className={classeEntrada} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="atrasadas" value="1" defaultChecked={filtro.so_atrasadas} /> Só atrasadas
            </label>
            <div className="sm:col-span-2">
              <Botao type="submit" variante="secundario">Aplicar filtros</Botao>
            </div>
          </form>
          <p className="mt-4 text-xs text-texto-2">
            Os indicadores e a análise são sempre do conjunto que pode ver; os filtros escolhem as linhas da lista.
          </p>
        </Cartao>

        <div className="space-y-3">
          {FORMATOS.map(([formato, rotulo, ajuda]) => (
            <Cartao key={formato} className="p-4">
              <a
                href={`/app/${id}/relatorios/exportar?formato=${formato}${query ? `&${query}` : ""}`}
                className={classeBotao("primario", "w-full")}
                download
              >
                Descarregar {rotulo}
              </a>
              <p className="mt-2 text-xs text-texto-2">{ajuda}</p>
            </Cartao>
          ))}
        </div>
      </div>
    </>
  );
}
