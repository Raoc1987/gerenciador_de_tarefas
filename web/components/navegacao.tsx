"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type Icone = "painel" | "tarefas" | "equipa" | "auditoria" | "definicoes";
export interface ItemNav {
  href: string;
  rotulo: string;
  icone: Icone;
}

const CAMINHOS: Record<Icone, string> = {
  painel: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z",
  tarefas: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  equipa: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 10v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  auditoria: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  definicoes: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-2.82 1.17V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-2.82-1.17l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 3.2 15H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.17-2.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 3.2V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 2.82 1.17l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 20.8 9H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
};

export function IconeSvg({ nome, className = "size-4" }: { nome: Icone; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d={CAMINHOS[nome]} />
    </svg>
  );
}

export function Navegacao({ itens, horizontal = false }: { itens: ItemNav[]; horizontal?: boolean }) {
  const atual = usePathname();
  // O painel é o prefixo de tudo: só está ativo quando é exatamente ele.
  const ativo = (href: string, i: number) => (i === 0 ? atual === href : atual.startsWith(href));

  return (
    <ul className={horizontal ? "flex gap-1 overflow-x-auto" : "space-y-0.5"}>
      {itens.map((item, i) => (
        <li key={item.href}>
          <Link
            href={item.href}
            aria-current={ativo(item.href, i) ? "page" : undefined}
            className={`flex items-center gap-2.5 whitespace-nowrap rounded-lg px-2 py-1.5 text-sm ${
              ativo(item.href, i) ? "bg-marca-suave font-medium text-marca" : "text-texto-2 hover:bg-superficie-2 hover:text-texto"
            }`}
          >
            <IconeSvg nome={item.icone} />
            {item.rotulo}
          </Link>
        </li>
      ))}
    </ul>
  );
}
