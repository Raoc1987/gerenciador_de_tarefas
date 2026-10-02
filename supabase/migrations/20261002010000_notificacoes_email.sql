-- Notificações por email.
--
-- Quem decide o que se envia é a base: gatilhos põem os emails numa fila no
-- mesmo momento em que acontece aquilo de que avisam (uma atribuição, um
-- comentário, um convite), e respeitam as preferências de cada pessoa. A
-- aplicação só entrega o que está na fila (ADR-0019).
--
-- A fila guarda tokens de convite, que são credenciais: nenhuma pessoa em
-- sessão a lê. Só o papel de serviço, e só por duas funções.

create table public.preferencias_notificacao (
  user_id        uuid primary key references auth.users (id) on delete cascade,
  atribuicoes    boolean not null default true,
  comentarios    boolean not null default true,
  resumo_diario  boolean not null default true,
  atualizado_em  timestamptz not null default now()
);

alter table public.preferencias_notificacao enable row level security;
create policy preferencias_proprias on public.preferencias_notificacao for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke all on public.preferencias_notificacao from anon;

-- Sem linha, vale o que está por omissão (tudo ligado).
create function public.quer_email(p_user uuid, p_tipo text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((
    select case p_tipo
      when 'atribuicao' then atribuicoes
      when 'comentario' then comentarios
      when 'resumo' then resumo_diario
      else true end
    from public.preferencias_notificacao where user_id = p_user
  ), true)
$$;
revoke execute on function public.quer_email(uuid, text) from public, anon, authenticated;

create table public.emails_pendentes (
  id            bigint generated always as identity primary key,
  tipo          text not null check (tipo in ('atribuicao', 'comentario', 'convite', 'resumo')),
  empresa_id    uuid references public.empresas (id) on delete cascade,
  user_id       uuid references auth.users (id) on delete cascade,
  email         text not null,
  dados         jsonb not null default '{}',
  -- Evita repetidos: o mesmo aviso, para a mesma pessoa, uma vez só.
  chave         text not null unique,
  criado_em     timestamptz not null default now(),
  reclamado_em  timestamptz,
  tentativas    integer not null default 0,
  enviado_em    timestamptz,
  erro          text
);

create index emails_por_enviar on public.emails_pendentes (id)
  where enviado_em is null and tentativas < 5;

alter table public.emails_pendentes enable row level security;
-- Nenhuma policy: nenhuma pessoa em sessão lê ou escreve a fila.
revoke all on public.emails_pendentes from anon, authenticated;

create function public.enfileirar_email(
  p_tipo text, p_empresa uuid, p_user uuid, p_email text, p_dados jsonb, p_chave text
) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(p_email, '') = '' then return; end if;
  if p_user is not null and p_tipo <> 'convite' and not public.quer_email(p_user, p_tipo) then
    return;
  end if;
  insert into public.emails_pendentes (tipo, empresa_id, user_id, email, dados, chave)
  values (p_tipo, p_empresa, p_user, p_email, p_dados, p_chave)
  on conflict (chave) do nothing;
end $$;
revoke execute on function public.enfileirar_email(text, uuid, uuid, text, jsonb, text)
  from public, anon, authenticated;

-- ------------------------------------------------------------------ gatilhos

create function public.avisar_atribuicao() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_email text;
begin
  if new.responsavel_id is null
     or new.responsavel_id = auth.uid()   -- quem se atribui a si próprio não precisa de aviso
     or (tg_op = 'UPDATE' and new.responsavel_id is not distinct from old.responsavel_id) then
    return new;
  end if;
  select email into v_email from auth.users where id = new.responsavel_id;
  perform public.enfileirar_email(
    'atribuicao', new.empresa_id, new.responsavel_id, v_email,
    jsonb_build_object(
      'tarefa_id', new.id, 'titulo', new.titulo, 'prazo', new.prazo,
      'prioridade', new.prioridade,
      'empresa', (select nome from public.empresas where id = new.empresa_id),
      'por', (select nome from public.perfis where id = auth.uid())
    ),
    format('atribuicao:%s:%s:%s', new.id, new.responsavel_id, extract(epoch from clock_timestamp()))
  );
  return new;
end $$;

create trigger avisar_atribuicao after insert or update of responsavel_id on public.tarefas
  for each row execute function public.avisar_atribuicao();

create function public.avisar_comentario() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_tarefa public.tarefas;
  v_dest uuid;
begin
  select * into v_tarefa from public.tarefas where id = new.tarefa_id;
  -- Avisa o responsável e o autor da tarefa, nunca quem comentou.
  for v_dest in
    select distinct u from unnest(array[v_tarefa.responsavel_id, v_tarefa.criada_por]) as u
    where u is not null and u <> new.autor_id
  loop
    perform public.enfileirar_email(
      'comentario', new.empresa_id, v_dest, (select email from auth.users where id = v_dest),
      jsonb_build_object(
        'tarefa_id', v_tarefa.id, 'titulo', v_tarefa.titulo, 'corpo', left(new.corpo, 500),
        'empresa', (select nome from public.empresas where id = new.empresa_id),
        'por', (select nome from public.perfis where id = new.autor_id)
      ),
      format('comentario:%s:%s', new.id, v_dest)
    );
  end loop;
  return new;
end $$;

create trigger avisar_comentario after insert on public.comentarios
  for each row execute function public.avisar_comentario();

create function public.avisar_convite() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform public.enfileirar_email(
    'convite', new.empresa_id, null, new.email,
    jsonb_build_object(
      'token', new.token, 'papel', new.papel, 'expira_em', new.expira_em,
      'empresa', (select nome from public.empresas where id = new.empresa_id),
      'por', (select nome from public.perfis where id = new.criado_por)
    ),
    format('convite:%s', new.id)
  );
  return new;
end $$;

create trigger avisar_convite after insert on public.convites
  for each row execute function public.avisar_convite();

revoke execute on function public.avisar_atribuicao() from public, anon, authenticated;
revoke execute on function public.avisar_comentario() from public, anon, authenticated;
revoke execute on function public.avisar_convite() from public, anon, authenticated;

-- ------------------------------------------------------------------ resumo diário
--
-- Uma vez por dia, a cada pessoa com tarefas atrasadas ou a vencer hoje,
-- por empresa. A chave inclui o dia: correr duas vezes não manda dois.

create function public.enfileirar_resumos(p_hoje date default current_date) returns integer
language plpgsql security definer set search_path = '' as $$
declare
  v_antes integer;
  v_depois integer;
begin
  select count(*) into v_antes from public.emails_pendentes where tipo = 'resumo';
  perform public.enfileirar_email(
    'resumo', r.empresa_id, r.user_id, u.email,
    jsonb_build_object(
      'empresa', e.nome, 'dia', p_hoje, 'atrasadas', r.atrasadas, 'hoje', r.hoje,
      'tarefas', r.tarefas
    ),
    format('resumo:%s:%s:%s', r.empresa_id, r.user_id, p_hoje)
  )
  from (
    select t.empresa_id, t.responsavel_id as user_id,
           count(*) filter (where t.prazo < p_hoje) as atrasadas,
           count(*) filter (where t.prazo = p_hoje) as hoje,
           jsonb_agg(jsonb_build_object('id', t.id, 'titulo', t.titulo, 'prazo', t.prazo)
                     order by t.prazo, t.titulo) as tarefas
    from public.tarefas t
    join public.membros m on m.empresa_id = t.empresa_id and m.user_id = t.responsavel_id
    where t.estado <> 'concluida' and t.prazo <= p_hoje
    group by t.empresa_id, t.responsavel_id
  ) r
  join public.empresas e on e.id = r.empresa_id
  join auth.users u on u.id = r.user_id;
  select count(*) into v_depois from public.emails_pendentes where tipo = 'resumo';
  return v_depois - v_antes;
end $$;

-- ------------------------------------------------------------------ entrega
--
-- O carteiro (web/app/api/cron/emails) reclama um lote, envia, e marca cada
-- um. `skip locked` deixa correr dois carteiros ao mesmo tempo sem enviarem
-- o mesmo email; um lote reclamado e não marcado volta à fila em 10 minutos.

create function public.reclamar_emails(p_limite integer default 50)
returns setof public.emails_pendentes
language sql security definer set search_path = '' as $$
  update public.emails_pendentes e set reclamado_em = now()
  where e.id in (
    select id from public.emails_pendentes
    where enviado_em is null and tentativas < 5
      and (reclamado_em is null or reclamado_em < now() - interval '10 minutes')
    order by id
    limit least(greatest(p_limite, 1), 200)
    for update skip locked
  )
  returning e.*
$$;

create function public.marcar_email(p_id bigint, p_ok boolean, p_erro text default null)
returns void
language sql security definer set search_path = '' as $$
  update public.emails_pendentes set
    enviado_em   = case when p_ok then now() end,
    tentativas   = tentativas + case when p_ok then 0 else 1 end,
    erro         = case when p_ok then null else left(p_erro, 500) end,
    reclamado_em = null
  where id = p_id and enviado_em is null
$$;

revoke execute on function public.enfileirar_resumos(date) from public, anon, authenticated;
revoke execute on function public.reclamar_emails(integer) from public, anon, authenticated;
revoke execute on function public.marcar_email(bigint, boolean, text) from public, anon, authenticated;
grant execute on function public.enfileirar_resumos(date) to service_role;
grant execute on function public.reclamar_emails(integer) to service_role;
grant execute on function public.marcar_email(bigint, boolean, text) to service_role;
