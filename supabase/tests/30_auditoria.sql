-- Auditoria: tudo fica registado, com a empresa do momento; ninguém a altera,
-- e só quem administra a lê.

select t.pessoa('dona@a.pt') as dona \gset
select t.pessoa('col@a.pt')  as col  \gset
select t.pessoa('outra@b.pt') as outra \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
insert into public.convites (empresa_id, email, criado_por) values (:'alfa', 'col@a.pt', auth.uid())
  returning token as token \gset
reset role;
select t.sessao(:'col'); set role authenticated;
select public.aceitar_convite(:'token');
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'alfa', 'Relatório', auth.uid())
  returning id as tarefa \gset
update public.tarefas set prioridade = 'alta' where id = :'tarefa';
update public.tarefas set prioridade = 'alta' where id = :'tarefa';
select t.ok((select count(*) from public.auditoria) = 0, 'um colaborador não lê a auditoria');
select t.recusa($$insert into public.auditoria (acao, entidade, entidade_id) values ('forjada', 'x', '1')$$,
                'ninguém escreve na auditoria diretamente');
reset role;

select t.sessao(:'outra'); set role authenticated;
select public.criar_empresa('Beta');
select t.ok((select count(*) from public.auditoria where empresa_id = :'alfa') = 0,
            'outra empresa não lê a auditoria da Alfa');
reset role;

select t.sessao(:'dona'); set role authenticated;
select t.ok((select count(*) from public.auditoria where entidade = 'tarefas') = 2,
            'criar e mudar a tarefa: 2 linhas (a gravação sem diferenças não conta)');
select t.ok((select antes ->> 'prioridade' = 'media' and depois ->> 'prioridade' = 'alta'
             from public.auditoria where entidade = 'tarefas' and acao = 'update'),
            'guarda o antes e o depois');
select t.ok((select actor_id from public.auditoria where entidade = 'tarefas' and acao = 'insert') = :'col'::uuid,
            'guarda quem fez');
select t.ok((select count(*) from public.auditoria where entidade = 'membros') = 2,
            'a entrada da proprietária e do colaborador ficam registadas');
select t.ok(not exists (select 1 from public.auditoria
                        where entidade = 'convites' and (depois ? 'token' or antes ? 'token')),
            'o token de um convite não vai para a trilha');
select t.recusa($$update public.auditoria set acao = 'apagado'$$, 'a proprietária não altera a auditoria');
select t.recusa($$delete from public.auditoria$$, 'nem a apaga');
reset role;

-- Nem o dono da base contorna: o gatilho recusa-o.
select t.recusa($$update public.auditoria set acao = 'apagado'$$, 'nem o superutilizador altera');
select t.recusa($$delete from public.auditoria where empresa_id is not null$$, 'nem apaga');
insert into public.auditoria (acao, entidade, entidade_id) values ('sistema', 'instalacao', '-');
select t.recusa($$delete from public.auditoria where empresa_id is null$$, 'nem as linhas sem empresa');
select t.recusa($$truncate public.auditoria$$, 'nem esvazia a tabela');

-- Apagar a empresa leva a sua trilha, e só a sua.
select count(*) as beta_antes from public.auditoria where empresa_id is distinct from :'alfa' \gset
delete from public.empresas where id = :'alfa';
select t.ok((select count(*) from public.auditoria where empresa_id = :'alfa') = 0,
            'apagar a empresa apaga a sua auditoria');
select t.ok((select count(*) from public.auditoria) = :beta_antes,
            'e não toca na das outras');
