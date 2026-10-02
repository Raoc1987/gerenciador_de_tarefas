// Como se escreve cada email. Puro: recebe a linha da fila e devolve
// assunto, HTML e texto simples. Os títulos, comentários e nomes foram
// escritos por pessoas, por isso tudo o que entra no HTML é escapado.

import { formatarData } from "./datas.ts";
import { ROTULO_PAPEL, type Papel } from "./papeis.ts";
import { ROTULO_PRIORIDADE, type Prioridade } from "./tarefas.ts";

export type TipoEmail = "atribuicao" | "comentario" | "convite" | "resumo";

export interface EmailPendente {
  id: number;
  tipo: TipoEmail;
  empresa_id: string | null;
  email: string;
  dados: Record<string, unknown>;
}

export interface EmailPronto {
  para: string;
  assunto: string;
  html: string;
  texto: string;
}

export function escapar(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const txt = (v: unknown) => String(v ?? "").replace(/[\r\n]+/g, " ").trim();
// Um assunto não pode ter quebras de linha: seria uma porta para injetar cabeçalhos.
const assunto = (s: string) => s.replace(/[\r\n]+/g, " ").slice(0, 200);

function moldura(titulo: string, corpo: string, botao: { texto: string; url: string }, rodape: string): string {
  return `<!doctype html><html lang="pt-PT"><body style="margin:0;background:#f7f7f8;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#18181b">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" style="max-width:520px;background:#ffffff;border:1px solid #e2e2e8;border-radius:12px" cellpadding="0" cellspacing="0">
<tr><td style="padding:28px">
<p style="margin:0 0 4px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#4338ca;font-weight:600">Gerenciador de Tarefas</p>
<h1 style="margin:0 0 16px;font-size:20px;line-height:1.3">${titulo}</h1>
${corpo}
<p style="margin:24px 0 0"><a href="${escapar(botao.url)}" style="display:inline-block;background:#4338ca;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;font-size:14px">${escapar(botao.texto)}</a></p>
</td></tr></table>
<p style="max-width:520px;margin:16px auto 0;font-size:12px;color:#52525b">${rodape}</p>
</td></tr></table></body></html>`;
}

const p = (html: string) => `<p style="margin:0 0 12px;font-size:15px;line-height:1.55">${html}</p>`;

export function montarEmail(e: EmailPendente, site: string): EmailPronto | null {
  const d = e.dados;
  const empresa = txt(d.empresa) || "a sua empresa";
  const por = txt(d.por);
  const base = site.replace(/\/$/, "");
  const preferencias = e.empresa_id ? `${base}/app/${e.empresa_id}/notificacoes` : `${base}/app`;
  const rodapeConta =
    `Recebe este email porque é membro de ${escapar(empresa)}. ` +
    `<a href="${escapar(preferencias)}" style="color:#52525b">Escolher que emails recebe</a>.`;
  const urlTarefa = e.empresa_id && d.tarefa_id ? `${base}/app/${e.empresa_id}/tarefas/${txt(d.tarefa_id)}` : `${base}/app`;

  switch (e.tipo) {
    case "atribuicao": {
      const titulo = txt(d.titulo);
      const detalhes = [
        d.prazo ? `prazo ${formatarData(String(d.prazo))}` : null,
        d.prioridade ? `prioridade ${ROTULO_PRIORIDADE[d.prioridade as Prioridade]?.toLowerCase() ?? ""}` : null,
      ].filter(Boolean).join(", ");
      const quem = por ? `${por} atribuiu-lhe` : "Foi-lhe atribuída";
      return {
        para: e.email,
        assunto: assunto(`Nova tarefa: ${titulo}`),
        html: moldura(
          escapar(titulo),
          p(`${escapar(quem)} esta tarefa em ${escapar(empresa)}${detalhes ? ` (${escapar(detalhes)})` : ""}.`),
          { texto: "Abrir a tarefa", url: urlTarefa },
          rodapeConta,
        ),
        texto: `${quem} a tarefa "${titulo}" em ${empresa}${detalhes ? ` (${detalhes})` : ""}.\n\n${urlTarefa}`,
      };
    }
    case "comentario": {
      const titulo = txt(d.titulo);
      const corpo = String(d.corpo ?? "");
      return {
        para: e.email,
        assunto: assunto(`${por || "Alguém"} comentou "${titulo}"`),
        html: moldura(
          escapar(titulo),
          p(`${escapar(por || "Alguém")} comentou:`) +
            `<blockquote style="margin:0;padding:12px 16px;background:#f1f1f4;border-radius:8px;white-space:pre-wrap;font-size:14px">${escapar(corpo)}</blockquote>`,
          { texto: "Responder", url: urlTarefa },
          rodapeConta,
        ),
        texto: `${por || "Alguém"} comentou "${titulo}":\n\n${corpo}\n\n${urlTarefa}`,
      };
    }
    case "convite": {
      const token = txt(d.token);
      if (!/^[0-9a-f]{16,}$/i.test(token)) return null;
      const url = `${base}/convite/${token}`;
      const papel = ROTULO_PAPEL[d.papel as Papel] ?? "membro";
      const expira = d.expira_em ? formatarData(String(d.expira_em).slice(0, 10)) : "";
      const quem = por ? `${por} convidou-o` : "Foi convidado";
      return {
        para: e.email,
        assunto: assunto(`Convite para ${empresa}`),
        html: moldura(
          `Convite para ${escapar(empresa)}`,
          p(`${escapar(quem)} para entrar em <strong>${escapar(empresa)}</strong> como <strong>${escapar(papel)}</strong>.`) +
            p(`O convite só funciona com a conta deste email${expira ? ` e expira a ${escapar(expira)}` : ""}.`),
          { texto: "Aceitar o convite", url },
          "Se não esperava este convite, pode ignorar este email.",
        ),
        texto: `${quem} para entrar em ${empresa} como ${papel}.\n\nAceitar: ${url}\n\nO convite só funciona com a conta deste email${expira ? ` e expira a ${expira}` : ""}.`,
      };
    }
    case "resumo": {
      const atrasadas = Number(d.atrasadas) || 0;
      const hoje = Number(d.hoje) || 0;
      const lista = (Array.isArray(d.tarefas) ? d.tarefas : []).slice(0, 10) as { titulo?: unknown; prazo?: unknown }[];
      const partes = [
        atrasadas ? `${atrasadas} ${atrasadas === 1 ? "atrasada" : "atrasadas"}` : null,
        hoje ? `${hoje} a vencer hoje` : null,
      ].filter(Boolean).join(" e ");
      if (!partes) return null;
      const urlLista = e.empresa_id ? `${base}/app/${e.empresa_id}/tarefas?responsavel=eu` : `${base}/app`;
      const itens = lista
        .map((t) => `<li style="margin:0 0 6px">${escapar(txt(t.titulo))} <span style="color:#52525b">— ${escapar(formatarData(String(t.prazo ?? "")))}</span></li>`)
        .join("");
      return {
        para: e.email,
        assunto: assunto(`${empresa}: ${partes}`),
        html: moldura(
          `Tem ${escapar(partes)}`,
          p(`Em ${escapar(empresa)}:`) + `<ul style="margin:0;padding-left:20px;font-size:14px">${itens}</ul>`,
          { texto: "Ver as minhas tarefas", url: urlLista },
          rodapeConta,
        ),
        texto: `Em ${empresa}, tem ${partes}:\n\n${lista.map((t) => `- ${txt(t.titulo)} (${formatarData(String(t.prazo ?? ""))})`).join("\n")}\n\n${urlLista}`,
      };
    }
  }
  return null;
}
