// Dados de ensaio para os testes de ponta a ponta: uma empresa, quatro
// pessoas com papéis diferentes e tarefas que cobrem os estados e prazos.
// Tudo entra pela API, com a sessão de cada pessoa — a RLS e os gatilhos
// atuam como em produção. Só os membros entram pela base: na aplicação
// chegam por convite, que precisa de email.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const E2E_DIR = process.env.E2E_DIR ?? "/tmp/gdt-e2e";
const amb = Object.fromEntries(
  readFileSync(`${E2E_DIR}/ambiente`, "utf8").trim().split("\n").map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const API = amb.NEXT_PUBLIC_SUPABASE_URL;
const CHAVE = amb.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
export const SENHA = "Ensaio-e2e-2026!";

async function api(metodo, caminho, token, corpo) {
  const r = await fetch(API + caminho, {
    method: metodo,
    headers: { apikey: CHAVE, authorization: `Bearer ${token ?? CHAVE}`, "content-type": "application/json", prefer: "return=representation" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const texto = await r.text();
  if (!r.ok) throw new Error(`${metodo} ${caminho} → ${r.status} ${texto}`);
  return texto ? JSON.parse(texto) : null;
}

function sql(consulta) {
  execFileSync("psql", [amb.E2E_PG, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-c", consulta]);
}

const pessoas = {
  dona: ["dona@ensaio.pt", "Ana Dona"],
  gestor: ["gestor@ensaio.pt", "Rui Gestor"],
  colaborador: ["colaborador@ensaio.pt", "João Colaborador"],
  outra: ["outra@ensaio.pt", "Inês Outra"],
};
const u = {};
for (const [chave, [email, nome]] of Object.entries(pessoas)) {
  const s = await api("POST", "/auth/v1/signup", null, { email, password: SENHA, data: { nome } });
  u[chave] = { id: s.user.id, token: s.access_token };
}

const empresa = await api("POST", "/rest/v1/rpc/criar_empresa", u.dona.token, { p_nome: "Ensaio, Lda." });
sql(`insert into public.membros (empresa_id, user_id, papel) values
  ('${empresa}', '${u.gestor.id}', 'gestor'),
  ('${empresa}', '${u.colaborador.id}', 'colaborador')`);
// "outra" tem conta mas não é membro: serve para provar o isolamento.

const dia = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
const tarefas = [
  ["Fechar contas do mês", "em_curso", "urgente", -2, "gestor", "gestor"],
  ["Preparar proposta para cliente", "a_fazer", "alta", 4, "colaborador", "gestor"],
  ["Rever contrato de fornecedor", "em_revisao", "media", 7, "gestor", "dona"],
  ["Tarefa só da dona", "a_fazer", "baixa", 10, "dona", "dona"],
];
for (const [titulo, estado, prioridade, prazo, responsavel, autor] of tarefas) {
  await api("POST", "/rest/v1/tarefas", u[autor].token, {
    empresa_id: empresa, titulo, estado, prioridade, prazo: dia(prazo), responsavel_id: u[responsavel].id,
  });
}
console.log(JSON.stringify({ empresa, tarefas: tarefas.length }));
