// Traduz o erro que vem da base para uma frase que se possa mostrar.
//
// As exceções das nossas funções e gatilhos já são frases em português
// (ex.: "a empresa ficaria sem proprietário") e mostram-se como estão. O que
// vem do próprio Postgres não se mostra: diz nomes de tabelas e de policies.

export interface ErroBd {
  code?: string;
  message?: string;
}

const NOSSAS = /^[a-zà-ú][a-zà-ú ,:;—-]+$/i;

export function mensagemDeErro(e: ErroBd | null | undefined): string {
  if (!e) return "Algo correu mal. Tente outra vez.";
  const msg = (e.message ?? "").trim();
  if (msg.includes("row-level security") || e.code === "42501") {
    if (e.code === "42501" && NOSSAS.test(msg) && !/permission denied/i.test(msg)) return capitalizar(msg);
    return "Não tem permissão para fazer isso.";
  }
  if (e.code === "23505") return "Isso já existe.";
  if (e.code === "23514" && NOSSAS.test(msg) && !msg.includes("violates")) return capitalizar(msg);
  if (e.code === "23514") return "Algum valor está fora do permitido.";
  // 22023 (invalid_parameter_value) é o que as nossas funções usam para um
  // pedido mal formado: "para confirmar, escreva o email da sua conta".
  if (e.code === "22023" && NOSSAS.test(msg)) return capitalizar(msg);
  if (e.code === "P0002" || e.code === "23503") {
    return NOSSAS.test(msg) && !msg.includes("violates") ? capitalizar(msg) : "Não encontrado.";
  }
  return "Algo correu mal. Tente outra vez.";
}

function capitalizar(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1) + (/[.!?]$/.test(s) ? "" : ".");
}

const ORIGEM_INTERNA = "https://interno.invalid";

/**
 * Só caminhos internos: `?seguinte=https://mal.com` não leva ninguém para fora.
 *
 * Quem decide é o parser de URLs, o mesmo que o browser usa: ele apaga tabs e
 * quebras de linha e trata `\` como `/`, por isso `"/\t/mal.com"` seria lido
 * como `//mal.com`. Verificar o texto à mão deixava estes casos passar.
 */
export function caminhoSeguro(destino: string | null | undefined, padrao = "/app"): string {
  if (!destino || !destino.startsWith("/")) return padrao;
  let url: URL;
  try {
    url = new URL(destino, ORIGEM_INTERNA);
  } catch {
    return padrao;
  }
  if (url.origin !== ORIGEM_INTERNA) return padrao;
  return url.pathname + url.search + url.hash;
}
