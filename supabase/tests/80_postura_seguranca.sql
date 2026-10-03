-- Postura de segurança lida do catálogo, depois de todas as migrações.
--
-- Os outros ficheiros provam cada regra com pessoas e pedidos; este prova
-- que nenhuma tabela ou função nova escapou às regras gerais, que é onde um
-- esquecimento passa em todos os testes de comportamento.

-- Funções que pertencem a extensões (pgcrypto, …) não são nossas.
create temporary view nossas_funcoes as
  select p.oid, p.proname, p.prosecdef, p.proconfig, pg_get_function_result(p.oid) as resultado
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and not exists (select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e');

select t.ok(not exists (
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind in ('r', 'p') and not c.relrowsecurity
), 'todas as tabelas de public têm RLS ligada');

-- Sem policies, ninguém em sessão lê nem escreve. Só é aceitável para o que
-- vive fora do alcance de qualquer pessoa, e cada caso fica nomeado aqui.
select t.ok(coalesce((
  select array_agg(c.relname::text order by c.relname)
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity
    and not exists (select 1 from pg_policy p where p.polrelid = c.oid)
), '{}') = array['emails_pendentes'],
'só a fila de emails (do carteiro) não tem policies');

select t.ok(not exists (
  select 1 from nossas_funcoes
  where prosecdef
    and not exists (select 1 from unnest(coalesce(proconfig, '{}')) c where c like 'search_path=%')
), 'toda a função security definer fixa o search_path');

select t.ok(not exists (
  select 1 from nossas_funcoes where has_function_privilege('anon', oid, 'execute')
), 'anon não executa nenhuma função de public');

select t.ok(not exists (
  select 1 from information_schema.role_table_grants
  where grantee = 'anon' and table_schema = 'public'
), 'anon não tem nenhum privilégio em tabelas de public');

select t.ok(not exists (
  select 1 from nossas_funcoes
  where resultado = 'trigger' and has_function_privilege('authenticated', oid, 'execute')
), 'nenhuma função de gatilho é executável por quem está em sessão');

select t.ok(not exists (
  select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'v'
    and not coalesce('security_invoker=true' = any (c.reloptions), false)
), 'toda a view de public corre com os direitos de quem a lê');

select t.ok(not has_schema_privilege('anon', 'interno', 'usage') and not has_schema_privilege('authenticated', 'interno', 'usage'),
            'ninguém em sessão entra no esquema interno (modos da importação e do apagamento)');

-- A próxima migração também fica coberta: uma função criada agora não nasce
-- executável por anon.
create function public.sonda_postura() returns int language sql as 'select 1';
select t.ok(not has_function_privilege('anon', 'public.sonda_postura()', 'execute'),
            'uma função nova em public não nasce executável por anon');
select t.ok(has_function_privilege('authenticated', 'public.sonda_postura()', 'execute'),
            'e continua executável por quem está em sessão');
drop function public.sonda_postura();
