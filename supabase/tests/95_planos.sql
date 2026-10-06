-- Planos: os limites recusam na base, o plano só muda pela faturação, e os
-- eventos do fornecedor aplicam-se uma vez e pela ordem certa.

select t.pessoa('dona@p.pt')  as dona  \gset
select t.pessoa('admin@p.pt') as admin \gset
select t.pessoa('col@p.pt')   as col   \gset
select t.pessoa('p4@p.pt')    as p4    \gset
select t.pessoa('p5@p.pt')    as p5    \gset
select t.pessoa('p6@p.pt')    as p6    \gset
select t.pessoa('fora@p.pt')  as fora  \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Plana') as plana \gset
reset role;

select t.ok((select plano from public.empresas where id = :'plana') = 'gratuito', 'uma empresa nova começa no Gratuito');

-- ---------------------------------------------------------------- membros

insert into public.membros values (:'plana', :'admin', 'administrador'), (:'plana', :'col', 'colaborador'), (:'plana', :'p4', 'colaborador');
-- 4 pessoas; o Gratuito permite 5. Um convite pendente guarda o 5.º lugar.
select t.sessao(:'admin'); set role authenticated;
insert into public.convites (empresa_id, email, papel, criado_por) values (:'plana', 'quinta@p.pt', 'colaborador', auth.uid());
select t.recusa_por(format($$insert into public.convites (empresa_id, email, papel, criado_por) values (%L, 'sexta@p.pt', 'colaborador', auth.uid())$$, :'plana'),
                    'permite até 5 pessoas', 'não se convida para lá do limite, contando os convites pendentes');
reset role;
insert into public.membros values (:'plana', :'p5', 'colaborador');
select t.recusa_por(format($$insert into public.membros values (%L, %L, 'colaborador')$$, :'plana', :'p6'),
                    'o plano Gratuito permite até 5 pessoas', 'a sexta pessoa é recusada, mesmo a quem contorna a RLS');

-- ----------------------------------------------------------------- tarefas

insert into public.tarefas (empresa_id, titulo, criada_por, estado)
  select :'plana', 'Tarefa ' || g, :'dona', 'a_fazer' from generate_series(1, 199) g;
select t.sessao(:'dona'); set role authenticated;
insert into public.tarefas (empresa_id, titulo) values (:'plana', 'A ducentésima') returning id as t200 \gset
select t.recusa_por(format($$insert into public.tarefas (empresa_id, titulo) values (%L, 'Uma a mais')$$, :'plana'),
                    'permite até 200 tarefas por concluir', 'a 201.ª tarefa por concluir é recusada');
insert into public.tarefas (empresa_id, titulo, estado) values (:'plana', 'Já feita', 'concluida') returning id as feita \gset
update public.tarefas set estado = 'concluida' where id = :'t200';
insert into public.tarefas (empresa_id, titulo) values (:'plana', 'Cabe outra vez') returning id as cabe \gset
select t.recusa_por(format($$update public.tarefas set estado = 'a_fazer' where id = %L$$, :'feita'),
                    'tarefas por concluir', 'reabrir também conta para o limite');
update public.tarefas set titulo = 'Editar não conta' where id = :'cabe';
reset role;
select t.ok(:'feita' is not null and :'cabe' is not null, 'concluídas não contam, e concluir liberta um lugar');

-- ---------------------------------------------------------------- copiloto

insert into public.copiloto_uso (empresa_id, user_id)
  select :'plana', :'dona' from generate_series(1, 50);
select t.sessao(:'col'); set role authenticated;
select t.recusa_por(format($$insert into public.copiloto_uso (empresa_id) values (%L)$$, :'plana'),
                    '50 perguntas ao copiloto por mês', 'a 51.ª pergunta do mês é recusada, contada por empresa');
select public.uso_do_plano(:'plana') as uso \gset
reset role;
select t.ok((:'uso'::jsonb -> 'membros' ->> 'usados')::int = 5 and (:'uso'::jsonb -> 'membros' ->> 'maximo')::int = 5,
            'o uso do plano diz quantas pessoas há e quantas cabem');
select t.ok((:'uso'::jsonb -> 'copiloto_mes' ->> 'usados')::int = 50, 'e quantas perguntas já se fizeram este mês');

select t.sessao(:'fora'); set role authenticated;
select t.recusa_por(format($$select public.uso_do_plano(%L)$$, :'plana'), 'não é membro', 'quem é de fora não vê o uso do plano');
reset role;

