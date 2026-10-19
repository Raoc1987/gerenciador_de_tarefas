-- Assinaturas do esquema por categoria (skill reconciliar-esquema).
--
-- Só leitura: um SELECT, sem efeitos. Corre-se igual nas migrações (CI,
-- supabase/tests/85_reconciliacao.sql) e em produção, e compara-se linha a
-- linha. Uma categoria com assinatura diferente é deriva; uma categoria que só
-- existe de um lado é deriva da própria consulta, não da base.
--
-- A lista de categorias vive AQUI e em mais lado nenhum. O teste conta-as.
-- Sem ponto e vírgula no fim: o teste inclui este ficheiro dentro de outra instrução.
with
esquemas as (select unnest(array['public', 'interno']) as nome),
tabelas as (
  select n.nspname || '.' || c.relname || ':' || a.attname || ':' || format_type(a.atttypid, a.atttypmod)
         || ':' || a.attnotnull || ':' || coalesce(pg_get_expr(d.adbin, d.adrelid), '') as linha
  from pg_attribute a
  join pg_class c on c.oid = a.attrelid and c.relkind in ('r', 'p', 'v')
  join pg_namespace n on n.oid = c.relnamespace and n.nspname in (select nome from esquemas)
  left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
  where a.attnum > 0 and not a.attisdropped
),
rls as (
  select n.nspname || '.' || c.relname || ':' || c.relrowsecurity || ':' || c.relforcerowsecurity as linha
  from pg_class c join pg_namespace n on n.oid = c.relnamespace and n.nspname in (select nome from esquemas)
  where c.relkind in ('r', 'p')
),
funcoes as (
  select n.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || '):'
         || p.prosecdef || ':' || coalesce(array_to_string(p.proconfig, ','), '') || ':' || md5(p.prosrc) as linha
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace and n.nspname in (select nome from esquemas)
),
politicas as (
  select schemaname || '.' || tablename || ':' || policyname || ':' || cmd || ':' || array_to_string(roles, ',')
         || ':' || coalesce(qual, '') || ':' || coalesce(with_check, '') as linha
  from pg_policies where schemaname in (select nome from esquemas)
),
gatilhos as (
  select n.nspname || '.' || c.relname || ':' || t.tgname || ':' || pg_get_triggerdef(t.oid) as linha
  from pg_trigger t join pg_class c on c.oid = t.tgrelid
  join pg_namespace n on n.oid = c.relnamespace and n.nspname in (select nome from esquemas)
  where not t.tgisinternal
),
restricoes as (
  select n.nspname || '.' || c.relname || ':' || k.conname || ':' || pg_get_constraintdef(k.oid) as linha
  from pg_constraint k join pg_class c on c.oid = k.conrelid
  join pg_namespace n on n.oid = c.relnamespace and n.nspname in (select nome from esquemas)
),
indices as (
  select schemaname || '.' || indexname || ':' || indexdef as linha
  from pg_indexes where schemaname in (select nome from esquemas)
),
enums as (
  select n.nspname || '.' || t.typname || ':' || string_agg(e.enumlabel, ',' order by e.enumsortorder) as linha
  from pg_type t join pg_enum e on e.enumtypid = t.oid
  join pg_namespace n on n.oid = t.typnamespace and n.nspname in (select nome from esquemas)
  group by n.nspname, t.typname
),
grants_tabelas as (
  select table_schema || '.' || table_name || ':' || grantee || ':' || privilege_type as linha
  from information_schema.role_table_grants
  where table_schema in (select nome from esquemas) and grantee in ('anon', 'authenticated', 'service_role')
),
grants_colunas as (
  select table_schema || '.' || table_name || '.' || column_name || ':' || grantee || ':' || privilege_type as linha
  from information_schema.column_privileges
  where table_schema in (select nome from esquemas) and grantee in ('anon', 'authenticated')
),
grants_funcoes as (
  select n.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || '):' || r.rolname as linha
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace and n.nspname in (select nome from esquemas)
  cross join (select rolname from pg_roles where rolname in ('anon', 'authenticated', 'service_role')) r
  where has_function_privilege(r.rolname, p.oid, 'execute')
),
todas as (
  select 'tabelas' as categoria, linha from tabelas
  union all select 'rls', linha from rls
  union all select 'funcoes', linha from funcoes
  union all select 'politicas', linha from politicas
  union all select 'gatilhos', linha from gatilhos
  union all select 'restricoes', linha from restricoes
  union all select 'indices', linha from indices
  union all select 'enums', linha from enums
  union all select 'grants_tabelas', linha from grants_tabelas
  union all select 'grants_colunas', linha from grants_colunas
  union all select 'grants_funcoes', linha from grants_funcoes
)
select categoria, count(*) as objetos, md5(string_agg(linha, E'\n' order by linha)) as assinatura
from todas group by categoria order by categoria
