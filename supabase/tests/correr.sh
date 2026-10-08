#!/usr/bin/env bash
# Corre as migrações REAIS contra um Postgres efémero e depois os testes SQL.
#
#   supabase/tests/correr.sh
#
# Precisa só dos binários do Postgres (initdb, pg_ctl, psql) — sem Docker,
# sem npm. O cluster vive numa pasta temporária e é apagado no fim.
#
# Cada ficheiro NN_*.sql em supabase/tests/ corre por ordem numa base
# nova; um teste falha levantando uma exceção (ON_ERROR_STOP).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
MIGRACOES="$AQUI/../migrations"

if ! command -v initdb >/dev/null 2>&1; then
  for d in /usr/lib/postgresql/*/bin; do PATH="$d:$PATH"; done
fi
command -v initdb >/dev/null || { echo "initdb não encontrado"; exit 2; }

TMP="$(mktemp -d)"
PORTA="${PGPORT_TESTES:-54329}"
trap 'pg_ctl -D "$TMP/dados" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

# initdb recusa correr como root; num contentor de CI pode ser o caso.
CORRER=()
if [ "$(id -u)" = "0" ]; then
  id postgres >/dev/null 2>&1 || useradd -m postgres
  chown -R postgres "$TMP"
  CORRER=(runuser -u postgres --)
fi

"${CORRER[@]}" initdb -D "$TMP/dados" -U postgres --auth=trust -E UTF8 --locale=C.UTF-8 >/dev/null
"${CORRER[@]}" pg_ctl -D "$TMP/dados" -o "-p $PORTA -k $TMP -c listen_addresses=''" -l "$TMP/log" -w start >/dev/null

PSQL=(psql -h "$TMP" -p "$PORTA" -U postgres -X -q -v ON_ERROR_STOP=1)
falhas=0

for teste in "$AQUI"/[0-9][0-9]_*.sql; do
  nome="$(basename "$teste")"
  [ "$nome" = "00_shim_supabase.sql" ] && continue
  base="t_$(echo "$nome" | tr -c 'a-z0-9' '_')"
  "${PSQL[@]}" -d postgres -c "create database $base" >/dev/null
  {
    "${PSQL[@]}" -d "$base" -f "$AQUI/00_shim_supabase.sql"
    for m in "$MIGRACOES"/*.sql; do "${PSQL[@]}" -d "$base" -f "$m"; done
    "${PSQL[@]}" -d "$base" -f "$AQUI/_ajuda.sql"
  } >/dev/null 2>"$TMP/erro" || { echo "FALHA  migrações ($nome)"; cat "$TMP/erro"; exit 1; }

  # SUPABASE: os testes que leem ficheiros do repositório (85_reconciliacao) usam-no.
  if "${PSQL[@]}" -At -d "$base" -v SUPABASE="$AQUI/.." -f "$teste" >"$TMP/saida" 2>&1; then
    echo "ok     $nome ($(grep -c '^ok' "$TMP/saida" || true) verificações)"
    [ -n "${VERBOSO:-}" ] && sed "s/^/       /" "$TMP/saida"
  else
    echo "FALHA  $nome"; sed 's/^/       /' "$TMP/saida"
    falhas=$((falhas + 1))
  fi
done

[ "$falhas" -eq 0 ] && echo "Tudo verde." || { echo "$falhas ficheiro(s) com falhas."; exit 1; }
