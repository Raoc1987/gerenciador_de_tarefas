-- Libertar a reserva quando o modelo falha (20261020000000_copiloto_libertar.sql).

select t.pessoa('dona@cl.pt')  as dona  \gset
select t.pessoa('col@cl.pt')   as col   \gset
select t.pessoa('fora@cl.pt')  as fora  \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Liberta') as emp \gset
reset role;
insert into public.membros values (:'emp', :'col', 'colaborador');
select t.sessao(:'fora'); set role authenticated;
select public.criar_empresa('Outra') as outra \gset
reset role;

-- O hash é o mesmo que o servidor calcula: o mesmo valor está em
-- web/lib/copiloto/reserva.test.ts, para as duas pontas não divergirem.
select encode(pg_catalog.sha256(convert_to('chave-de-teste', 'UTF8')), 'hex') as hash_teste \gset
select t.ok(:'hash_teste' = 'f957e85f6eccfd653d8e8d7e20513a49ae07a34423d8d991b12b03d27a479318', 'o hash da base é o mesmo que o do servidor');

-- O formato do hash é verificado pela base.
select t.sessao(:'col'); set role authenticated;
select t.recusa_por(format($$insert into public.copiloto_uso (empresa_id, chave_hash) values (%L, 'nao-e-hex')$$, :'emp'),
                    'chave_hash_check', 'um hash fora do formato é recusado');
reset role;

-- Reserva com a chave: liberta-se e deixa de existir.
select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id, chave_hash) values (:'emp', :'hash_teste') returning id as r1 \gset
select t.ok(not public.copiloto_libertar_reserva(:r1, 'outra-chave'), 'com a chave errada não se liberta');
select t.ok(not public.copiloto_libertar_reserva(:r1, null), 'sem chave não se liberta');
select t.ok(public.copiloto_libertar_reserva(:r1, 'chave-de-teste'), 'com a chave certa liberta-se');
select t.ok(not public.copiloto_libertar_reserva(:r1, 'chave-de-teste'), 'e só uma vez');
reset role;
select t.ok(not exists (select 1 from public.copiloto_uso where id = :r1), 'a reserva desapareceu');

-- Uma reserva feita sem chave (como antes) nunca se liberta.
select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id) values (:'emp') returning id as sem_chave \gset
select t.ok(not public.copiloto_libertar_reserva(:sem_chave, ''), 'uma reserva sem chave não se liberta');
reset role;

-- Com tokens registados (houve resposta) já não se liberta.
select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id, chave_hash) values (:'emp', :'hash_teste') returning id as respondida \gset
select t.ok(public.copiloto_registar_tokens(:respondida, 10, 5), 'regista os tokens');
select t.ok(not public.copiloto_libertar_reserva(:respondida, 'chave-de-teste'), 'uma pergunta respondida não se liberta');
reset role;

-- A reserva de outra pessoa, mesmo com a chave, não se toca.
select t.sessao(:'dona'); set role authenticated;
insert into public.copiloto_uso (empresa_id, chave_hash) values (:'emp', :'hash_teste') returning id as da_dona \gset
reset role;
select t.sessao(:'col'); set role authenticated;
select t.ok(not public.copiloto_libertar_reserva(:da_dona, 'chave-de-teste'), 'não se liberta a reserva de outra pessoa');
reset role;
-- Nem a partir de outra empresa.
select t.sessao(:'fora'); set role authenticated;
select t.ok(not public.copiloto_libertar_reserva(:da_dona, 'chave-de-teste'), 'nem alguém de outra empresa');
reset role;
select t.ok(exists (select 1 from public.copiloto_uso where id = :da_dona), 'e ela fica');

-- Uma reserva antiga já não se liberta.
insert into public.copiloto_uso (empresa_id, user_id, chave_hash) values (:'emp', :'col', :'hash_teste') returning id as antiga \gset
update public.copiloto_uso set em = now() - interval '1 hour' where id = :antiga;
select t.sessao(:'col'); set role authenticated;
select t.ok(not public.copiloto_libertar_reserva(:antiga, 'chave-de-teste'), 'uma reserva com mais de 15 minutos não se liberta');
reset role;

-- O ponto disto: libertar devolve a pergunta ao plano.
delete from public.copiloto_uso where empresa_id = :'emp';
insert into public.copiloto_uso (empresa_id, user_id) select :'emp', :'dona' from generate_series(1, 49);
select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id, chave_hash) values (:'emp', :'hash_teste') returning id as ultima \gset
select t.recusa_por(format($$insert into public.copiloto_uso (empresa_id) values (%L)$$, :'emp'),
                    '50 perguntas ao copiloto por mês', 'com o plano cheio, a 51.ª é recusada');
select t.ok(public.copiloto_libertar_reserva(:ultima, 'chave-de-teste'), 'liberta-se a que falhou');
insert into public.copiloto_uso (empresa_id) values (:'emp');
select t.ok(true, 'e a pergunta seguinte já cabe no plano');
reset role;

set role anon;
select t.recusa($$select public.copiloto_libertar_reserva(1, 'x')$$, 'sem sessão não se liberta nada');
reset role;
