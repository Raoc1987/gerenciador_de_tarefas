import Link from "next/link";
import { contextoDaEmpresa } from "@/lib/contexto";
import { pode, ROTULO_PAPEL } from "@/lib/dominio/papeis";
import { Navegacao, type ItemNav } from "@/components/navegacao";
import { PaletaComandos } from "@/components/paleta-comandos";

export default async function ConchaDaEmpresa({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ empresa: string }>;
}) {
  const { empresa: id } = await params;
  const { empresa, papel, user } = await contextoDaEmpresa(id);
  const base = `/app/${id}`;

  // Cada secção declara quem a vê; a lista é a mesma para a barra lateral e
  // para a paleta de comandos (ADR-0009 do desktop: um sítio só).
  const itens: ItemNav[] = [
    { href: base, rotulo: "Painel", icone: "painel" },
    { href: `${base}/tarefas`, rotulo: "Tarefas", icone: "tarefas" },
    { href: `${base}/copiloto`, rotulo: "Copiloto", icone: "copiloto" },
    { href: `${base}/relatorios`, rotulo: "Relatórios", icone: "relatorios" },
    { href: `${base}/equipa`, rotulo: "Equipa", icone: "equipa" },
    ...(pode(papel, "auditoria.ler") ? [{ href: `${base}/auditoria`, rotulo: "Auditoria", icone: "auditoria" } as const] : []),
    ...(pode(papel, "definicoes.editar") ? [{ href: `${base}/definicoes`, rotulo: "Definições", icone: "definicoes" } as const] : []),
  ];

  const comandos = [
    ...itens.map((i) => ({ rotulo: `Ir para ${i.rotulo}`, href: i.href })),
    ...(pode(papel, "tarefas.criar") ? [{ rotulo: "Nova tarefa", href: `${base}/tarefas?nova=1` }] : []),
    { rotulo: "Perguntar ao Copiloto", href: `${base}/copiloto` },
    { rotulo: "Exportar relatório em PDF", href: `${base}/relatorios` },
    { rotulo: "As minhas tarefas", href: `${base}/tarefas?responsavel=eu` },
    { rotulo: "Tarefas atrasadas", href: `${base}/tarefas?atrasadas=1` },
    { rotulo: "Quadro", href: `${base}/tarefas?vista=quadro` },
    { rotulo: "Notificações por email", href: `${base}/notificacoes` },
    ...(pode(papel, "pessoas.gerir") ? [{ rotulo: "Importar do desktop", href: `${base}/importar` }] : []),
    { rotulo: "Trocar de empresa", href: "/app?escolher=1" },
  ];

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-borda bg-superficie p-3 md:flex">
        <Link href="/app?escolher=1" className="mb-6 rounded-lg px-2 py-2 hover:bg-superficie-2" title="Trocar de empresa">
          <span className="block truncate font-semibold">{empresa.nome}</span>
          <span className="text-xs text-texto-2">{ROTULO_PAPEL[papel]}</span>
        </Link>
        <Navegacao itens={itens} />
        <div className="mt-auto space-y-1 border-t border-borda pt-3 text-sm">
          <p className="truncate px-2 text-texto-2" title={user.email ?? ""}>
            {user.email}
          </p>
          <Link href={`${base}/notificacoes`} className="block rounded-lg px-2 py-1.5 text-texto-2 hover:bg-superficie-2 hover:text-texto">
            Notificações
          </Link>
          <form action="/sair" method="post">
            <button className="w-full rounded-lg px-2 py-1.5 text-left text-texto-2 hover:bg-superficie-2 hover:text-texto">
              Sair
            </button>
          </form>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-borda bg-fundo/80 px-4 py-2.5 backdrop-blur">
          <Link href="/app?escolher=1" className="truncate font-semibold md:hidden">
            {empresa.nome}
          </Link>
          <div className="ml-auto">
            <PaletaComandos comandos={comandos} />
          </div>
        </header>
        <nav className="border-b border-borda bg-superficie px-2 py-1 md:hidden">
          <Navegacao itens={itens} horizontal />
        </nav>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
