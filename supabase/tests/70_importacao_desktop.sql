-- Importação do desktop: só quem administra, sem duplicados, com as datas
-- de lá, sem emails, e sem abrir a porta a datas inventadas fora dela.

select t.pessoa('dona@a.pt') as dona \gset
select t.pessoa('col@a.pt')  as col  \gset
select t.pessoa('fora@b.pt') as fora \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
update public.empresas set segregacao_funcoes = true where id = :'alfa';
reset role;
insert into public.membros values (:'alfa', :'col', 'colaborador');

\set lote '[{"origem":"desktop:1:2026-01-05T09:00:00","titulo":"Ligar ao fornecedor","prazo":"2026-02-01","estado":"a_fazer","criada_em":"2026-01-05T09:00:00","etiquetas":["importado"]},{"origem":"desktop:2:2026-01-06T10:00:00","titulo":"Fechar o mês","estado":"concluida","criada_em":"2026-01-06T10:00:00","concluida_em":"2026-07-20T17:00:00","responsavel_id":"__COL__"},{"origem":"desktop:3:x","titulo":"   ","estado":"a_fazer"},{"origem":"desktop:4:x","titulo":"Para alguém de fora","responsavel_id":"__FORA__"}]'
select replace(replace(:'lote', '__COL__', :'col'), '__FORA__', :'fora') as lote \gset

select t.sessao(:'col'); set role authenticated;
select t.recusa(format($$select public.importar_tarefas(%L, %L)$$, :'alfa', :'lote'), 'um colaborador não importa');
reset role;
select t.sessao(:'fora'); set role authenticated;
select t.recusa(format($$select public.importar_tarefas(%L, %L)$$, :'alfa', :'lote'), 'quem é de fora não importa');
reset role;

select t.sessao(:'dona'); set role authenticated;
select public.importar_tarefas(:'alfa', :'lote') as r \gset
select t.ok((:'r'::jsonb ->> 'inseridas')::int = 3, 'entram as válidas');
select t.ok((:'r'::jsonb ->> 'recusadas')::int = 1, 'a sem título é recusada sem deitar abaixo o lote');
select t.ok(:'r'::jsonb -> 'motivos' -> 0 ->> 'origem' = 'desktop:3:x', 'e diz qual foi');

select public.importar_tarefas(:'alfa', :'lote') as r2 \gset
select t.ok((:'r2'::jsonb ->> 'inseridas')::int = 0 and (:'r2'::jsonb ->> 'repetidas')::int = 3,
            'importar o mesmo ficheiro outra vez não duplica nada');

select t.ok((select criada_em = '2026-01-05T09:00:00Z'::timestamptz from public.tarefas where titulo = 'Ligar ao fornecedor'),
            'a data de criação é a do desktop: 9h de inverno em Lisboa são 9h UTC');
select t.ok((select concluida_em = '2026-07-20T16:00:00Z'::timestamptz and concluida_por = auth.uid()
             from public.tarefas where titulo = 'Fechar o mês'),
            'a de conclusão também, com hora de verão (17h em Lisboa = 16h UTC), mesmo com segregação');
select t.ok((select criada_por = auth.uid() from public.tarefas where titulo = 'Fechar o mês'),
            'o autor é quem importou');
select t.ok((select responsavel_id = :'col'::uuid from public.tarefas where titulo = 'Fechar o mês'),
            'o responsável mapeado fica');
select t.ok((select responsavel_id is null from public.tarefas where titulo = 'Para alguém de fora'),
            'um responsável que não é da empresa fica vazio, em vez de recusar a tarefa');

-- Fora da importação, as datas continuam a ser as de agora.
insert into public.tarefas (empresa_id, titulo, criada_em) values (:'alfa', 'Normal', '2020-01-01');
select t.ok((select criada_em > now() - interval '1 minute' from public.tarefas where titulo = 'Normal'),
            'fora da importação ninguém escolhe a data de criação');
select t.ok(coalesce(current_setting('gdt.importacao', true), '') = '', 'a importação não deixa o modo ligado');
select t.recusa(format($$select public.importar_tarefas(%L, (select jsonb_agg(x) from generate_series(1, 1001) x))$$, :'alfa'),
                'lotes acima de 1000 são recusados');
select t.recusa(format($$select public.importar_tarefas(%L, '[]', 'Marte/Olympus')$$, :'alfa'),
                'um fuso desconhecido é recusado');
reset role;

select t.ok(not exists (select 1 from public.emails_pendentes where tipo = 'atribuicao'),
            'importar não manda um email por tarefa atribuída');
select t.ok((select count(*) from public.auditoria where entidade = 'tarefas' and acao = 'insert') = 4,
            'cada tarefa importada fica na auditoria');
