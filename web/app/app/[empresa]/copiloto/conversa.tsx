"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { aplicarProposta, perguntar } from "./acoes";
import type { Proposta, Turno } from "@/lib/dominio/copiloto";
import { ROTULO_ESTADO, ROTULO_PRIORIDADE, type DadosTarefa } from "@/lib/dominio/tarefas";
import { formatarData } from "@/lib/dominio/datas";
import { Aviso, Botao, Cartao, Selo, classeEntrada } from "@/components/ui";

const SUGESTOES = [
  "O que está atrasado e quem precisa de ajuda?",
  "Resume o estado da equipa esta semana.",
  "Quais são as 5 tarefas mais urgentes para hoje?",
  "Cria tarefas a partir desta lista: ",
];

interface Mensagem extends Turno {
  propostas?: Proposta[];
}

type EstadoProposta = "pendente" | "aplicada" | "ignorada" | { erro: string };

export function Conversa({
  empresaId, podeAplicar, configurado, nomes,
}: {
  empresaId: string;
  podeAplicar: boolean;
  configurado: boolean;
  nomes: Record<string, string>;
}) {
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string>();
  const [restantes, setRestantes] = useState<number>();
  const [aPensar, iniciar] = useTransition();
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensagens, aPensar]);

  function enviar(pergunta: string) {
    const q = pergunta.trim();
    if (!q || aPensar) return;
    setErro(undefined);
    const historico: Turno[] = mensagens.map(({ papel, texto }) => ({ papel, texto }));
    setMensagens((m) => [...m, { papel: "pessoa", texto: q }]);
    setTexto("");
    iniciar(async () => {
      const r = await perguntar(empresaId, historico, q);
      if (r.erro) {
        setErro(r.erro);
        setMensagens((m) => m.slice(0, -1));
        setTexto(q);
        return;
      }
      setRestantes(r.restantes);
      setMensagens((m) => [...m, { papel: "copiloto", texto: r.resposta ?? "", propostas: r.propostas }]);
    });
  }

  if (!configurado) {
    return (
      <Cartao className="max-w-2xl p-6 text-sm">
        <p className="font-medium">O Copiloto ainda não está ligado nesta instalação.</p>
        <p className="mt-2 text-texto-2">
          Quem gere o alojamento tem de definir a variável <code>ANTHROPIC_API_KEY</code> no servidor (nunca no browser).
          Ver <code>web/README.md</code>.
        </p>
      </Cartao>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      {mensagens.length === 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {SUGESTOES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                if (s.endsWith(": ")) {
                  setTexto(s);
                  campo.current?.focus();
                } else enviar(s);
              }}
              className="rounded-[var(--radius-cartao)] border border-borda bg-superficie p-4 text-left text-sm hover:border-marca"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <ol className="space-y-4" aria-live="polite">
        {mensagens.map((m, i) => (
          <li key={i} className={m.papel === "pessoa" ? "flex justify-end" : ""}>
            {m.papel === "pessoa" ? (
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-marca px-4 py-2.5 text-sm text-marca-texto">
                {m.texto}
              </p>
            ) : (
              <div className="space-y-3">
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.texto}</p>
                {!!m.propostas?.length && (
                  <Propostas empresaId={empresaId} propostas={m.propostas} podeAplicar={podeAplicar} nomes={nomes} />
                )}
              </div>
            )}
          </li>
        ))}
        {aPensar && (
          <li className="flex items-center gap-2 text-sm text-texto-2">
            <span className="size-2 animate-pulse rounded-full bg-marca" aria-hidden /> A ler as tarefas e a pensar…
          </li>
        )}
      </ol>
      <div ref={fim} />

      {erro && <Aviso>{erro}</Aviso>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          enviar(texto);
        }}
        className="sticky bottom-0 space-y-1.5 bg-fundo pb-2 pt-1"
      >
        <label htmlFor="pergunta" className="sr-only">Pergunta ao Copiloto</label>
        <div className="flex items-end gap-2">
          <textarea
            id="pergunta"
            ref={campo}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar(texto);
              }
            }}
            rows={2}
            maxLength={2000}
            placeholder="Pergunte sobre as tarefas, ou peça para organizar…"
            className={`${classeEntrada} resize-none`}
          />
          <Botao type="submit" disabled={aPensar || !texto.trim()}>Enviar</Botao>
        </div>
        <p className="text-xs text-texto-2">
          Enter envia, Shift+Enter muda de linha.
          {restantes !== undefined && ` Restam ${restantes} perguntas hoje.`}
        </p>
      </form>
    </div>
  );
}

