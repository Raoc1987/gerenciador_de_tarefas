-- Uso do Copiloto: cada um regista o seu, ninguém forja o de outro, e só
-- quem administra vê o da empresa.

select t.pessoa('dona@a.pt') as dona \gset
select t.pessoa('col@a.pt')  as col  \gset
select t.pessoa('fora@b.pt') as fora \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
reset role;
insert into public.membros values (:'alfa', :'col', 'colaborador');

select t.sessao(:'col'); set role authenticated;
insert into public.copiloto_uso (empresa_id, user_id, tokens_entrada, tokens_saida, em)
  values (:'alfa', :'dona', 100, 50, now() - interval '3 days');
select t.ok((select user_id from public.copiloto_uso) = :'col'::uuid,
            'o uso fica em nome de quem pergunta, não de quem o cliente diz');
select t.ok((select em::date from public.copiloto_uso) = current_date,
            'e com a hora do servidor');
select t.ok(public.copiloto_perguntas_hoje() = 1, 'conta as perguntas de hoje');
select t.recusa($$update public.copiloto_uso set tokens_saida = 0$$, 'ninguém reescreve o seu consumo');
select t.recusa($$delete from public.copiloto_uso$$, 'nem o apaga');
reset role;

select t.sessao(:'fora'); set role authenticated;
select t.recusa(format($$insert into public.copiloto_uso (empresa_id) values (%L)$$, :'alfa'),
                'quem é de fora não regista uso na empresa');
select t.ok((select count(*) from public.copiloto_uso) = 0, 'nem o vê');
reset role;

select t.sessao(:'dona'); set role authenticated;
insert into public.copiloto_uso (empresa_id, tokens_entrada, tokens_saida) values (:'alfa', 10, 5);
select t.ok((select count(*) from public.copiloto_uso) = 2, 'a proprietária vê o uso da empresa');
select t.ok(public.copiloto_perguntas_hoje() = 1, 'mas o limite diário é de cada um');
reset role;

select t.sessao(:'col'); set role authenticated;
select t.ok((select count(*) from public.copiloto_uso) = 1, 'o colaborador só vê o seu');
reset role;
