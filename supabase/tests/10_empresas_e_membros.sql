-- Empresas, membros e convites: quem entra, quem manda em quem, e o
-- isolamento entre empresas.

select t.pessoa('ana@a.pt')   as ana   \gset
select t.pessoa('bruno@a.pt') as bruno \gset
select t.pessoa('carla@b.pt') as carla \gset
select t.pessoa('duarte@a.pt') as duarte \gset

select t.ok((select count(*) from public.perfis) = 4, 'cada conta nova ganha um perfil');
select t.ok((select nome from public.perfis where id = :'ana') = 'ana', 'o nome por omissão vem do email');

-- Sem sessão não se cria nada.
set role anon;
select t.recusa($$select public.criar_empresa('Fantasma')$$, 'anónimo não cria empresas');
reset role;

-- Ana cria a Alfa e fica proprietária.
select t.sessao(:'ana'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
select t.ok(public.papel_em(:'alfa') = 'proprietario', 'quem cria a empresa é proprietário');
select t.recusa($$insert into public.empresas (nome, criada_por) values ('Direta', auth.uid())$$,
                'empresas só se criam pela função');
select t.recusa(format($$insert into public.membros values (%L, %L, 'proprietario')$$, :'alfa', :'bruno'),
                'não se escreve em membros diretamente');
reset role;

-- Carla cria a Beta.
select t.sessao(:'carla'); set role authenticated;
select public.criar_empresa('Beta') as beta \gset
select t.ok((select count(*) from public.empresas) = 1, 'Carla só vê a sua empresa');
select t.ok((select count(*) from public.perfis) = 1, 'Carla só vê o seu perfil');
select t.ok(t.linhas(format($$update public.empresas set nome = 'Tomada' where id = %L$$, :'alfa')) = 0,
            'Carla não mexe na empresa de outros');
reset role;

-- Ana convida o Bruno como colaborador.
select t.sessao(:'ana'); set role authenticated;
insert into public.convites (empresa_id, email, papel, criado_por)
  values (:'alfa', 'bruno@a.pt', 'colaborador', auth.uid())
  returning token as token_bruno \gset
insert into public.convites (empresa_id, email, papel, criado_por)
  values (:'alfa', 'duarte@a.pt', 'administrador', auth.uid())
  returning token as token_duarte \gset
reset role;

-- A Carla não vê os convites da Alfa, nem consegue usar o do Bruno.
select t.sessao(:'carla'); set role authenticated;
select t.ok((select count(*) from public.convites) = 0, 'convites de outra empresa são invisíveis');
select t.recusa(format($$select public.aceitar_convite(%L)$$, :'token_bruno'),
                'um convite não se aceita com a conta de outra pessoa');
reset role;

select t.sessao(:'bruno'); set role authenticated;
select t.ok(public.aceitar_convite(:'token_bruno') = :'alfa'::uuid, 'Bruno aceita o seu convite');
select t.ok(public.papel_em(:'alfa') = 'colaborador', 'e entra com o papel do convite');
select t.recusa(format($$select public.aceitar_convite(%L)$$, :'token_bruno'), 'um convite só se usa uma vez');
select t.ok((select count(*) from public.perfis) = 2, 'Bruno vê o perfil de quem partilha a empresa');
select t.ok((select count(*) from public.convites) = 0, 'um colaborador não vê convites');
select t.recusa(format($$insert into public.convites (empresa_id, email, criado_por) values (%L, 'x@y.pt', auth.uid())$$, :'alfa'),
                'um colaborador não convida');
select t.recusa(format($$select public.alterar_papel(%L, %L, 'administrador')$$, :'alfa', :'bruno'),
                'ninguém se promove a si próprio');
select t.ok(t.linhas(format($$update public.empresas set segregacao_funcoes = true where id = %L$$, :'alfa')) = 0,
            'um colaborador não muda as definições');
reset role;

select t.sessao(:'duarte'); set role authenticated;
select public.aceitar_convite(:'token_duarte');
select t.ok(public.papel_em(:'alfa') = 'administrador', 'Duarte entra como administrador');
-- Um administrador gere os de baixo, não os do seu nível nem o proprietário.
select public.alterar_papel(:'alfa', :'bruno', 'supervisor');
select t.ok((select papel from public.membros where user_id = :'bruno') = 'supervisor',
            'um administrador promove um colaborador a supervisor');
select t.recusa(format($$select public.alterar_papel(%L, %L, 'administrador')$$, :'alfa', :'bruno'),
                'só o proprietário cria administradores');
select t.recusa(format($$select public.remover_membro(%L, %L)$$, :'alfa', :'ana'),
                'um administrador não remove o proprietário');
select t.recusa(format($$select public.alterar_papel(%L, %L, 'leitor')$$, :'alfa', :'ana'),
                'um administrador não despromove o proprietário');
select t.recusa(format($$insert into public.convites (empresa_id, email, papel, criado_por) values (%L, 'z@a.pt', 'administrador', auth.uid())$$, :'alfa'),
                'um administrador não convida administradores');
select t.ok(t.linhas(format($$update public.empresas set segregacao_funcoes = true where id = %L$$, :'alfa')) = 1,
            'um administrador muda as definições');
select t.recusa(format($$update public.empresas set criada_por = auth.uid() where id = %L$$, :'alfa'),
                'o autor da empresa não se reescreve');
reset role;

select t.sessao(:'ana'); set role authenticated;
select t.recusa(format($$select public.remover_membro(%L, %L)$$, :'alfa', :'ana'),
                'o último proprietário não sai');
select t.recusa(format($$select public.alterar_papel(%L, %L, 'gestor')$$, :'alfa', :'ana'),
                'o último proprietário não se despromove');
select public.alterar_papel(:'alfa', :'duarte', 'proprietario');
select public.alterar_papel(:'alfa', :'ana', 'administrador');
select t.ok(public.papel_em(:'alfa') = 'administrador', 'havendo outro proprietário, pode passar o testemunho');
reset role;

select t.sessao(:'bruno'); set role authenticated;
select public.remover_membro(:'alfa', :'bruno');
select t.ok(not public.e_membro(:'alfa'), 'qualquer um pode sair de uma empresa');
select t.ok((select count(*) from public.empresas) = 0, 'e deixa de a ver');
reset role;

-- Apagar a empresa: só o proprietário, e leva tudo consigo — tarefas,
-- membros e a própria auditoria — sem tocar nas outras.
select t.sessao(:'carla'); set role authenticated;
insert into public.tarefas (empresa_id, titulo) values (:'beta', 'Da Beta');
reset role;
select t.sessao(:'duarte'); set role authenticated;
select t.ok(t.linhas(format($$delete from public.empresas where id = %L$$, :'beta')) = 0,
            'quem não é membro não apaga a empresa');
select t.ok(t.linhas(format($$delete from public.empresas where id = %L$$, :'alfa')) = 1,
            'o proprietário apaga a sua');
reset role;
select t.sessao(:'carla'); set role authenticated;
select t.ok(t.linhas(format($$delete from public.empresas where id = %L$$, :'beta')) = 1,
            'a Carla apaga a Beta, com tarefas e auditoria');
reset role;
select t.ok((select count(*) from public.empresas) = 0
            and (select count(*) from public.tarefas) = 0
            and (select count(*) from public.membros) = 0
            and (select count(*) from public.auditoria) = 0,
            'não sobra nada de nenhuma das duas');
