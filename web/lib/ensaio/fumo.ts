// Ensaio de fumo de um deploy: pedidos HTTP sem sessão a um URL publicado,
// com o que cada um tem de responder. Não cria contas nem dados — prova que o
// deploy está de pé e que as portas que têm de estar fechadas estão fechadas.
//
// O fetch é injetado, para os testes correrem sem rede.

export type Busca = (url: string, init: RequestInit) => Promise<Response>;

export type Resultado = { nome: string; ok: boolean; detalhe: string };

type Verificacao = {
  nome: string;
  caminho: string;
  cabecalhos?: Record<string, string>;
  avaliar: (r: Response, corpo: string) => string | null; // null = passou; texto = porque falhou
};

const CABECALHOS_DE_SEGURANCA: Record<string, string> = {
  "x-frame-options": "DENY",
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
};

function estado(esperado: number) {
  return (r: Response) => (r.status === esperado ? null : `respondeu ${r.status}, esperava ${esperado}`);
}

export const VERIFICACOES: Verificacao[] = [
  {
    nome: "a página inicial abre, em português de Portugal",
    caminho: "/",
    avaliar: (r, corpo) => {
      if (r.status !== 200) return `respondeu ${r.status}, esperava 200`;
      return /<html[^>]*lang="pt-PT"/.test(corpo) ? null : 'sem <html lang="pt-PT">';
    },
  },
  {
    nome: "os cabeçalhos de segurança vão em todas as respostas",
    caminho: "/",
    avaliar: (r) => {
      const faltam = Object.entries(CABECALHOS_DE_SEGURANCA)
        .filter(([nome, valor]) => r.headers.get(nome)?.toLowerCase() !== valor.toLowerCase())
        .map(([nome]) => nome);
      if (!r.headers.get("permissions-policy")) faltam.push("permissions-policy");
      return faltam.length ? `faltam ou estão errados: ${faltam.join(", ")}` : null;
    },
  },
  { nome: "a página de entrar abre", caminho: "/entrar", avaliar: estado(200) },
  {
    nome: "/app sem sessão manda para o login, e lembra o destino",
    caminho: "/app",
    avaliar: (r) => {
      const destino = r.headers.get("location") ?? "";
      if (r.status < 300 || r.status > 399) return `respondeu ${r.status}, esperava um redirecionamento`;
      return /\/entrar\?seguinte=%2Fapp/.test(destino) ? null : `redireciona para "${destino}"`;
    },
  },
  { nome: "o cron dos emails recusa quem não traz o segredo", caminho: "/api/cron/emails", avaliar: estado(401) },
  {
    nome: "o cron dos emails recusa um segredo errado",
    caminho: "/api/cron/emails",
    cabecalhos: { authorization: "Bearer ensaio-de-fumo-segredo-errado" },
    avaliar: estado(401),
  },
  { nome: "o cron dos resumos recusa quem não traz o segredo", caminho: "/api/cron/resumos", avaliar: estado(401) },
  { nome: "um caminho que não existe dá 404", caminho: "/ensaio-de-fumo-nao-existe", avaliar: estado(404) },
];

/**
 * Uma resposta que não veio da aplicação: a Proteção de Deployments do
 * Vercel (401, ou o SSO do Vercel) ou um proxy/firewall pelo caminho (403 ou
 * 407 sem os cabeçalhos que a aplicação põe em tudo). Nenhuma é uma falha da
 * aplicação, e enquanto durar o resto do ensaio não prova nada.
 */
export function barrado(r: Response): string | null {
  const destino = r.headers.get("location") ?? "";
  if (/vercel\.com\/sso/.test(destino)) return "a Proteção de Deployments do Vercel";
  const daAplicacao = r.headers.has("x-frame-options");
  if (r.status === 401 && r.headers.has("x-vercel-id") && !daAplicacao) return "a Proteção de Deployments do Vercel";
  if ((r.status === 403 || r.status === 407) && !daAplicacao) return `um proxy ou firewall pelo caminho (${r.status})`;
  return null;
}

export async function ensaiar(
  base: string,
  buscar: Busca,
  opcoes: { bypass?: string } = {},
): Promise<{ barrado: string | null; resultados: Resultado[] }> {
  const raiz = base.replace(/\/+$/, "");
  const extra: Record<string, string> = opcoes.bypass ? { "x-vercel-protection-bypass": opcoes.bypass } : {};
  const resultados: Resultado[] = [];

  for (const v of VERIFICACOES) {
    let r: Response;
    try {
      r = await buscar(raiz + v.caminho, { redirect: "manual", headers: { ...extra, ...v.cabecalhos } });
    } catch (erro) {
      resultados.push({ nome: v.nome, ok: false, detalhe: `sem resposta: ${(erro as Error).message}` });
      continue;
    }
    // Só a primeira resposta decide: mais à frente, um 401 é do próprio cron.
    const motivo = resultados.length === 0 ? barrado(r) : null;
    if (motivo) return { barrado: motivo, resultados };
    const corpo = await r.text();
    const falha = v.avaliar(r, corpo);
    resultados.push({ nome: v.nome, ok: falha === null, detalhe: falha ?? `${r.status}` });
  }
  return { barrado: null, resultados };
}
