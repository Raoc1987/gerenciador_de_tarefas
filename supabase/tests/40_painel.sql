-- Indicadores do painel: os números são os das tarefas que quem pergunta vê.

select t.pessoa('dona@a.pt') as dona \gset
select t.pessoa('col@a.pt')  as col  \gset
select t.pessoa('fora@b.pt') as fora \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
reset role;
insert into public.membros values (:'alfa', :'col', 'colaborador');

select t.sessao(:'dona'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, prazo, prioridade) values
  (:'alfa', 'Atrasada', current_date - 3, 'urgente'),
  (:'alfa', 'Hoje', current_date, 'alta'),
  (:'alfa', 'Futura', current_date + 5, 'baixa');
insert into public.tarefas (empresa_id, titulo, responsavel_id, prazo) values
  (:'alfa', 'Do colaborador', :'col', current_date - 1);
update public.tarefas set estado = 'concluida' where titulo = 'Futura';

select public.indicadores_painel(:'alfa') as p \gset
select t.ok((:'p'::jsonb ->> 'total')::int = 4, 'a proprietária vê o total da empresa');
select t.ok((:'p'::jsonb ->> 'abertas')::int = 3, 'abertas');
select t.ok((:'p'::jsonb ->> 'atrasadas')::int = 2, 'atrasadas: prazo passado e não concluída');
select t.ok((:'p'::jsonb ->> 'vencem_hoje')::int = 1, 'vencem hoje');
select t.ok((:'p'::jsonb ->> 'concluidas_periodo')::int = 1, 'concluídas no período');
select t.ok((:'p'::jsonb -> 'por_estado' ->> 'concluida')::int = 1, 'por estado');
select t.ok((:'p'::jsonb -> 'por_prioridade' ->> 'urgente')::int = 1, 'por prioridade, só as abertas');
select t.ok(jsonb_array_length(:'p'::jsonb -> 'serie') = 30, 'série de 30 dias');
select t.ok((select sum((d ->> 'criadas')::int) from jsonb_array_elements(:'p'::jsonb -> 'serie') d) = 4,
            'a série conta as criadas');
select t.ok(jsonb_array_length(public.indicadores_painel(:'alfa', 1) -> 'serie') = 7,
            'o período tem um mínimo de 7 dias');
reset role;

select t.sessao(:'col'); set role authenticated;
select public.indicadores_painel(:'alfa') as pc \gset
select t.ok((:'pc'::jsonb ->> 'total')::int = 1, 'o colaborador vê os números das suas, não os da empresa');
select t.ok((:'pc'::jsonb ->> 'atrasadas')::int = 1, 'incluindo as suas atrasadas');
reset role;

select t.sessao(:'fora'); set role authenticated;
select t.ok((public.indicadores_painel(:'alfa') ->> 'total')::int = 0, 'quem é de fora não vê nada');
reset role;
set role anon;
select t.recusa(format($$select public.indicadores_painel(%L)$$, :'alfa'), 'anónimo não pergunta');
reset role;

-- O hoje é o de quem pergunta: amanhã, a de hoje já está atrasada.
select t.sessao(:'dona'); set role authenticated;
select t.ok((public.indicadores_painel(:'alfa', 30, current_date + 1) ->> 'atrasadas')::int = 3,
            'o dia de referência vem de quem pergunta');
reset role;
