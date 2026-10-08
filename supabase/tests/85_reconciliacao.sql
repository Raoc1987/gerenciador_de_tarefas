-- A consulta de assinaturas (supabase/reconciliacao/assinaturas.sql) corre
-- sobre as migrações reais e devolve todas as categorias. É o fio de tropeço da
-- skill reconciliar-esquema: uma consulta partida ou sem permissão devolve
-- menos categorias sem dar erro, e a comparação com produção mentia.

\set consulta `cat :SUPABASE/reconciliacao/assinaturas.sql`
create temp table assinaturas as :consulta;

select t.ok((select count(*) from assinaturas) = 11, 'as onze categorias aparecem');
select t.ok((select bool_and(objetos > 0 and assinatura ~ '^[0-9a-f]{32}$') from assinaturas),
            'cada categoria tem objetos e uma assinatura md5');
select t.ok((select objetos from assinaturas where categoria = 'enums') = 5, 'os cinco enums do produto');

-- A assinatura muda quando o esquema muda: uma política a mais tem de se ver.
select assinatura as antes from assinaturas where categoria = 'politicas' \gset
create policy deriva_de_ensaio on public.planos for select to authenticated using (false);
create temp table depois as :consulta;
select t.ok((select assinatura from depois where categoria = 'politicas') <> :'antes',
            'uma política nova muda a assinatura das políticas');
select t.ok((select count(*) from assinaturas a join depois d using (categoria)
             where a.assinatura <> d.assinatura) = 1, 'e só essa categoria muda');
