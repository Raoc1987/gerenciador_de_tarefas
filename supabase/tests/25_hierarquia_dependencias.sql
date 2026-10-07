-- Subtarefas e dependências (ADR-0023, primeira fatia): mesma empresa, sem
-- ciclos, e as ligações seguem quem vê e quem escreve nas tarefas.

select t.pessoa('dona@h.pt')     as dona     \gset
select t.pessoa('col1@h.pt')     as col1     \gset
select t.pessoa('col2@h.pt')     as col2     \gset
select t.pessoa('leit@h.pt')     as leit     \gset
select t.pessoa('estranho@h.pt') as estranho \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Hera') as hera \gset
insert into public.tarefas (empresa_id, titulo) values (:'hera', 'Projeto') returning id as projeto \gset
insert into public.tarefas (empresa_id, titulo, pai_id) values (:'hera', 'Fase A', :'projeto') returning id as fase_a \gset
insert into public.tarefas (empresa_id, titulo, pai_id) values (:'hera', 'Fase B', :'projeto') returning id as fase_b \gset
insert into public.tarefas (empresa_id, titulo, pai_id) values (:'hera', 'A.1', :'fase_a') returning id as a1 \gset
insert into public.tarefas (empresa_id, titulo) values (:'hera', 'Solta') returning id as solta \gset
reset role;
insert into public.membros values (:'hera', :'col1', 'colaborador'), (:'hera', :'col2', 'colaborador'), (:'hera', :'leit', 'leitor');

select t.sessao(:'estranho'); set role authenticated;
select public.criar_empresa('Outra') as outra \gset
insert into public.tarefas (empresa_id, titulo) values (:'outra', 'Alheia') returning id as alheia \gset
reset role;

-- ------------------------------------------------------------- hierarquia

select t.ok((select pai_id from public.tarefas where id = :'a1') = :'fase_a'::uuid, 'uma subtarefa guarda a mãe');

select t.sessao(:'dona'); set role authenticated;
select t.recusa_por(format($$update public.tarefas set pai_id = %L where id = %L$$, :'a1', :'projeto'),
                    'dentro de si mesma nem de uma subtarefa sua', 'a mãe não pode ficar dentro de uma neta (ciclo)');
select t.recusa_por(format($$update public.tarefas set pai_id = id where id = %L$$, :'solta'),
                    'dentro de si mesma', 'uma tarefa não é mãe de si própria');
select t.recusa_por(format($$insert into public.tarefas (empresa_id, titulo, pai_id) values (%L, 'X', %L)$$, :'hera', :'alheia'),
                    'não existe nesta empresa', 'a mãe não pode ser de outra empresa');
select t.recusa_por(format($$insert into public.tarefas (empresa_id, titulo, pai_id) values (%L, 'X', gen_random_uuid())$$, :'hera'),
                    'não existe nesta empresa', 'mãe inexistente dá a mesma frase que mãe alheia');
update public.tarefas set pai_id = :'fase_b' where id = :'solta';
reset role;
select t.ok((select pai_id from public.tarefas where id = :'solta') = :'fase_b'::uuid, 'mover uma tarefa para dentro de outra é permitido');

-- O colaborador 1 não vê o Projeto (nem é dele nem lhe foi atribuído).
select t.sessao(:'col1'); set role authenticated;
select t.recusa_por(format($$insert into public.tarefas (empresa_id, titulo, pai_id) values (%L, 'Às escondidas', %L)$$, :'hera', :'projeto'),
                    'não existe nesta empresa', 'não se pendura uma subtarefa numa tarefa que não se vê');
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'hera', 'Do col1', auth.uid()) returning id as do_col1 \gset
insert into public.tarefas (empresa_id, titulo, responsavel_id, pai_id) values (:'hera', 'Sub do col1', auth.uid(), :'do_col1') returning id as sub_col1 \gset
reset role;
select t.ok(:'sub_col1' is not null, 'um colaborador cria subtarefas nas suas tarefas');

-- ----------------------------------------------------------- dependências

select t.sessao(:'dona'); set role authenticated;
insert into public.dependencias (antecessora_id, sucessora_id) values (:'fase_a', :'fase_b') returning id as dep_ab \gset
insert into public.dependencias (antecessora_id, sucessora_id, tipo, desfasamento_dias, empresa_id, criada_por)
  values (:'fase_b', :'do_col1', 'inicio_inicio', 2, :'outra', :'estranho') returning id as dep_b_col1 \gset