-- ------------------------------------------------- o plano não se escreve

select t.sessao(:'dona'); set role authenticated;
select t.recusa_por(format($$update public.empresas set plano = 'empresa' where id = %L$$, :'plana'),
                    'permission denied', 'nem a proprietária escolhe o plano escrevendo na tabela (a coluna não se concede)');
reset role;
-- Segunda barreira: mesmo que um dia alguém conceda as colunas, o gatilho recusa.
grant update (plano, plano_ate) on public.empresas to authenticated;
select t.sessao(:'dona'); set role authenticated;
select t.recusa_por(format($$update public.empresas set plano = 'empresa' where id = %L$$, :'plana'),
                    'o plano muda só pela faturação', 'com a coluna concedida, o gatilho recusa na mesma');
select t.recusa_por(format($$update public.empresas set plano_ate = now() + interval '10 years' where id = %L$$, :'plana'),
                    'o plano muda só pela faturação', 'e não deixa esticar o período pago');
reset role;
revoke update (plano, plano_ate) on public.empresas from authenticated;
select t.sessao(:'dona'); set role authenticated;
update public.empresas set nome = 'Plana, Lda.' where id = :'plana';
select public.preparar_faturacao(:'plana') as prep \gset
reset role;
select t.ok((:'prep'::jsonb ->> 'email') = 'dona@p.pt', 'a proprietária prepara a faturação com o seu email');
select t.ok((select nome from public.empresas where id = :'plana') = 'Plana, Lda.', 'o resto da empresa edita-se como antes');

select t.sessao(:'admin'); set role authenticated;
select t.recusa_por(format($$select public.preparar_faturacao(%L)$$, :'plana'), 'só a pessoa proprietária', 'um administrador não paga pela empresa');
select t.recusa_por(format($$select public.aplicar_faturacao('evt_x', now(), %L, 'empresa', null, null, null)$$, :'plana'),
                    'permission denied', 'ninguém em sessão aplica eventos de faturação');
select t.recusa($$select * from interno.faturacao$$, 'os dados do fornecedor não se leem pela API');
reset role;
set role anon;
select t.recusa($$select * from public.planos$$, 'sem sessão não se veem os planos');
reset role;

-- ------------------------------------------------- eventos do fornecedor

set role service_role;
select t.ok(public.aplicar_faturacao('evt_1', '2026-10-01 10:00+00', :'plana', 'equipa', now() + interval '30 days', 'cus_1', 'sub_1'),
            'um evento novo muda o plano');
select t.ok(not public.aplicar_faturacao('evt_1', '2026-10-01 10:00+00', :'plana', 'empresa', null, 'cus_1', 'sub_1'),
            'o mesmo evento outra vez não muda nada');
select t.ok(not public.aplicar_faturacao('evt_0', '2026-09-30 10:00+00', :'plana', 'gratuito', null, null, null),
            'um evento mais antigo do que o último aplicado não volta atrás');
select t.ok(not public.aplicar_faturacao('evt_2', now(), gen_random_uuid(), 'equipa', null, null, null),
            'um evento para uma empresa que não existe é ignorado');
reset role;
select t.ok((select plano from public.empresas where id = :'plana') = 'equipa', 'a empresa fica no plano pago');
select t.ok((select cliente from interno.faturacao where empresa_id = :'plana') = 'cus_1', 'e com o cliente do fornecedor guardado');
select t.ok(exists (select 1 from public.auditoria where entidade = 'empresas' and entidade_id = :'plana'
                    and depois ->> 'plano' = 'equipa'), 'a mudança de plano fica na auditoria');
insert into public.membros values (:'plana', :'p6', 'colaborador');
select t.ok(true, 'no plano Equipa cabe a sexta pessoa');

-- Período pago que acabou há mais de 3 dias sem renovação: conta como Gratuito.
set role service_role;
select public.aplicar_faturacao('evt_3', now(), :'plana', 'equipa', now() - interval '4 days', null, null);
reset role;
select t.ok(public.plano_efetivo(:'plana') = 'gratuito', 'um período pago caducado conta como Gratuito');
select t.recusa_por(format($$insert into public.tarefas (empresa_id, titulo, criada_por) values (%L, 'Depois de caducar', %L)$$, :'plana', :'dona'),
                    'o plano Gratuito', 'e os limites do Gratuito voltam a aplicar-se');
