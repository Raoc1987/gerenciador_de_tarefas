// Datas no fuso de quem usa. "Hoje" num servidor em UTC não é o hoje de
// quem está em São Paulo às 22h — e é isso que decide se uma tarefa está
// atrasada.

export const FUSO_PADRAO = "America/Sao_Paulo";

export function hojeNoFuso(fuso: string = FUSO_PADRAO, agora: Date = new Date()): string {
  // en-CA formata como AAAA-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: fuso,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(agora);
}

export function formatarData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

export function formatarDataHora(iso: string, fuso: string = FUSO_PADRAO): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: fuso,
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(iso));
}

/** "há 3 dias", "daqui a 2 dias", "hoje", "ontem", "amanhã". */
export function relativo(prazo: string, hoje: string): string {
  const ms = Date.parse(`${prazo}T00:00:00Z`) - Date.parse(`${hoje}T00:00:00Z`);
  const dias = Math.round(ms / 86_400_000);
  if (dias === 0) return "hoje";
  if (dias === -1) return "ontem";
  if (dias === 1) return "amanhã";
  return dias < 0 ? `há ${-dias} dias` : `daqui a ${dias} dias`;
}
