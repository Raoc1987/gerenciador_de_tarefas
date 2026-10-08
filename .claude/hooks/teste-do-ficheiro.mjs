#!/usr/bin/env node
/**
 * PostToolUse: depois de editar um `x.ts` em web/, corre o teste colocado `x.test.ts`.
 *
 * Vem do ALKMIA (`.claude/hooks/teste-do-ficheiro.mjs`), adaptado: aqui os testes da
 * web são `node:test` e correm com `node --test` sem `npm ci`, logo funcionam também
 * nas sessões na cloud sem registo npm. É a regra R8 do docs/METODO.md (a disciplina
 * falha, o procedimento apanha) aplicada ao "corre o teste do que mudaste".
 *
 * Cala-se quando passa e quando não há teste: um hook que fala em cada edição deixa de
 * ser lido. Quando falha, sai com 2 e o erro chega ao agente, que vê o vermelho logo.
 */
import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { basename, dirname, join, relative, resolve, sep } from "node:path";

let payload = {};
try {
  payload = JSON.parse(readFileSync(0, "utf8") || "{}");
} catch {
  process.exit(0);
}
const ficheiro = payload?.tool_input?.file_path;
if (!ficheiro) process.exit(0);

const raiz = payload?.cwd || process.cwd();
const abs = resolve(raiz, ficheiro);
const rel = relative(raiz, abs).split(sep).join("/");

// Só web/, só TypeScript, e nunca um teste (correria a si próprio em ciclo).
if (!rel.startsWith("web/") || !/\.tsx?$/.test(rel) || /\.test\.tsx?$/.test(rel)) process.exit(0);

const teste = join(dirname(abs), basename(abs).replace(/\.tsx?$/, ".test.ts"));
if (!existsSync(teste)) process.exit(0);

const r = spawnSync(process.execPath, ["--test", teste], { cwd: join(raiz, "web"), encoding: "utf8", timeout: 60_000 });
if (r.status === 0) process.exit(0);

const saida = `${r.stdout ?? ""}${r.stderr ?? ""}`.split("\n").filter((l) => /not ok|Error|assert|expected|actual/i.test(l));
process.stderr.write(`O teste colocado falhou: ${relative(raiz, teste)}\n${saida.slice(0, 30).join("\n")}\n`);
process.exit(2);
