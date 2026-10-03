-- Shim do que o Supabase traz e as migrações não criam: o schema `auth`, os
-- papéis `anon`/`authenticated`/`service_role`, os grants por omissão e a
-- publicação do Realtime. Nada aqui é schema do produto.
--
-- auth.uid() lê as claims do pedido como o Supabase moderno faz, por isso
-- "estar em sessão como X" num teste é:
--   set local role authenticated;
--   set local request.jwt.claims = '{"sub": "<uuid de X>"}';

-- Os papéis são do cluster, não da base: cada ficheiro de teste corre numa
-- base nova do mesmo cluster.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
    create role authenticated nologin;
    create role service_role nologin bypassrls;
  end if;
end $$;

create schema auth;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;

create table auth.users (
  id                 uuid primary key default gen_random_uuid(),
  email              text,
  raw_user_meta_data jsonb not null default '{}'
);

create function auth.uid() returns uuid language sql stable as $$
  select nullif(
    coalesce(
      nullif(current_setting('request.jwt.claim.sub', true), ''),
      nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
    ), '')::uuid
$$;

alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;

create publication supabase_realtime;
