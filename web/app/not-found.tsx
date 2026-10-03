import Link from "next/link";
import { classeBotao } from "@/components/ui";

export default function NaoEncontrado() {
  return (
    <main className="mx-auto flex min-h-[60dvh] max-w-md flex-col items-center justify-center px-4 text-center">
      <p className="text-sm font-medium text-marca">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Não encontrado</h1>
      <p className="mt-2 text-sm text-texto-2">
        Esta página não existe, ou não tem acesso a ela.
      </p>
      <Link href="/app" className={classeBotao("secundario", "mt-6")}>
        Voltar ao início
      </Link>
    </main>
  );
}