reset role;
select t.ok((select empresa_id from public.dependencias where id = :'dep_b_col1') = :'hera'::uuid,
            'a empresa da dependência vem das tarefas, não do cliente');
select t.ok((select criada_por from public.dependencias where id = :'dep_b_col1') = :'dona'::uuid,
            'quem criou é quem está em sessão');

select t.sessao(:'dona'); set role authenticated;
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'do_col1', :'fase_a'),
                    'fecharia um ciclo', 'A→B→col1 e col1→A fecha um ciclo');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'fase_b', :'fase_a'),
                    'fecharia um ciclo', 'o ciclo direto também');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'fase_a', :'fase_a'),
                    'não depende de si própria', 'uma tarefa não depende de si própria');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'projeto', :'a1'),
                    'tarefa-mãe nem de uma subtarefa', 'uma neta não depende da avó');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'a1', :'fase_a'),
                    'tarefa-mãe nem de uma subtarefa', 'a mãe não depende da filha');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'alheia', :'fase_a'),
                    'não pode ligar estas tarefas', 'não se liga a uma tarefa de outra empresa');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'fase_a', :'fase_b'),
                    'duplicate key', 'a mesma ligação não se repete');
select t.recusa(format($$insert into public.dependencias (antecessora_id, sucessora_id, desfasamento_dias) values (%L, %L, 400)$$, :'a1', :'solta'),
                'o desfasamento tem limites');
select t.recusa_por(format($$update public.dependencias set tipo = 'fim_fim' where id = %L$$, :'dep_ab'),
                    'permission denied', 'uma ligação não se edita: apaga-se e cria-se outra');
reset role;

-- O colaborador 1 vê a sua tarefa, mas não a Fase B: não vê a ligação.
select t.sessao(:'col1'); set role authenticated;
select t.ok((select count(*) from public.dependencias) = 0, 'só se veem ligações com as duas pontas visíveis');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'fase_a', :'do_col1'),
                    'não pode ligar estas tarefas', 'não se liga a uma tarefa que não se vê');
select t.ok(t.linhas(format($$delete from public.dependencias where id = %L$$, :'dep_b_col1')) = 0,
            'não se apaga uma ligação que não se vê');
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'hera', 'Outra do col1', auth.uid()) returning id as outra_col1 \gset
insert into public.dependencias (antecessora_id, sucessora_id) values (:'do_col1', :'outra_col1') returning id as dep_col1 \gset
reset role;
select t.ok(:'dep_col1' is not null, 'um colaborador liga as suas tarefas');

-- O colaborador 2 não escreve nas tarefas do 1; o leitor vê mas não escreve.
select t.sessao(:'col2'); set role authenticated;
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'do_col1', :'sub_col1'),
                    'não pode ligar estas tarefas', 'não se ligam tarefas alheias, e a recusa não diz nada sobre elas');
reset role;
select t.sessao(:'leit'); set role authenticated;
select t.ok((select count(*) from public.dependencias) = 3, 'quem vê a empresa toda vê todas as ligações');
select t.recusa_por(format($$insert into public.dependencias (antecessora_id, sucessora_id) values (%L, %L)$$, :'a1', :'solta'),
                    'não pode ligar estas tarefas', 'o leitor não cria ligações');
select t.ok(t.linhas(format($$delete from public.dependencias where id = %L$$, :'dep_ab')) = 0, 'o leitor não apaga ligações');
reset role;

set role anon;
select t.recusa($$select * from public.dependencias$$, 'sem sessão não se vê nada');
reset role;

-- ------------------------------------------------- auditoria e apagamentos

select t.ok(exists (select 1 from public.auditoria where entidade = 'dependencias' and acao = 'insert'
                    and entidade_id = :'dep_ab'), 'criar uma ligação fica na auditoria');

select t.sessao(:'dona'); set role authenticated;
delete from public.tarefas where id = :'fase_a';
reset role;
select t.ok(not exists (select 1 from public.tarefas where id = :'a1'), 'apagar a mãe apaga as subtarefas');
select t.ok(not exists (select 1 from public.dependencias where id = :'dep_ab'), 'e as ligações delas');
select t.ok(exists (select 1 from public.tarefas where id = :'fase_b'), 'as irmãs ficam');