function descreverCampos(c: Partial<DadosTarefa>, nomes: Record<string, string>): string[] {
  const out: string[] = [];
  if (c.titulo !== undefined) out.push(`título: “${c.titulo}”`);
  if (c.estado) out.push(`estado: ${ROTULO_ESTADO[c.estado]}`);
  if (c.prioridade) out.push(`prioridade: ${ROTULO_PRIORIDADE[c.prioridade]}`);
  if (c.prazo !== undefined) out.push(`prazo: ${formatarData(c.prazo)}`);
  if (c.responsavel_id !== undefined) out.push(`responsável: ${c.responsavel_id ? nomes[c.responsavel_id] ?? "—" : "ninguém"}`);
  if (c.etiquetas?.length) out.push(`etiquetas: ${c.etiquetas.join(", ")}`);
  if (c.descricao) out.push("descrição atualizada");
  return out;
}

function Propostas({
  empresaId, propostas, podeAplicar, nomes,
}: {
  empresaId: string;
  propostas: Proposta[];
  podeAplicar: boolean;
  nomes: Record<string, string>;
}) {
  const [estados, setEstados] = useState<EstadoProposta[]>(() => propostas.map(() => "pendente"));
  const [aAplicar, iniciar] = useTransition();

  function aplicar(i: number) {
    iniciar(async () => {
      const r = await aplicarProposta(empresaId, propostas[i]);
      setEstados((e) => e.map((x, j) => (j === i ? (r.erro ? { erro: r.erro } : "aplicada") : x)));
    });
  }

  const pendentes = estados.map((e, i) => (e === "pendente" ? i : -1)).filter((i) => i >= 0);

  return (
    <Cartao className="divide-y divide-borda">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
        <p className="text-sm font-medium">Propostas ({propostas.length})</p>
        {podeAplicar && pendentes.length > 1 && (
          <Botao variante="secundario" disabled={aAplicar} onClick={() => pendentes.forEach(aplicar)}>
            Aplicar todas
          </Botao>
        )}
      </div>
      {propostas.map((p, i) => {
        const estado = estados[i];
        const campos = p.acao === "criar" ? p.dados : p.campos;
        return (
          <div key={i} className="flex flex-wrap items-start gap-3 px-4 py-3 text-sm">
            <div className="min-w-0 flex-1 space-y-1">
              <p>
                <Selo tom={p.acao === "criar" ? "sucesso" : "marca"}>{p.acao === "criar" ? "Nova" : "Alterar"}</Selo>{" "}
                <span className="font-medium">{p.acao === "criar" ? p.dados.titulo : p.titulo_atual}</span>
              </p>
              <p className="text-xs text-texto-2">
                {descreverCampos(p.acao === "criar" ? { ...campos, titulo: undefined } : campos, nomes).join(" · ")}
              </p>
              {p.motivo && <p className="text-xs italic text-texto-2">{p.motivo}</p>}
              {typeof estado === "object" && <p role="alert" className="text-xs text-perigo">{estado.erro}</p>}
            </div>
            {estado === "aplicada" ? (
              <Selo tom="sucesso">Aplicada ✓</Selo>
            ) : estado === "ignorada" ? (
              <Selo>Ignorada</Selo>
            ) : podeAplicar ? (
              <div className="flex gap-1.5">
                <Botao disabled={aAplicar} onClick={() => aplicar(i)}>Aplicar</Botao>
                <Botao
                  variante="fantasma"
                  disabled={aAplicar}
                  onClick={() => setEstados((e) => e.map((x, j) => (j === i ? "ignorada" : x)))}
                >
                  Ignorar
                </Botao>
              </div>
            ) : (
              <Selo>Só leitura</Selo>
            )}
          </div>
        );
      })}
    </Cartao>
  );
}
