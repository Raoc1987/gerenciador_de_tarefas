import Link from "next/link";
import { classeBotao } from "@/components/ui";

const PONTOS = [
  ["Várias empresas, separadas de verdade", "Cada empresa só vê o que é seu — garantido pela base de dados, não por um filtro na interface."],
  ["Papéis que fazem sentido", "Do leitor ao proprietário: cada pessoa vê e faz o que o seu papel permite."],
  ["Quadro e lista em tempo real", "Quando alguém mexe numa tarefa, toda a equipa vê na hora."],
  ["Auditoria que não se apaga", "Quem fez o quê, quando, e o que estava antes. Nem um administrador a altera."],
  ["Indicadores que contam a verdade", "Atrasadas, ritmo de entrega e carga por pessoa — cada um vê os números do que pode ver."],
  ["Segregação de funções", "Opcional: quem cria uma tarefa não a dá por concluída."],
];

export default function Inicio() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-16 sm:py-24">
      <section className="max-w-2xl">
        <p className="text-sm font-medium text-marca">Gerenciador de Tarefas</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">
          O dia a dia da sua empresa, organizado e à vista de todos.
        </h1>
        <p className="mt-5 text-lg text-texto-2">
          Tarefas, equipas e indicadores num só sítio — com a segurança de uma plataforma empresarial
          e a rapidez de uma aplicação moderna.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/entrar?modo=registar" className={classeBotao("primario", "px-5 py-2.5")}>
            Começar agora
          </Link>
          <Link href="/entrar" className={classeBotao("secundario", "px-5 py-2.5")}>
            Já tenho conta
          </Link>
        </div>
      </section>

      <section className="mt-20 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {PONTOS.map(([titulo, texto]) => (
          <div key={titulo} className="rounded-[var(--radius-cartao)] border border-borda bg-superficie p-5">
            <h2 className="font-medium">{titulo}</h2>
            <p className="mt-2 text-sm text-texto-2">{texto}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
