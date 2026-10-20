-- Interruptores de funcionalidade por empresa (20261020010000_interruptores.sql).
-- O que nunca pode acontecer: uma empresa saber alguma coisa de outra.

select t.pessoa('dona.a@int.pt') as dona_a \gset
select t.pessoa('col.a@int.pt')  as col_a  \gset
select t.pessoa('dona.b@int.pt') as dona_b \gset

select t.sessao(:'dona_a'); set role authenticated;
select public.criar_empresa('Empresa A') as a \gset
reset role;
insert into public.membros values (:'a', :'col_a', 'colaborador');
select t.sessao(:'dona_b'); set role authenticated;
select public.criar_empresa('Empresa B') as b \gset
reset role;

-- Uma funcionalidade desligada por omissão, para provar que nada se adivinha.
insert into public.funcionalidades values ('novidade', 'Uma novidade em ensaio', false);

-- Por omissão: o Copiloto ligado, a novidade desligada.
select t.sessao(:'col_a'); set role authenticated;
select t.ok(public.funcionalidade_ligada(:'a', 'copiloto'), 'o copiloto está ligado por omissão');
select t.ok(not public.funcionalidade_ligada(:'a', 'novidade'), 'a novidade está desligada por omissão');
select t.ok(not public.funcionalidade_ligada(:'a', 'nao_existe'), 'uma funcionalidade que não existe está desligada');
select t.ok((select count(*) from public.funcionalidades) >= 2, 'o catálogo lê-se com sessão');
reset role;

-- O operador liga a novidade só para A e desliga o Copiloto só para A.
insert into public.funcionalidades_empresa (empresa_id, funcionalidade, ligada, motivo)
values (:'a', 'novidade', true, 'ensaio com um cliente'), (:'a', 'copiloto', false, 'pedido do cliente');

select t.sessao(:'col_a'); set role authenticated;
select t.ok(public.funcionalidade_ligada(:'a', 'novidade'), 'a novidade passa a ligada em A');
select t.ok(not public.funcionalidade_ligada(:'a', 'copiloto'), 'e o copiloto desligado em A');
select t.ok((select count(*) from public.funcionalidades_empresa) = 2, 'um membro de A vê os interruptores de A');
-- A base recusa a pergunta, com a frase, antes do limite do plano.
select t.recusa_por(format($$insert into public.copiloto_uso (empresa_id) values (%L)$$, :'a'),
                    'o copiloto não está disponível para esta empresa', 'em A a pergunta ao copiloto é recusada');
reset role;

-- B não é afetado, e não sabe nada de A.
select t.sessao(:'dona_b'); set role authenticated;
select t.ok(public.funcionalidade_ligada(:'b', 'copiloto'), 'em B o copiloto continua ligado');
select t.ok(not public.funcionalidade_ligada(:'b', 'novidade'), 'e a novidade continua desligada em B');
insert into public.copiloto_uso (empresa_id) values (:'b');
select t.ok(true, 'em B a pergunta ao copiloto reserva-se');
select t.ok((select count(*) from public.funcionalidades_empresa) = 0, 'B não vê nenhum interruptor de A');
select t.ok((select count(*) from public.funcionalidades_empresa where empresa_id = :'a') = 0,
            'nem pedindo pela empresa A');
select t.ok(not public.funcionalidade_ligada(:'a', 'novidade'),
            'perguntar por A responde desligada, mesmo estando ligada em A');
select t.ok(not public.funcionalidade_ligada(:'a', 'copiloto'), 'e o mesmo para o que A tem desligado');
select t.ok(not public.funcionalidade_ligada(gen_random_uuid(), 'copiloto'),
            'uma empresa que não existe responde igual: não se distingue');
select t.ok((select count(*) from public.auditoria where empresa_id = :'a') = 0, 'B não vê a auditoria de A');
reset role;

-- Ninguém com sessão escreve interruptores, nem a proprietária.
select t.sessao(:'dona_a'); set role authenticated;
select t.recusa_por(format($$insert into public.funcionalidades_empresa (empresa_id, funcionalidade, ligada) values (%L, 'copiloto', true)$$, :'a'),
                    'permission denied', 'a proprietária não liga funcionalidades');
select t.recusa_por($$update public.funcionalidades_empresa set ligada = true$$,
                    'permission denied', 'nem altera interruptores');
select t.recusa_por($$delete from public.funcionalidades_empresa$$,
                    'permission denied', 'nem os apaga');
select t.recusa_por($$insert into public.funcionalidades values ('outra', 'Outra coisa', true)$$,
                    'permission denied', 'nem acrescenta ao catálogo');
select t.recusa_por(format($$select interno.funcionalidade_efetiva(%L, 'copiloto')$$, :'b'),
                    'permission denied', 'nem chama a função interna');
reset role;

-- A mudança fica na auditoria da empresa certa.
select t.ok((select count(*) from public.auditoria
             where empresa_id = :'a' and entidade = 'funcionalidades_empresa') = 2,
            'ligar e desligar fica na auditoria de A');
select t.ok((select count(*) from public.auditoria
             where empresa_id = :'b' and entidade = 'funcionalidades_empresa') = 0,
            'e nada na de B');

-- Religar devolve o Copiloto a A.
update public.funcionalidades_empresa set ligada = true where empresa_id = :'a' and funcionalidade = 'copiloto';
select t.sessao(:'col_a'); set role authenticated;
insert into public.copiloto_uso (empresa_id) values (:'a');
select t.ok(true, 'religado, a pergunta em A reserva-se');
reset role;

set role anon;
select t.recusa($$select public.funcionalidade_ligada(gen_random_uuid(), 'copiloto')$$, 'sem sessão não se pergunta');
select t.recusa($$select * from public.funcionalidades$$, 'sem sessão não se lê o catálogo');
reset role;
