-- Dados de planeamento: limites e quem os escreve (as regras de escrita
-- das tarefas, sem exceções).

select t.pessoa('dona@c.pt') as dona \gset
select t.pessoa('col@c.pt')  as col  \gset
select t.pessoa('leit@c.pt') as leit \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Crono') as crono \gset
insert into public.tarefas (empresa_id, titulo, duracao_dias, inicio_minimo)
  values (:'crono', 'Planeada', 5, '2026-11-02') returning id as planeada \gset
reset role;
insert into public.membros values (:'crono', :'col', 'colaborador'), (:'crono', :'leit', 'leitor');

select t.ok((select duracao_dias from public.tarefas where id = :'planeada') = 5, 'a duração grava-se');
select t.ok((select inicio_minimo from public.tarefas where id = :'planeada') = '2026-11-02', 'o início mínimo grava-se');

select t.sessao(:'dona'); set role authenticated;
update public.tarefas set duracao_dias = 0 where id = :'planeada';
select t.recusa_por(format($$update public.tarefas set duracao_dias = -1 where id = %L$$, :'planeada'),
                    'tarefas_duracao_dias_check', 'duração negativa recusada');
select t.recusa_por(format($$update public.tarefas set duracao_dias = 1001 where id = %L$$, :'planeada'),
                    'tarefas_duracao_dias_check', 'duração absurda recusada');
reset role;
select t.ok((select duracao_dias from public.tarefas where id = :'planeada') = 0, 'um marco tem duração 0');

-- O colaborador não escreve numa tarefa que não é sua; o leitor em nenhuma.
select t.sessao(:'col'); set role authenticated;
select t.ok(t.linhas(format($$update public.tarefas set duracao_dias = 9 where id = %L$$, :'planeada')) = 0,
            'o colaborador não planeia tarefas alheias');
insert into public.tarefas (empresa_id, titulo, responsavel_id, duracao_dias) values (:'crono', 'Minha', auth.uid(), 3)
  returning id as minha \gset
select t.ok(t.linhas(format($$update public.tarefas set duracao_dias = 4 where id = %L$$, :'minha')) = 1,
            'o colaborador planeia as suas');
reset role;
select t.sessao(:'leit'); set role authenticated;
select t.ok(t.linhas(format($$update public.tarefas set duracao_dias = 2 where id = %L$$, :'minha')) = 0,
            'o leitor não planeia');
reset role;
