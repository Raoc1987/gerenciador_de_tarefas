-- Tarefas, comentários, auditoria e indicadores do painel.
--
-- Quem vê o quê é a regra do desktop (tarefas_servico.py, TAREFAS_VER_TODAS):
-- um colaborador vê as suas — as que lhe estão atribuídas ou que criou —, e
-- quem tem visão de conjunto vê as de toda a empresa. Aqui é a RLS a dizê-lo,
-- e os indicadores do painel herdam-no por serem `security invoker`: um
-- colaborador vê os números das suas tarefas, não os da empresa.

create type public.estado_tarefa as enum ('a_fazer', 'em_curso', 'em_revisao', 'concluida');
create type public.prioridade as enum ('baixa', 'media', 'alta', 'urgente');

create table public.tarefas (
  id              uuid primary key default gen_random_uuid(),
  empresa_id      uuid not null references public.empresas (id) on delete cascade,
  titulo          text not null check (length(btrim(titulo)) between 1 and 200),
  descricao       text not null default '' check (length(descricao) <= 10000),
  estado          public.estado_tarefa not null default 'a_fazer',
  prioridade      public.prioridade not null default 'media',
  prazo           date,
  etiquetas       text[] not null default '{}'
                  check (cardinality(etiquetas) <= 10),
  responsavel_id  uuid references auth.users (id) on delete set null,
  -- Ordem dentro da coluna do quadro. Fracionária: mover um cartão escreve
  -- uma linha, não renumera a coluna inteira.
  posicao         double precision not null default extract(epoch from clock_timestamp()),
  criada_por      uuid not null default auth.uid() references auth.users (id),
  criada_em       timestamptz not null default now(),
  atualizada_em   timestamptz not null default now(),
  concluida_por   uuid references auth.users (id),
  concluida_em    timestamptz
);

create index tarefas_empresa_estado on public.tarefas (empresa_id, estado, posicao);
create index tarefas_responsavel on public.tarefas (responsavel_id) where responsavel_id is not null;
create index tarefas_prazo on public.tarefas (empresa_id, prazo) where estado <> 'concluida';
create index tarefas_pesquisa on public.tarefas
  using gin (to_tsvector('portuguese', titulo || ' ' || descricao));

create table public.comentarios (
  id          uuid primary key default gen_random_uuid(),
  tarefa_id   uuid not null references public.tarefas (id) on delete cascade,
  empresa_id  uuid not null references public.empresas (id) on delete cascade,
  autor_id    uuid not null default auth.uid() references auth.users (id),
  corpo       text not null check (length(btrim(corpo)) between 1 and 5000),
  criado_em   timestamptz not null default now()
);

create index comentarios_por_tarefa on public.comentarios (tarefa_id, criado_em);

-- ------------------------------------------------------------------ regras de escrita

create function public.pode_ver_tarefa(p_empresa uuid, p_responsavel uuid, p_autor uuid)
returns boolean
language sql stable security definer set search_path = '' as $$
  select public.ve_todas_as_tarefas(p_empresa)
      or (public.e_membro(p_empresa) and auth.uid() in (p_responsavel, p_autor))
$$;

create function public.pode_escrever_tarefa(p_empresa uuid, p_responsavel uuid, p_autor uuid)
returns boolean
language sql stable security definer set search_path = '' as $$
  select public.tem_papel(p_empresa, 'supervisor')
      or (public.papel_em(p_empresa) = 'colaborador' and auth.uid() in (p_responsavel, p_autor))
$$;

