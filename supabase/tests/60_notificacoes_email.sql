-- Notificações por email: o que entra na fila, quando não entra, e quem a
-- consegue ler (ninguém em sessão — guarda tokens de convite).

select t.pessoa('dona@a.pt') as dona \gset
select t.pessoa('sup@a.pt')  as sup  \gset
select t.pessoa('col@a.pt')  as col  \gset

select t.sessao(:'dona'); set role authenticated;
select public.criar_empresa('Alfa') as alfa \gset
reset role;
insert into public.membros values (:'alfa', :'sup', 'supervisor'), (:'alfa', :'col', 'colaborador');

-- Atribuir a outra pessoa avisa-a; atribuir a si próprio não.
select t.sessao(:'sup'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id, prazo)
  values (:'alfa', 'Relatório', :'col', current_date - 1) returning id as t1 \gset
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'alfa', 'Minha', :'sup');
update public.tarefas set titulo = 'Relatório mensal' where id = :'t1';
reset role;
select t.ok((select count(*) from public.emails_pendentes where tipo = 'atribuicao') = 1,
            'só a atribuição a outra pessoa gera aviso, e editar o título não gera outro');
select t.ok((select email from public.emails_pendentes where tipo = 'atribuicao') = 'col@a.pt',
            'vai para o email do responsável');
select t.ok((select dados ->> 'empresa' = 'Alfa' and dados ->> 'por' = 'sup'
             from public.emails_pendentes where tipo = 'atribuicao'),
            'diz de que empresa e quem atribuiu');

-- Comentário: avisa o responsável e o autor, nunca quem comentou.
select t.sessao(:'col'); set role authenticated;
insert into public.comentarios (tarefa_id, empresa_id, corpo) values (:'t1', :'alfa', 'Feito em parte');
reset role;
select t.ok((select array_agg(email order by email) from public.emails_pendentes where tipo = 'comentario')
            = array['sup@a.pt'], 'o comentário do responsável avisa só o autor da tarefa');

-- Preferências: quem desliga, não recebe.
select t.sessao(:'col'); set role authenticated;
insert into public.preferencias_notificacao (user_id, atribuicoes) values (auth.uid(), false);
select t.recusa(format($$insert into public.preferencias_notificacao (user_id) values (%L)$$, :'sup'),
                'ninguém muda as preferências de outra pessoa');
reset role;
select t.sessao(:'sup'); set role authenticated;
insert into public.tarefas (empresa_id, titulo, responsavel_id) values (:'alfa', 'Outra', :'col');
reset role;
select t.ok((select count(*) from public.emails_pendentes where tipo = 'atribuicao') = 1,
            'com as atribuições desligadas, não entra aviso novo');

-- Convite: vai para o email convidado, com o token.
select t.sessao(:'dona'); set role authenticated;
insert into public.convites (empresa_id, email, criado_por) values (:'alfa', 'novo@x.pt', auth.uid())
  returning token as token \gset
reset role;
select t.ok((select dados ->> 'token' from public.emails_pendentes where tipo = 'convite') = :'token',
            'o convite segue com a ligação');

-- A fila é invisível a quem está em sessão: tem tokens de convite.
select t.sessao(:'dona'); set role authenticated;
select t.recusa($$select * from public.emails_pendentes$$, 'nem a proprietária lê a fila');
select t.recusa($$select public.reclamar_emails(10)$$, 'nem reclama emails');
select t.recusa($$select public.marcar_email(1, true)$$, 'nem os marca como enviados');
select t.recusa($$select public.enfileirar_email('convite', null, null, 'x@y.pt', '{}', 'k')$$,
                'nem põe emails na fila à mão');
select t.recusa($$select public.enfileirar_resumos()$$, 'nem dispara os resumos');
reset role;
set role anon;
select t.recusa($$select public.reclamar_emails(10)$$, 'anónimo também não');
reset role;

-- Resumo diário: uma vez por dia, só a quem tem atrasadas ou a vencer hoje.
set role service_role;
select t.ok(public.enfileirar_resumos() = 1, 'um resumo para quem tem tarefas atrasadas');
select t.ok(public.enfileirar_resumos() = 0, 'correr outra vez no mesmo dia não manda outro');
select t.ok((select (dados ->> 'atrasadas')::int from public.emails_pendentes where tipo = 'resumo') = 1,
            'o resumo conta as atrasadas');
reset role;

-- Entrega: reclamar não dá o mesmo email duas vezes; falhas contam e param às 5.
set role service_role;
select count(*) as lote1 from public.reclamar_emails(2) \gset
select count(*) as lote2 from public.reclamar_emails(50) \gset
select t.ok(:lote1 = 2 and :lote2 = 2, 'dois lotes seguidos não repetem emails');
select t.ok((select count(*) from public.reclamar_emails(50)) = 0, 'o que está reclamado não volta logo');
select min(id) as primeiro from public.emails_pendentes \gset
select public.marcar_email(:primeiro, true);
select t.ok((select enviado_em is not null from public.emails_pendentes where id = :primeiro), 'enviado fica marcado');
select max(id) as ultimo from public.emails_pendentes \gset
select public.marcar_email(:ultimo, false, 'Resend 500') from generate_series(1, 5);
select t.ok((select tentativas = 5 and erro = 'Resend 500' from public.emails_pendentes where id = :ultimo),
            'cada falha conta e guarda o erro');
reset role;
update public.emails_pendentes set reclamado_em = now() - interval '11 minutes';
set role service_role;
select t.ok(not exists (select 1 from public.reclamar_emails(50) r where r.id in (:primeiro, :ultimo)),
            'enviados e esgotados não voltam; os esquecidos voltam ao fim de 10 minutos');
reset role;
