// Primitivas de interface. Pequenas de propósito: o resto da aplicação
// compõe-se a partir daqui, e o aspeto muda num sítio só.

import type { ComponentProps, ReactNode } from "react";

type Variante = "primario" | "secundario" | "perigo" | "fantasma";

const VARIANTES: Record<Variante, string> = {
  primario: "bg-marca text-marca-texto hover:opacity-90",
  secundario: "bg-superficie border border-borda hover:bg-superficie-2",
  perigo: "bg-perigo-suave text-perigo border border-perigo/30 hover:bg-perigo/10",
  fantasma: "hover:bg-superficie-2",
};

export function classeBotao(variante: Variante = "primario", extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 disabled:pointer-events-none ${VARIANTES[variante]} ${extra}`;
}

export function Botao({
  variante = "primario",
  className = "",
  ...props
}: ComponentProps<"button"> & { variante?: Variante }) {
  return <button className={classeBotao(variante, className)} {...props} />;
}

export function Campo({
  rotulo,
  erro,
  ajuda,
  children,
}: {
  rotulo: string;
  erro?: string;
  ajuda?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{rotulo}</span>
      {children}
      {ajuda && !erro && <span className="block text-xs text-texto-2">{ajuda}</span>}
      {erro && (
        <span role="alert" className="block text-xs text-perigo">
          {erro}
        </span>
      )}
    </label>
  );
}

export const classeEntrada =
  "w-full rounded-lg border border-borda bg-superficie px-3 py-2 text-sm placeholder:text-texto-2/70 focus:border-marca focus:outline-none";

export function Cartao({ className = "", ...props }: ComponentProps<"div">) {
  return (
    <div className={`rounded-[var(--radius-cartao)] border border-borda bg-superficie ${className}`} {...props} />
  );
}

type Tom = "neutro" | "marca" | "perigo" | "aviso" | "sucesso";
const TONS: Record<Tom, string> = {
  neutro: "bg-superficie-2 text-texto-2",
  marca: "bg-marca-suave text-marca",
  perigo: "bg-perigo-suave text-perigo",
  aviso: "bg-aviso-suave text-aviso",
  sucesso: "bg-sucesso-suave text-sucesso",
};

export function Selo({ tom = "neutro", children }: { tom?: Tom; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${TONS[tom]}`}>
      {children}
    </span>
  );
}

export function Aviso({ tom = "perigo", children }: { tom?: Tom; children: ReactNode }) {
  if (!children) return null;
  return (
    <p role="status" className={`rounded-lg px-3 py-2 text-sm ${TONS[tom]}`}>
      {children}
    </p>
  );
}

export function Vazio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="rounded-[var(--radius-cartao)] border border-dashed border-borda px-6 py-12 text-center">
      <p className="font-medium">{titulo}</p>
      {children && <div className="mt-2 text-sm text-texto-2">{children}</div>}
    </div>
  );
}

export function Cabecalho({
  titulo,
  descricao,
  acoes,
}: {
  titulo: string;
  descricao?: string;
  acoes?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        {descricao && <p className="mt-1 text-sm text-texto-2">{descricao}</p>}
      </div>
      {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
    </header>
  );
}