-- O que nenhuma policy consegue dizer bem: campos que não mudam, carimbos
-- que a pessoa não escolhe, e a segregação de funções.
create function public.antes_de_gravar_tarefa() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_segregacao boolean;
begin
  if tg_op = 'INSERT' then
    new.criada_por    := coalesce(auth.uid(), new.criada_por);
    new.criada_em     := now();
    new.concluida_por := null;
    new.concluida_em  := null;
  else
    if new.empresa_id <> old.empresa_id or new.criada_por <> old.criada_por
       or new.criada_em <> old.criada_em then
      raise exception 'a empresa e o autor de uma tarefa não mudam' using errcode = '42501';
    end if;
  end if;

  -- Atribuir a outra pessoa é de quem tem visão de conjunto. Um colaborador
  -- fica com a tarefa ou larga-a, e pode continuar a editar uma que criou
  -- e alguém atribuiu a outro.
  if new.responsavel_id is distinct from (case when tg_op = 'UPDATE' then old.responsavel_id end)
     and new.responsavel_id is distinct from auth.uid()
     and new.responsavel_id is not null
     and auth.uid() is not null
     and not public.tem_papel(new.empresa_id, 'supervisor') then
    raise exception 'só quem supervisiona atribui tarefas a outras pessoas' using errcode = '42501';
  end if;

  -- O responsável tem de ser da mesma empresa.
  if new.responsavel_id is not null and not exists (
    select 1 from public.membros
    where empresa_id = new.empresa_id and user_id = new.responsavel_id
  ) then
    raise exception 'o responsável não é membro da empresa' using errcode = '23503';
  end if;

  if new.estado = 'concluida' and (tg_op = 'INSERT' or old.estado <> 'concluida') then
    select segregacao_funcoes into v_segregacao
    from public.empresas where id = new.empresa_id;
    if v_segregacao and auth.uid() = new.criada_por then
      raise exception 'segregação de funções: quem criou a tarefa não a conclui'
        using errcode = '42501';
    end if;
    new.concluida_por := auth.uid();
    new.concluida_em  := now();
  elsif new.estado <> 'concluida' then
    new.concluida_por := null;
    new.concluida_em  := null;
  else
    new.concluida_por := old.concluida_por;
    new.concluida_em  := old.concluida_em;
  end if;

  -- Gravar sem mudar nada não é uma alteração: nem mexe na hora nem
  -- chega à auditoria.
  if tg_op = 'UPDATE' and to_jsonb(new) - 'atualizada_em' = to_jsonb(old) - 'atualizada_em' then
    new.atualizada_em := old.atualizada_em;
  else
    new.atualizada_em := now();
  end if;
  return new;
end $$;

create trigger antes_de_gravar
  before insert or update on public.tarefas
  for each row execute function public.antes_de_gravar_tarefa();

create function public.antes_de_gravar_comentario() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- A empresa vem da tarefa: não se confia no que o cliente manda.
  select empresa_id into new.empresa_id from public.tarefas where id = new.tarefa_id;
  new.autor_id  := auth.uid();
  new.criado_em := now();
  return new;
end $$;

create trigger antes_de_gravar
  before insert on public.comentarios
  for each row execute function public.antes_de_gravar_comentario();

-- ------------------------------------------------------------------ RLS

alter table public.tarefas     enable row level security;
alter table public.comentarios enable row level security;

create policy tarefas_ler on public.tarefas for select to authenticated
  using (public.pode_ver_tarefa(empresa_id, responsavel_id, criada_por));

create policy tarefas_criar on public.tarefas for insert to authenticated
  with check (
    public.tem_papel(empresa_id, 'colaborador')
  );

create policy tarefas_editar on public.tarefas for update to authenticated
  using (public.pode_escrever_tarefa(empresa_id, responsavel_id, criada_por))
  with check (public.pode_escrever_tarefa(empresa_id, responsavel_id, criada_por));

create policy tarefas_apagar on public.tarefas for delete to authenticated
  using (public.tem_papel(empresa_id, 'gestor'));

-- Comentar é para quem vê a tarefa e escreve na empresa.
create policy comentarios_ler on public.comentarios for select to authenticated
  using (exists (
    select 1 from public.tarefas t where t.id = comentarios.tarefa_id
  ));
