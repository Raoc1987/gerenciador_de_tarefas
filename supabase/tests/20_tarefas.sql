-- Tarefas: quem vê, quem escreve, quem atribui, quem apaga, e a segregação
-- de funções. É a regra do desktop (TAREFAS_VER_TODAS), agora na base.

select t.pessoa('dona@a.pt')  as dona  \gset
select t.pessoa('sup@a.pt')   as sup   \gset
select t.pessoa('col1@a.pt')  as col1  \gset
select t.pessoa('col2@a.pt')  as col2  \gset
select t.pessoa('leit@a.pt')  as leit  \gset
select t.pessoa('estranho@b.pt') as estranho \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
reset role;
-- Montar a equipa diretamente (como postgres) — os convites já têm testes.
insert into public.membros values
  (:'alfa', :'sup', 'supervisor'), (:'alfa', :'col1', 'colaborador'),
  (:'alfa', :'col2', 'colaborador'), (:'alfa', :'leit', 'leitor');

select t.sessao(:'estranho'); set role authenticated;
select public.criar_empresa('Beta') as beta \gset
insert into public.tarefas (empresa_id, titulo) values (:'beta', 'Segredo da Beta');
reset role;

-- O colaborador 1 cria uma para si e uma sem responsável.
select t.sessao(:'col1'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'alfa', 'Minha', auth.uid())
  returning id as t_col1 \gset
insert into public.tarefas (empresa_id, titulo) values (:'alfa', 'Sem dono')
  returning id as t_solta \gset
select t.recusa(format($$insert into public.tarefas (empresa_id, titulo, responsavel_id) values (%L, 'Para o col2', %L)$$, :'alfa', :'col2'),
                'um colaborador não atribui tarefas a outros');
select t.recusa(format($$insert into public.tarefas (empresa_id, titulo) values (%L, 'Intrusa')$$, :'beta'),
                'ninguém cria tarefas numa empresa que não é a sua');
insert into public.tarefas (empresa_id, titulo, criada_por) values (:'alfa', 'Forjada', :'col2');
reset role;
select t.ok((select criada_por from public.tarefas where titulo = 'Forjada') = :'col1'::uuid,
            'o autor é quem está em sessão, não o que o cliente diz');
delete from public.tarefas where titulo = 'Forjada';
select t.ok((select criada_por from public.tarefas where id = :'t_solta') = :'col1'::uuid, 'o autor fica carimbado');

-- O supervisor atribui ao colaborador 2.
select t.sessao(:'sup'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id, prazo)
  values (:'alfa', 'Para o col2', :'col2', current_date - 2)
  returning id as t_col2 \gset
select t.recusa(format($$insert into public.tarefas (empresa_id, titulo, responsavel_id) values (%L, 'Para fora', %L)$$, :'alfa', :'estranho'),
                'o responsável tem de ser da empresa');
select t.ok((select count(*) from public.tarefas) = 3, 'o supervisor vê todas as da empresa, e só essas');
reset role;

select t.sessao(:'col2'); set role authenticated;
select t.ok((select count(*) from public.tarefas) = 1, 'o colaborador 2 vê só a sua');
select t.ok(t.linhas(format($$update public.tarefas set titulo = 'mexida' where id = %L$$, :'t_col1')) = 0,
            'e não mexe nas dos outros');
select t.ok(t.linhas(format($$update public.tarefas set estado = 'em_curso' where id = %L$$, :'t_col2')) = 1,
            'mexe na que lhe foi atribuída');
select t.recusa(format($$update public.tarefas set responsavel_id = %L where id = %L$$, :'col1', :'t_col2'),
                'mas não a passa a outra pessoa');
select t.recusa(format($$update public.tarefas set responsavel_id = null where id = %L$$, :'t_col2'),
                'nem a larga: deixaria de a ver, e devolvê-la é com quem a atribuiu');
