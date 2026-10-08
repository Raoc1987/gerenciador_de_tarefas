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
"${CORRER[@]}" pg_ctl -D "$TMP/dados" -o "-p $PORTA -k $TMP -c listen_addresses='' -c track_functions=all" -l "$TMP/log" -w start >/dev/null

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
  # Só contam as chamadas feitas pelo teste, não as das migrações.
  "${PSQL[@]}" -d "$base" -c "select pg_stat_reset()" >/dev/null

  # SUPABASE: os testes que leem ficheiros do repositório (85_reconciliacao) usam-no.
  if "${PSQL[@]}" -At -d "$base" -v SUPABASE="$AQUI/.." -f "$teste" >"$TMP/saida" 2>&1; then
    echo "ok     $nome ($(grep -c '^ok' "$TMP/saida" || true) verificações)"
    [ -n "${VERBOSO:-}" ] && sed "s/^/       /" "$TMP/saida"
  else
    echo "FALHA  $nome"; sed 's/^/       /' "$TMP/saida"
    falhas=$((falhas + 1))
  fi
  # Que funções o teste chamou de facto (track_functions=all).
  "${PSQL[@]}" -At -d "$base" -c "select schemaname || '.' || funcname from pg_stat_user_functions
    where schemaname in ('public', 'interno') and calls > 0" >>"$TMP/chamadas"
  ultima="$base"
done

# Cada função das migrações tem de correr em pelo menos um teste. Ter o nome num
# ficheiro de teste não basta: os gatilhos e as funções de apoio correm por
# arrasto, e só o Postgres sabe se correram. As exceções vivem num ficheiro, com
# a razão de cada uma (supabase/tests/funcoes-sem-chamada.txt).
"${PSQL[@]}" -At -d "$ultima" -c "select n.nspname || '.' || p.proname from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace where n.nspname in ('public', 'interno')
  and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')" | sort -u >"$TMP/todas"
sort -u "$TMP/chamadas" >"$TMP/chamadas_u"
{ grep -v '^\s*\(#\|$\)' "$AQUI/funcoes-sem-chamada.txt" || true; } | awk '{print $1}' | sort -u >"$TMP/excecoes"
nunca="$(comm -23 "$TMP/todas" "$TMP/chamadas_u" | comm -23 - "$TMP/excecoes")"
obsoletas="$(comm -13 "$TMP/todas" "$TMP/excecoes")"
echo "funções chamadas pelos testes: $(comm -12 "$TMP/todas" "$TMP/chamadas_u" | wc -l) de $(wc -l <"$TMP/todas")"
if [ -n "$nunca" ]; then
  echo "FALHA  funções que nenhum teste chama:"; echo "$nunca" | sed 's/^/       /'; falhas=$((falhas + 1))
fi
if [ -n "$obsoletas" ]; then
  echo "FALHA  exceções para funções que já não existem:"; echo "$obsoletas" | sed 's/^/       /'; falhas=$((falhas + 1))
fi

[ "$falhas" -eq 0 ] && echo "Tudo verde." || { echo "$falhas ficheiro(s) com falhas."; exit 1; }
