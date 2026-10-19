-- A reserva da pergunta e o registo dos tokens (20261008000000_copiloto_reserva.sql).

select t.pessoa('dona@cr.pt') as dona \gset
select t.pessoa('col@cr.pt')  as col  \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Reserva') as emp \gset
reset role;
insert into public.membros values (:'emp', :'col', 'colaborador');

-- Reservar é inserir a linha de uso sem tokens, com a sessão da pessoa.
select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id) values (:'emp') returning id as reserva \gset
select t.ok(public.copiloto_registar_tokens(:reserva, 1200, 300), 'os tokens registam-se na própria reserva');
select t.ok(not public.copiloto_registar_tokens(:reserva, 1, 1), 'e só uma vez: o custo não se reescreve');
select t.recusa_por(format($$select public.copiloto_registar_tokens(%s, -1, 0)$$, :reserva),
                    'não podem ser negativos', 'tokens negativos são recusados');
reset role;
select t.ok((select tokens_entrada from public.copiloto_uso where id = :reserva) = 1200, 'ficou o primeiro registo');

-- A reserva de outra pessoa não se toca.
select t.sessao(:'dona'); set role authenticated;
insert into public.copiloto_uso (empresa_id) values (:'emp') returning id as da_dona \gset
reset role;
select t.sessao(:'col'); set role authenticated;
select t.ok(not public.copiloto_registar_tokens(:da_dona, 999, 999), 'não se registam tokens na reserva de outra pessoa');
reset role;
select t.ok((select tokens_entrada from public.copiloto_uso where id = :da_dona) = 0, 'e ela fica como estava');

-- Uma reserva antiga já não aceita tokens.
insert into public.copiloto_uso (empresa_id, user_id) values (:'emp', :'col') returning id as antiga \gset
update public.copiloto_uso set em = now() - interval '1 hour' where id = :antiga;
select t.sessao(:'col'); set role authenticated;
select t.ok(not public.copiloto_registar_tokens(:antiga, 5, 5), 'uma reserva com mais de 15 minutos não aceita tokens');
reset role;

-- O limite do plano recusa NA RESERVA, antes de haver custo, e com a frase certa.
insert into public.copiloto_uso (empresa_id, user_id) select :'emp', :'dona' from generate_series(1, 47);
select t.sessao(:'col'); set role authenticated;
select t.recusa_por(format($$insert into public.copiloto_uso (empresa_id) values (%L)$$, :'emp'),
                    '50 perguntas ao copiloto por mês', 'a reserva da 51.ª pergunta é recusada pelo plano');
reset role;

set role anon;
select t.recusa($$select public.copiloto_registar_tokens(1, 1, 1)$$, 'sem sessão não se registam tokens');
reset role;
