// Ensaio de fumo de um deploy publicado:
//
//   npm run ensaio:fumo -- https://gerenciador-de-tarefas.vercel.app
//
// Numa pré-visualização protegida pelo Vercel, defina
// VERCEL_AUTOMATION_BYPASS_SECRET (Project Settings → Deployment Protection).
// Sai com 1 se alguma verificação falhar, 2 se não conseguir ensaiar.

import { ensaiar } from "../lib/ensaio/fumo.ts";

const base = process.argv[2];
if (!base || !/^https?:\/\//.test(base)) {
  console.error("Uso: npm run ensaio:fumo -- <url do deploy>");
  process.exit(2);
}

const { barrado, resultados } = await ensaiar(base, fetch, {
  bypass: process.env.VERCEL_AUTOMATION_BYPASS_SECRET || undefined,
});

if (barrado) {
  console.error(
    `O ensaio não chegou à aplicação em ${base}: foi barrado por ${barrado}.\n` +
      "Na Proteção de Deployments do Vercel, defina VERCEL_AUTOMATION_BYPASS_SECRET; " +
      "num proxy, corra o ensaio de uma rede que chegue ao deploy.",
  );
  process.exit(2);
}

for (const r of resultados) console.log(`${r.ok ? "ok    " : "FALHA "} ${r.nome} — ${r.detalhe}`);
const falhas = resultados.filter((r) => !r.ok).length;
console.log(falhas ? `\n${falhas} de ${resultados.length} falharam em ${base}.` : `\nTudo verde em ${base}.`);
process.exit(falhas ? 1 : 0);