create policy comentarios_criar on public.comentarios for insert to authenticated
  with check (
    public.papel_em(empresa_id) <> 'leitor'
    and exists (select 1 from public.tarefas t where t.id = comentarios.tarefa_id)
  );
create policy comentarios_apagar on public.comentarios for delete to authenticated
  using (autor_id = auth.uid() or public.tem_papel(empresa_id, 'gestor'));

revoke all on public.tarefas, public.comentarios from anon;
revoke update on public.comentarios from authenticated;

-- ------------------------------------------------------------------ auditoria
--
-- Quem, o quê, quando, antes e depois — e de que empresa, gravado no
-- momento (ADR-0015). Ninguém escreve aqui diretamente: só os gatilhos.
-- Ninguém altera nem apaga: nem policies nem grants o permitem, e um
-- gatilho recusa-o mesmo a quem contorne a RLS.

create table public.auditoria (
  id          bigint generated always as identity primary key,
  empresa_id  uuid references public.empresas (id) on delete cascade,
  actor_id    uuid,
  acao        text not null,
  entidade    text not null,
  entidade_id text not null,
  antes       jsonb,
  depois      jsonb,
  em          timestamptz not null default now()
);

create index auditoria_empresa_em on public.auditoria (empresa_id, em desc);

alter table public.auditoria enable row level security;
create policy auditoria_ler on public.auditoria for select to authenticated
  using (public.tem_papel(empresa_id, 'administrador'));
revoke insert, update, delete, truncate on public.auditoria from anon, authenticated;
revoke all on public.auditoria from anon;

-- A única forma de uma linha sair é apagar a empresa: os dados de uma
-- empresa que saiu da plataforma não ficam para trás. O cascade dispara os
-- gatilhos de linha, por isso a exceção tem de estar escrita aqui — e só vale
-- quando a empresa da linha já não existe.
create function public.auditoria_imutavel() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'DELETE' and old.empresa_id is not null and not exists (
    select 1 from public.empresas where id = old.empresa_id
  ) then
    return old;
  end if;
  raise exception 'a auditoria não se altera nem se apaga' using errcode = '42501';
end $$;

create trigger imutavel
  before update or delete on public.auditoria
  for each row execute function public.auditoria_imutavel();
create trigger imutavel_truncate
  before truncate on public.auditoria
  for each statement execute function public.auditoria_imutavel();

create function public.registar_auditoria() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_antes  jsonb := case when tg_op <> 'INSERT' then to_jsonb(old) end;
  v_depois jsonb := case when tg_op <> 'DELETE' then to_jsonb(new) end;
  v_linha  jsonb := coalesce(v_depois, v_antes);
  v_empresa uuid;
  v_id text;
begin
  if tg_table_name = 'empresas' then
    v_empresa := (v_linha ->> 'id')::uuid;
    v_id := v_linha ->> 'id';
  else
    v_empresa := (v_linha ->> 'empresa_id')::uuid;
    v_id := coalesce(v_linha ->> 'id', v_linha ->> 'user_id');
  end if;

  -- Apagar a empresa leva tudo à frente; registá-lo seria escrever linhas
  -- que o próprio cascade vai apagar a seguir.
  if tg_op = 'DELETE' and tg_table_name <> 'empresas'
     and not exists (select 1 from public.empresas where id = v_empresa) then
    return old;
  end if;
  if tg_table_name = 'empresas' and tg_op = 'DELETE' then
    return old;
  end if;

  -- O token de um convite é uma credencial: não vai para a trilha.
  if tg_table_name = 'convites' then
    v_antes  := v_antes  - 'token';
    v_depois := v_depois - 'token';
  end if;

  if tg_op = 'UPDATE' and v_antes = v_depois then
    return new;
  end if;

  insert into public.auditoria (empresa_id, actor_id, acao, entidade, entidade_id, antes, depois)
  values (v_empresa, auth.uid(), lower(tg_op), tg_table_name, v_id, v_antes, v_depois);

  return coalesce(new, old);
