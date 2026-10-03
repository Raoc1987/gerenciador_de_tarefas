"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export interface Comando {
  rotulo: string;
  href: string;
}

// Ctrl+K / ⌘K, como no desktop. Um <dialog> nativo: o foco fica preso lá
// dentro e Esc fecha, sem código para isso.
export function PaletaComandos({ comandos }: { comandos: Comando[] }) {
  const router = useRouter();
  const dialogo = useRef<HTMLDialogElement>(null);
  const [consulta, setConsulta] = useState("");
  const [indice, setIndice] = useState(0);

  const visiveis = useMemo(() => {
    const q = consulta.trim().toLowerCase();
    return q ? comandos.filter((c) => c.rotulo.toLowerCase().includes(q)) : comandos;
  }, [consulta, comandos]);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        abrir();
      }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  function abrir() {
    setConsulta("");
    setIndice(0);
    dialogo.current?.showModal();
  }

  function executar(c: Comando | undefined) {
    if (!c) return;
    dialogo.current?.close();
    router.push(c.href);
  }

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className="flex items-center gap-3 rounded-lg border border-borda bg-superficie px-3 py-1.5 text-sm text-texto-2 hover:text-texto"
      >
        Procurar ou ir para…
        <kbd className="rounded border border-borda px-1.5 text-xs">Ctrl K</kbd>
      </button>
      <dialog
        ref={dialogo}
        aria-label="Paleta de comandos"
        className="mx-auto mt-[15vh] w-[min(36rem,calc(100vw-2rem))] rounded-xl border border-borda bg-superficie p-0 text-texto shadow-2xl backdrop:bg-black/40"
        onClick={(e) => e.target === dialogo.current && dialogo.current?.close()}
      >
        <input
          autoFocus
          value={consulta}
          onChange={(e) => {
            setConsulta(e.target.value);
            setIndice(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndice((i) => Math.min(i + 1, visiveis.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndice((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              executar(visiveis[indice]);
            }
          }}
          placeholder="Escreva um comando…"
          aria-controls="paleta-lista"
          aria-activedescendant={visiveis[indice] ? `paleta-${indice}` : undefined}
          className="w-full border-b border-borda bg-transparent px-4 py-3 text-sm outline-none"
        />
        <ul id="paleta-lista" role="listbox" className="max-h-80 overflow-y-auto p-2">
          {visiveis.length === 0 && <li className="px-3 py-6 text-center text-sm text-texto-2">Nada encontrado.</li>}
          {visiveis.map((c, i) => (
            <li
              key={c.href + c.rotulo}
              id={`paleta-${i}`}
              role="option"
              aria-selected={i === indice}
              onMouseEnter={() => setIndice(i)}
              onClick={() => executar(c)}
              className={`cursor-pointer rounded-lg px-3 py-2 text-sm ${i === indice ? "bg-marca-suave text-marca" : ""}`}
            >
              {c.rotulo}
            </li>
          ))}
        </ul>
      </dialog>
    </>
  );
}
