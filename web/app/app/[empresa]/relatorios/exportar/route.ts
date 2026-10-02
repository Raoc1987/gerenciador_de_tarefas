import { NextResponse, type NextRequest } from "next/server";
import { clienteServidor } from "@/lib/supabase/servidor";
import { FUSO_PADRAO, formatarDataHora, hojeNoFuso } from "@/lib/dominio/datas";
import { INDICADORES_VAZIOS, type Indicadores } from "@/lib/dominio/painel";
import { pode, type Papel } from "@/lib/dominio/papeis";
import type { Tarefa } from "@/lib/dominio/tarefas";
import { construirRelatorio } from "@/lib/relatorios/construtor";
import { gerarCsv } from "@/lib/relatorios/csv";
import { nomeDeFicheiro } from "@/lib/relatorios/modelo";
import { FORMATOS, TIPO_MIME, filtroDoPedido, type Formato } from "@/lib/relatorios/pedido";
import { gerarPdf } from "@/lib/relatorios/pdf";
import { gerarXlsx } from "@/lib/relatorios/xlsx";

export const dynamic = "force-dynamic";

// Gera o relatório com a sessão de quem pede: a RLS decide que tarefas
// entram, exatamente como na lista. Um colaborador exporta as suas.
export async function GET(request: NextRequest, { params }: { params: Promise<{ empresa: string }> }) {
  const { empresa: empresaId } = await params;
  const formato = request.nextUrl.searchParams.get("formato") as Formato;
  if (!FORMATOS.includes(formato)) return NextResponse.json({ erro: "formato inválido" }, { status: 400 });

  const supabase = await clienteServidor();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ erro: "sessão necessária" }, { status: 401 });

  const [{ data: empresa }, { data: membro }] = await Promise.all([
    supabase.from("empresas").select("nome").eq("id", empresaId).maybeSingle(),
    supabase.from("membros").select("papel").eq("empresa_id", empresaId).eq("user_id", user.id).maybeSingle(),
  ]);
  if (!empresa || !membro) return NextResponse.json({ erro: "não encontrado" }, { status: 404 });

  const hoje = hojeNoFuso();
  const [{ data: tarefas }, { data: numeros }, { data: membros }] = await Promise.all([
    supabase.from("tarefas").select("*").eq("empresa_id", empresaId).limit(5000),
    supabase.rpc("indicadores_painel", { p_empresa: empresaId, p_dias: 30, p_hoje: hoje }),
    supabase.from("membros").select("user_id").eq("empresa_id", empresaId),
  ]);
  const ids = (membros ?? []).map((m) => m.user_id as string);
  const { data: perfis } = ids.length
    ? await supabase.from("perfis").select("id, nome, email").in("id", ids)
    : { data: [] };
  const nomes = new Map<string, string>(
    (perfis ?? []).map((p: { id: string; nome: string; email: string }) => [p.id, p.nome || p.email]),
  );

  const relatorio = construirRelatorio({
    empresa: empresa.nome as string,
    tarefas: (tarefas ?? []) as Tarefa[],
    numeros: { ...INDICADORES_VAZIOS, ...(numeros as Partial<Indicadores> | null) },
    nomes,
    filtro: filtroDoPedido(request.nextUrl.searchParams),
    eu: user.id,
    hoje,
    geradoEm: formatarDataHora(new Date().toISOString(), FUSO_PADRAO),
    geradoPor: nomes.get(user.id) ?? user.email ?? "",
    conjunto: pode(membro.papel as Papel, "tarefas.ver_todas"),
  });

  const bytes = formato === "pdf" ? gerarPdf(relatorio) : formato === "xlsx" ? gerarXlsx(relatorio) : gerarCsv(relatorio);
  const nome = nomeDeFicheiro(`tarefas ${empresa.nome} ${hoje}`, formato);
  return new NextResponse(bytes as unknown as BodyInit, {
    headers: {
      "Content-Type": TIPO_MIME[formato],
      "Content-Disposition": `attachment; filename="${nome}"`,
      "Cache-Control": "private, no-store",
    },
  });
}
