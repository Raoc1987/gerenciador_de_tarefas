-- RGPD: exportar os dados de uma pessoa e apagar a sua conta.

select t.pessoa('dona@r.pt')   as dona  \gset
select t.pessoa('gest@r.pt')   as gest  \gset
select t.pessoa('colab@r.pt')  as colab \gset
select t.pessoa('solo@r.pt')   as solo  \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Rio') as rio \gset
reset role;
insert into public.membros values (:'rio', :'gest', 'gestor'), (:'rio', :'colab', 'colaborador');

-- O colaborador cria uma tarefa, comenta, e conclui outra que lhe deram.
select t.sessao(:'colab'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'rio', 'Do colaborador', :'colab') returning id as t_colab \gset
insert into public.comentarios (tarefa_id, empresa_id, corpo) values (:'t_colab', :'rio', 'Comentário do colaborador');
reset role;
select t.sessao(:'gest'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'rio', 'Do gestor para o colaborador', :'colab') returning id as t_gest \gset
insert into public.tarefas (empresa_id, titulo) values (:'rio', 'Só do gestor');
reset role;
select t.sessao(:'colab'); set role authenticated;
update public.tarefas set estado = 'concluida' where id = :'t_gest';
reset role;

-- ------------------------------------------------------------ exportar

set role anon;
select t.recusa($$select public.exportar_os_meus_dados()$$, 'sem sessão não se exporta nada');
reset role;

select t.sessao(:'colab'); set role authenticated;
select public.exportar_os_meus_dados() as dados \gset
reset role;
select t.ok((:'dados'::jsonb -> 'conta' ->> 'email') = 'colab@r.pt', 'a exportação traz a conta de quem pede');
select t.ok(jsonb_array_length(:'dados'::jsonb -> 'tarefas') = 2, 'traz as tarefas que criou e as que lhe atribuíram');
select t.ok(not (:'dados'::jsonb -> 'tarefas')::text like '%Só do gestor%', 'não traz tarefas de outras pessoas');
select t.ok((:'dados'::jsonb -> 'comentarios' -> 0 ->> 'corpo') = 'Comentário do colaborador', 'traz os comentários');
select t.ok((:'dados'::jsonb -> 'empresas' -> 0 ->> 'papel') = 'colaborador', 'traz as empresas e o papel em cada uma');
select t.ok(not (:'dados'::jsonb)::text like '%gest@r.pt%', 'não traz o email de mais ninguém');

-- -------------------------------------------------------------- apagar

select t.sessao(:'colab'); set role authenticated;
select t.recusa_por($$select public.apagar_a_minha_conta('outro@r.pt')$$, 'escreva o email da sua conta',
                    'apagar exige confirmar com o próprio email');
reset role;

select t.sessao(:'dona'); set role authenticated;
select t.recusa_por($$select public.apagar_a_minha_conta('dona@r.pt')$$, 'única pessoa proprietária de uma empresa com mais gente',
                    'a única proprietária de uma empresa com pessoas não apaga a conta sem passar a propriedade');
reset role;

select t.sessao(:'colab'); set role authenticated;
select public.apagar_a_minha_conta('COLAB@r.pt');
reset role;

select t.ok(not exists (select 1 from auth.users where id = :'colab'), 'a conta desaparece');
select t.ok(not exists (select 1 from public.perfis where id = :'colab'), 'o perfil desaparece');
select t.ok(not exists (select 1 from public.membros where user_id = :'colab'), 'as pertenças desaparecem');
select t.ok((select criada_por is null and responsavel_id is null from public.tarefas where id = :'t_colab'),
            'a tarefa que criou fica, sem autor nem responsável');
select t.ok((select concluida_por is null and estado = 'concluida' from public.tarefas where id = :'t_gest'),
            'a tarefa que concluiu continua concluída, sem quem a concluiu');
select t.ok((select autor_id is null from public.comentarios where tarefa_id = :'t_colab'),
            'o comentário fica, sem autor');
select t.ok(exists (select 1 from public.auditoria where actor_id = :'colab'),
            'a auditoria fica como estava (é imutável)');

-- A empresa continua a trabalhar nas tarefas que eram do colaborador.
select t.sessao(:'gest'); set role authenticated;
select t.ok(t.linhas(format($$update public.tarefas set titulo = 'Retomada' where id = %L$$, :'t_colab')) = 1,
            'quem supervisiona continua a editar as tarefas sem autor');
reset role;

-- Quem está sozinho numa empresa apaga a conta e a empresa vai com ela.
select t.sessao(:'solo'); set role authenticated;
select public.criar_empresa('Sozinha') as sozinha \gset
insert into public.tarefas (empresa_id, titulo) values (:'sozinha', 'Minha');
select public.apagar_a_minha_conta('solo@r.pt');
reset role;
select t.ok(not exists (select 1 from public.empresas where id = :'sozinha'), 'a empresa de uma só pessoa apaga-se com a conta');

-- O modo de anonimizar não se forja: nem pela variável de sessão antiga,
-- nem chamando a função interna, nem escrevendo na tabela dos modos.
select t.sessao(:'gest'); set role authenticated;
select t.recusa_por($$select set_config('gdt.anonimizar', 'on', false); update public.tarefas set criada_por = auth.uid() where titulo = 'Retomada'$$,
                    'o autor de uma tarefa não mud', 'ligar a variável antiga à mão não deixa mudar o autor');
select t.recusa_por($$select interno.ligar('anonimizar')$$, 'permission denied', 'ninguém em sessão liga um modo interno');
select t.recusa_por($$insert into interno.modos (modo) values ('anonimizar')$$, 'permission denied', 'nem escreve na tabela dos modos');
reset role;
select t.ok(not exists (select 1 from interno.modos), 'apagar a conta não deixa o modo ligado');
