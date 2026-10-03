#!/usr/bin/env bash
# Inventário só de leitura de candidatos para a auditoria de segurança.
# Cada linha é um sítio a rever, não uma vulnerabilidade.
#
#   bash .claude/skills/auditoria-seguranca/scripts/superficie.sh [raiz]
set -euo pipefail

RAIZ="${1:-.}"
[ -d "$RAIZ" ] || { echo "superficie: não é uma pasta: $RAIZ" >&2; exit 64; }
command -v rg >/dev/null || { echo "superficie: precisa do ripgrep (rg)" >&2; exit 69; }
cd "$RAIZ"

COMUM=(--hidden --line-number --no-heading --color never
  --glob '!.git/**' --glob '!**/node_modules/**' --glob '!**/.next/**'
  --glob '!build/**' --glob '!dist/**' --glob '!*.md' --glob '!*.min.js'
  --glob '!.claude/**' --glob '!.trabalho/**' --glob '!.dependencias/**')

seccao() { printf '\n## %s\n' "$1"; }
procura() { # titulo, padrão, [globs extra...]
  local titulo="$1" padrao="$2"; shift 2
  seccao "$titulo"
  rg "${COMUM[@]}" "$@" --regexp "$padrao" . 2>/dev/null \
    | awk 'NR <= 60 { print } END { if (NR > 60) print "... cortado depois de 60 candidatos" }' || true
}

seccao "Estado do repositório"
git status --short --branch 2>/dev/null || true

seccao "Executáveis, symlinks e submódulos versionados"
git ls-files -s 2>/dev/null | awk '$1 == "100755" || $1 == "120000" || $1 == "160000"' | head -60 || true

# --- Base de dados: é aqui que mora a autoridade (ADR-0017) ---
procura "SQL: funções security definer (verificar papel dentro e search_path)" \
  'security definer' --glob 'supabase/migrations/*.sql'
procura "SQL: grants, revokes e default privileges" \
  '\b(grant|revoke|alter default privileges)\b' --glob 'supabase/migrations/*.sql'
procura "SQL: policies e RLS (procurar using (true), with check (true), disable)" \
  '(create policy|using\s*\(\s*true|with check\s*\(\s*true|disable row level security|bypassrls|force row level security)' \
  --glob 'supabase/migrations/*.sql'
procura "SQL: SQL dinâmico (format/execute com texto do cliente)" \
  '(execute\s+format|execute\s+[a-z_]+\s*\|\||%s)' --glob 'supabase/migrations/*.sql'
procura "SQL: colunas de identidade escritas pelo cliente (validar no gatilho)" \
  '(criada_por|responsavel_id|empresa_id|autor_id)\s*=' --glob 'supabase/migrations/*.sql'

# --- Web ---
procura "Web: chave de serviço e segredos do servidor" \
  '(SERVICE_ROLE|CRON_SECRET|ANTHROPIC_API_KEY|RESEND_API_KEY|NEXT_PUBLIC_[A-Z_]+)' --glob 'web/**'
procura "Web: Server Actions e rotas (cada uma corre como quem?)" \
  '(^["'"'"']use server|export async function (GET|POST|PUT|PATCH|DELETE))' --glob 'web/app/**'
procura "Web: HTML cru, redirecionamentos e URLs montados" \
  '(dangerouslySetInnerHTML|innerHTML|redirect\(|NextResponse\.redirect|new URL\(|location\.href)' --glob 'web/**'
procura "Web: chamadas de rede para fora" \
  '(fetch\(|https?://[a-z0-9.-]+\.(com|io|dev|app|pt|net))' --glob 'web/**' --glob '!web/**/*.test.ts'
procura "Web: execução dinâmica" \
  '(eval\(|new Function|child_process|import\(\s*[^"'"'"'])' --glob 'web/**'
procura "Web: Copiloto — ferramentas, prompt de sistema, propostas" \
  '(tools?:|tool_use|system:|propor_alteracoes|validarProposta)' --glob 'web/lib/copiloto/**' --glob 'web/lib/dominio/copiloto.ts' --glob 'web/app/**/copiloto/**'
procura "Web: entradas de ficheiro e exportações (limites, injeção de fórmulas)" \
  '(FileReader|arrayBuffer\(|Uint8Array|DataView|neutraliz|inlineStr|<f>)' --glob 'web/lib/importacao/**' --glob 'web/lib/relatorios/**'

# --- Desktop (src/, plugins/) ---
procura "Desktop: processos, eval, desserialização" \
  '(subprocess|os\.system|eval\(|exec\(|pickle|marshal|yaml\.load|__import__)' --glob 'src/**' --glob 'plugins/**' --glob 'tools/**'
procura "Desktop: SQL montado com texto (f-strings ou %)" \
  '(execute\(\s*f["'"'"']|execute\([^)]*%|execute\([^)]*\.format\()' --glob 'src/**' --glob 'plugins/**'

# --- CI, release, cadeia de fornecimento ---
procura "CI: gatilhos, permissões, segredos e Actions" \
  '(pull_request_target|permissions:|secrets\.|github\.event\.|uses:|curl .*\|\s*(sh|bash)|sha256sum)' --glob '.github/**'
procura "Manifestos e scripts de instalação" \
  '("(pre|post)install"|"prepare"|git\+|file:|link:)' --glob '**/package.json'

seccao "Unicode bidi (código que se lê diferente do que corre)"
rg "${COMUM[@]}" --pcre2 '[\x{202A}-\x{202E}\x{2066}-\x{2069}]' . 2>/dev/null | head -60 || true

seccao "Fim"
echo "Rever alcance, controlo do atacante, autorização e intenção antes de classificar qualquer linha."
