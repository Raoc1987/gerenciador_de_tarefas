#!/usr/bin/env bash
# Um Supabase mínimo, sem Docker, para os testes de ponta a ponta:
# Postgres + GoTrue (autenticação) + PostgREST (API) + um proxy com as rotas
# do Supabase (/auth/v1, /rest/v1). Tudo em 127.0.0.1 — nada fica exposto.
#
#   supabase/e2e/levantar.sh            # levanta e escreve $E2E_DIR/ambiente
#   supabase/e2e/levantar.sh parar      # pára tudo
#
# Aplica as migrações REAIS de supabase/migrations/ por cima do esquema de
# autenticação verdadeiro do GoTrue. Fica de fora o Realtime (a aplicação
# funciona sem ele; só deixa de receber alterações ao vivo).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
E2E_DIR="${E2E_DIR:-/tmp/gdt-e2e}"
PORTA_PG="${E2E_PORTA_PG:-54322}"
PORTA_API="${E2E_PORTA_API:-54321}"
SEGREDO="segredo-jwt-so-para-testes-e2e-com-32-caracteres"

# Binários fixados por versão e SHA-256, como as Actions por SHA.
AUTH_VERSAO=v2.197.0
AUTH_SHA256=9daff5d1939c3142a1586e435e6e2a7a2f71534ec40ff1b196b59b83ad5678f3
POSTGREST_VERSAO=v16.4
POSTGREST_SHA256=b47ecc82fce1dcebbbc4183d839e52f07f7630c9d7ad0f54db753d1939299354

if ! command -v initdb >/dev/null 2>&1; then
  for d in /usr/lib/postgresql/*/bin; do PATH="$d:$PATH"; done
fi

CORRER=()
if [ "$(id -u)" = "0" ]; then
  id postgres >/dev/null 2>&1 || useradd -m postgres
  CORRER=(runuser -u postgres --)
fi

if [ "${1:-}" = "parar" ]; then
  for f in "$E2E_DIR"/*.pid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true; done
  "${CORRER[@]}" pg_ctl -D "$E2E_DIR/dados" -m immediate stop >/dev/null 2>&1 || true
  exit 0
fi

mkdir -p "$E2E_DIR"
[ ${#CORRER[@]} -gt 0 ] && chown postgres "$E2E_DIR"
cd "$E2E_DIR"

descarregar() { # url, sha256, ficheiro
  [ -f "$3" ] || curl -sSLf -o "$3" "$1"
  echo "$2  $3" | sha256sum -c --quiet
}
descarregar "https://github.com/supabase/auth/releases/download/$AUTH_VERSAO/auth-$AUTH_VERSAO-x86.tar.gz" "$AUTH_SHA256" auth.tgz
descarregar "https://github.com/PostgREST/postgrest/releases/download/$POSTGREST_VERSAO/postgrest-$POSTGREST_VERSAO-linux-static-x86-64.tar.xz" "$POSTGREST_SHA256" postgrest.tar.xz
tar xzf auth.tgz && tar xJf postgrest.tar.xz

# Postgres
"${CORRER[@]}" initdb -D "$E2E_DIR/dados" -U postgres --auth=trust -E UTF8 --locale=C.UTF-8 >/dev/null
"${CORRER[@]}" pg_ctl -D "$E2E_DIR/dados" -o "-p $PORTA_PG -k $E2E_DIR -c listen_addresses=127.0.0.1" \
  -l "$E2E_DIR/postgres.log" -w start >/dev/null
P=(psql -h 127.0.0.1 -p "$PORTA_PG" -U postgres -X -q -v ON_ERROR_STOP=1)

# O que o Supabase traz antes das nossas migrações: papéis, esquema auth,
# grants por omissão e a publicação do Realtime.
"${P[@]}" <<'SQL'
create role anon nologin noinherit;
create role authenticated nologin noinherit;
create role service_role nologin noinherit bypassrls;
create role authenticator login password 'autenticador' noinherit;
create role supabase_auth_admin login password 'auth' superuser createrole;
grant anon, authenticated, service_role to authenticator;
create schema auth authorization supabase_auth_admin;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;
create publication supabase_realtime;
SQL

# GoTrue: as suas migrações criam auth.users, auth.uid() e o resto.
export GOTRUE_DB_DRIVER=postgres
export DATABASE_URL="postgres://supabase_auth_admin:auth@127.0.0.1:$PORTA_PG/postgres?search_path=auth"
export GOTRUE_DB_DATABASE_URL="$DATABASE_URL" GOTRUE_DB_MIGRATIONS_PATH="$E2E_DIR/migrations"
export GOTRUE_JWT_SECRET="$SEGREDO" GOTRUE_JWT_EXP=3600 GOTRUE_JWT_AUD=authenticated
# Sem isto, as sessões saem com o papel vazio e o PostgREST recusa-as.
export GOTRUE_JWT_DEFAULT_GROUP_NAME=authenticated GOTRUE_JWT_ADMIN_ROLES=service_role
export GOTRUE_SITE_URL=http://localhost:3000 API_EXTERNAL_URL="http://127.0.0.1:$PORTA_API/auth/v1"
export GOTRUE_API_HOST=127.0.0.1 PORT=9999
export GOTRUE_MAILER_AUTOCONFIRM=true GOTRUE_EXTERNAL_EMAIL_ENABLED=true
export GOTRUE_URI_ALLOW_LIST="http://localhost:3000/**" GOTRUE_RATE_LIMIT_EMAIL_SENT=10000
./auth migrate >"$E2E_DIR/auth-migrate.log" 2>&1
nohup ./auth serve >"$E2E_DIR/auth.log" 2>&1 & echo $! >"$E2E_DIR/auth.pid"

# As migrações do produto
for m in "$AQUI"/../migrations/*.sql; do "${P[@]}" -f "$m" >/dev/null; done

# PostgREST
cat >"$E2E_DIR/postgrest.conf" <<EOF
db-uri = "postgres://authenticator:autenticador@127.0.0.1:$PORTA_PG/postgres"
db-schemas = "public"
db-anon-role = "anon"
jwt-secret = "$SEGREDO"
server-host = "127.0.0.1"
server-port = 3001
EOF
nohup ./postgrest "$E2E_DIR/postgrest.conf" >"$E2E_DIR/postgrest.log" 2>&1 & echo $! >"$E2E_DIR/postgrest.pid"

# Proxy com as rotas do Supabase
PORTA_API="$PORTA_API" nohup node "$AQUI/proxy.mjs" >"$E2E_DIR/proxy.log" 2>&1 & echo $! >"$E2E_DIR/proxy.pid"

# Chaves: anon e service_role (JWT HS256, só para este ambiente)
chave() {
  node -e '
    const c = require("crypto"), b = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
    const h = b({ alg: "HS256", typ: "JWT" }), p = b({ role: process.argv[2], iss: "supabase", iat: 1700000000, exp: 4100000000 });
    console.log(h + "." + p + "." + c.createHmac("sha256", process.argv[1]).update(h + "." + p).digest("base64url"));
  ' "$SEGREDO" "$1"
}

for i in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORTA_API/auth/v1/health" >/dev/null && curl -sf -o /dev/null "http://127.0.0.1:3001/" && break
  sleep 1
done

cat >"$E2E_DIR/ambiente" <<EOF
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:$PORTA_API
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$(chave anon)
NEXT_PUBLIC_SITE_URL=http://localhost:3000
E2E_PG=postgres://postgres@127.0.0.1:$PORTA_PG/postgres
EOF
echo "Supabase local de pé: API em http://127.0.0.1:$PORTA_API, Postgres em $PORTA_PG"