end $$;

create trigger auditar after insert or update or delete on public.tarefas
  for each row execute function public.registar_auditoria();
create trigger auditar after insert or delete on public.comentarios
  for each row execute function public.registar_auditoria();
create trigger auditar after insert or update or delete on public.membros
  for each row execute function public.registar_auditoria();
create trigger auditar after insert or update or delete on public.convites
  for each row execute function public.registar_auditoria();
create trigger auditar after insert or update or delete on public.empresas
  for each row execute function public.registar_auditoria();

revoke execute on function public.registar_auditoria() from public, anon, authenticated;
revoke execute on function public.antes_de_gravar_tarefa() from public, anon, authenticated;
revoke execute on function public.antes_de_gravar_comentario() from public, anon, authenticated;

-- ------------------------------------------------------------------ painel
--
-- `security invoker`: os números são os das tarefas que quem pergunta vê.
-- Não há forma de um colaborador obter, por aqui, o total da empresa.

-- `p_hoje` vem de quem pergunta: o hoje de um servidor em UTC não é o hoje
-- de quem está em São Paulo às 22h, e é isso que decide o que está atrasado.
create function public.indicadores_painel(
  p_empresa uuid, p_dias integer default 30, p_hoje date default current_date
)
returns jsonb
language sql stable security invoker set search_path = '' as $$
  with visiveis as (
    select * from public.tarefas where empresa_id = p_empresa
  ),
  dias as (
    select generate_series(p_hoje - (least(greatest(p_dias, 7), 365) - 1), p_hoje, '1 day')::date as dia
  )
  select jsonb_build_object(
    'total',        (select count(*) from visiveis),
    'abertas',      (select count(*) from visiveis where estado <> 'concluida'),
    'atrasadas',    (select count(*) from visiveis where estado <> 'concluida' and prazo < p_hoje),
    'vencem_hoje',  (select count(*) from visiveis where estado <> 'concluida' and prazo = p_hoje),
    'concluidas_periodo', (select count(*) from visiveis
                           where concluida_em >= p_hoje - (least(greatest(p_dias, 7), 365) - 1)),
    'por_estado', (select coalesce(jsonb_object_agg(estado, n), '{}'::jsonb) from (
                     select estado, count(*) n from visiveis group by estado) e),
    'por_prioridade', (select coalesce(jsonb_object_agg(prioridade, n), '{}'::jsonb) from (
                     select prioridade, count(*) n from visiveis
                     where estado <> 'concluida' group by prioridade) p),
    'serie', (select jsonb_agg(jsonb_build_object(
                'dia', d.dia,
                'criadas', (select count(*) from visiveis v where v.criada_em::date = d.dia),
                'concluidas', (select count(*) from visiveis v where v.concluida_em::date = d.dia)
              ) order by d.dia) from dias d),
    'por_responsavel', (select coalesce(jsonb_agg(r order by r.abertas desc), '[]'::jsonb) from (
                     select v.responsavel_id, coalesce(p.nome, '') as nome,
                            count(*) filter (where v.estado <> 'concluida') as abertas,
                            count(*) filter (where v.estado <> 'concluida' and v.prazo < p_hoje) as atrasadas
                     from visiveis v left join public.perfis p on p.id = v.responsavel_id
                     group by v.responsavel_id, p.nome) r)
  )
$$;

revoke execute on function public.indicadores_painel(uuid, integer, date) from public, anon;
grant execute on function public.indicadores_painel(uuid, integer, date) to authenticated;

-- ------------------------------------------------------------------ tempo real
--
-- O quadro atualiza-se sozinho quando outra pessoa mexe numa tarefa. O
-- Supabase Realtime respeita a RLS: cada um só recebe o que pode ler.

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.tarefas, public.comentarios;
  end if;
end $$;