select t.recusa(format($$update public.tarefas set empresa_id = %L where id = %L$$, :'beta', :'t_col2'),
                'uma tarefa não muda de empresa');
select t.ok(t.linhas(format($$delete from public.tarefas where id = %L$$, :'t_col2')) = 0,
            'um colaborador não apaga');
reset role;

select t.sessao(:'leit'); set role authenticated;
select t.ok((select count(*) from public.tarefas) = 3, 'o leitor vê todas');
select t.recusa(format($$insert into public.tarefas (empresa_id, titulo) values (%L, 'Do leitor')$$, :'alfa'),
                'o leitor não cria');
select t.ok(t.linhas(format($$update public.tarefas set titulo = 'x' where id = %L$$, :'t_col1')) = 0,
            'o leitor não edita');
reset role;

select t.sessao(:'estranho'); set role authenticated;
select t.ok((select count(*) from public.tarefas) = 1, 'outra empresa não vê nenhuma tarefa da Alfa');
reset role;

-- Concluir carimba quem e quando; reabrir limpa.
select t.sessao(:'col1'); set role authenticated;
update public.tarefas set estado = 'concluida', concluida_por = :'dona' where id = :'t_col1';
select t.ok((select concluida_por from public.tarefas where id = :'t_col1') = :'col1'::uuid
            and (select concluida_em from public.tarefas where id = :'t_col1') is not null,
            'concluir carimba quem concluiu, não o que o cliente diz');
update public.tarefas set estado = 'a_fazer' where id = :'t_col1';
select t.ok((select concluida_em from public.tarefas where id = :'t_col1') is null, 'reabrir limpa o carimbo');
reset role;

-- Segregação de funções.
update public.empresas set segregacao_funcoes = true where id = :'alfa';
select t.sessao(:'col1'); set role authenticated;
select t.recusa(format($$update public.tarefas set estado = 'concluida' where id = %L$$, :'t_col1'),
                'com segregação, quem criou não conclui');
reset role;
select t.sessao(:'dona'); set role authenticated;
insert into public.tarefas (empresa_id, titulo) values (:'alfa', 'Da dona') returning id as t_dona \gset
select t.recusa(format($$update public.tarefas set estado = 'concluida' where id = %L$$, :'t_dona'),
                'nem a proprietária');
select t.ok(t.linhas(format($$update public.tarefas set estado = 'concluida' where id = %L$$, :'t_col1')) = 1,
            'outra pessoa conclui');
reset role;

-- Comentários.
select t.sessao(:'col2'); set role authenticated;
insert into public.comentarios (tarefa_id, empresa_id, corpo) values (:'t_col2', :'beta', 'Olá')
  returning empresa_id as emp_coment \gset
select t.ok(:'emp_coment'::uuid = :'alfa'::uuid, 'a empresa de um comentário vem da tarefa, não do cliente');
select t.recusa(format($$insert into public.comentarios (tarefa_id, empresa_id, corpo) values (%L, %L, 'espreita')$$, :'t_col1', :'alfa'),
                'não se comenta uma tarefa que não se vê');
reset role;
select t.sessao(:'leit'); set role authenticated;
select t.ok((select count(*) from public.comentarios) = 1, 'quem vê a tarefa vê os comentários');
select t.recusa(format($$insert into public.comentarios (tarefa_id, empresa_id, corpo) values (%L, %L, 'opinião')$$, :'t_col2', :'alfa'),
                'o leitor não comenta');
reset role;
select t.sessao(:'estranho'); set role authenticated;
select t.ok((select count(*) from public.comentarios) = 0, 'outra empresa não vê comentários da Alfa');
reset role;

-- O gestor apaga.
insert into public.membros values (:'alfa', :'estranho', 'gestor');
select t.sessao(:'estranho'); set role authenticated;
select t.ok(t.linhas(format($$delete from public.tarefas where id = %L$$, :'t_solta')) = 1, 'um gestor apaga');
reset role;
