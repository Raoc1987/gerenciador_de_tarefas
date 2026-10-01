-- Núcleo da plataforma web: pessoas, empresas, membros e convites.
--
-- A regra que atravessa todo o schema (ADR-0017): a autoridade é a base de
-- dados. A interface esconde o que não se pode fazer, mas quem decide é a RLS
-- e as funções abaixo — um pedido feito à mão à API recebe a mesma resposta
-- que um clique.
--
-- Os papéis vêm do desktop (src/core/permissoes.py), com um a mais: o
-- `proprietario`, que no desktop não existia porque havia um só dono da
-- instalação. Numa empresa SaaS é quem não pode ser removido por um
-- administrador.

create extension if not exists pgcrypto;

-- ------------------------------------------------------------------ tipos

create type public.papel as enum (
  'leitor',         -- vê todas as tarefas, não escreve
  'colaborador',    -- vê e escreve as suas (responsável ou autor)
  'supervisor',     -- vê e escreve as de toda a gente
  'gestor',         -- + apaga tarefas
  'administrador',  -- + gere pessoas, convites e definições; lê a auditoria
  'proprietario'    -- + promove administradores; não pode ser removido por eles
);

-- ------------------------------------------------------------------ pessoas

create table public.perfis (
  id         uuid primary key references auth.users (id) on delete cascade,
  email      text not null,
  nome       text not null default '',
  criado_em  timestamptz not null default now()
);

-- Um perfil nasce com a conta. A função é da plataforma (security definer)
-- porque quem se regista ainda não pode escrever em lado nenhum.
create function public.criar_perfil() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.perfis (id, email, nome)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data ->> 'nome', split_part(coalesce(new.email, ''), '@', 1))
  );
  return new;
end $$;

create trigger ao_criar_conta
  after insert on auth.users
  for each row execute function public.criar_perfil();

-- ------------------------------------------------------------------ empresas

create table public.empresas (
  id                  uuid primary key default gen_random_uuid(),
  nome                text not null check (length(btrim(nome)) between 2 and 120),
  -- Segregação de funções (desktop, ADR-0007): quem cria uma tarefa não a
  -- dá por concluída — nem um administrador. Desligada por omissão.
  segregacao_funcoes  boolean not null default false,
  criada_por          uuid not null references auth.users (id),
  criada_em           timestamptz not null default now()
);

create table public.membros (
  empresa_id  uuid not null references public.empresas (id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  papel       public.papel not null default 'colaborador',
  entrou_em   timestamptz not null default now(),
  primary key (empresa_id, user_id)
);

create index membros_por_pessoa on public.membros (user_id);

create table public.convites (
  id          uuid primary key default gen_random_uuid(),
  empresa_id  uuid not null references public.empresas (id) on delete cascade,
  email       text not null check (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  papel       public.papel not null default 'colaborador'
              check (papel <> 'proprietario'),
  token       text not null unique default encode(gen_random_bytes(24), 'hex'),
  criado_por  uuid not null references auth.users (id),
  criado_em   timestamptz not null default now(),
  expira_em   timestamptz not null default now() + interval '7 days',
  aceite_em   timestamptz
);

create unique index um_convite_pendente_por_email
  on public.convites (empresa_id, lower(email)) where aceite_em is null;

-- ------------------------------------------------------------------ quem é quem
--
-- Funções security definer para a RLS não se consultar a si própria em
-- recursão (uma policy de `membros` que lê `membros`). Devolvem só o que
-- diz respeito a quem pergunta.

create function public.papel_em(p_empresa uuid) returns public.papel
language sql stable security definer set search_path = '' as $$
  select m.papel from public.membros m
  where m.empresa_id = p_empresa and m.user_id = auth.uid()
$$;

create function public.e_membro(p_empresa uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.membros m
    where m.empresa_id = p_empresa and m.user_id = auth.uid()
  )
$$;

-- "Pelo menos este papel", na ordem do enum. `leitor` é a exceção à ordem
-- para a leitura de tarefas, e é tratada onde importa (ve_todas_as_tarefas).
create function public.tem_papel(p_empresa uuid, p_minimo public.papel) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(public.papel_em(p_empresa) >= p_minimo, false)
$$;

create function public.ve_todas_as_tarefas(p_empresa uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(public.papel_em(p_empresa) in
    ('leitor', 'supervisor', 'gestor', 'administrador', 'proprietario'), false)
$$;

-- ------------------------------------------------------------------ RLS

alter table public.perfis   enable row level security;
alter table public.empresas enable row level security;
alter table public.membros  enable row level security;
alter table public.convites enable row level security;

-- Vê-se o próprio perfil e os de quem partilha uma empresa connosco.
create policy perfis_ler on public.perfis for select to authenticated using (
  id = auth.uid() or exists (
    select 1 from public.membros eu
    join public.membros outro on outro.empresa_id = eu.empresa_id
    where eu.user_id = auth.uid() and outro.user_id = perfis.id
  )
);
create policy perfis_editar_o_proprio on public.perfis for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

create policy empresas_ler on public.empresas for select to authenticated
  using (public.e_membro(id));
create policy empresas_editar on public.empresas for update to authenticated
  using (public.tem_papel(id, 'administrador'))
  with check (public.tem_papel(id, 'administrador'));
-- Criar e apagar empresas passa só por funções (abaixo): criar tem de pôr o
-- criador como proprietário na mesma transação.
create policy empresas_apagar on public.empresas for delete to authenticated
  using (public.tem_papel(id, 'proprietario'));

create policy membros_ler on public.membros for select to authenticated
  using (public.e_membro(empresa_id));
-- Escrever em `membros` passa só por funções: as regras sobre quem pode dar
-- que papel a quem não cabem numa policy legível.

create policy convites_ler on public.convites for select to authenticated
  using (public.tem_papel(empresa_id, 'administrador'));
create policy convites_criar on public.convites for insert to authenticated
  with check (
    public.tem_papel(empresa_id, 'administrador')
    and criado_por = auth.uid()
    and aceite_em is null
    -- Só o proprietário convida administradores.
    and (papel < 'administrador' or public.tem_papel(empresa_id, 'proprietario'))
  );
create policy convites_apagar on public.convites for delete to authenticated
  using (public.tem_papel(empresa_id, 'administrador'));

-- ------------------------------------------------------------------ funções

create function public.criar_empresa(p_nome text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'sessão necessária' using errcode = '42501';
  end if;
  insert into public.empresas (nome, criada_por)
  values (btrim(p_nome), auth.uid())
  returning id into v_id;
  insert into public.membros (empresa_id, user_id, papel)
  values (v_id, auth.uid(), 'proprietario');
  return v_id;
end $$;

create function public.aceitar_convite(p_token text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  v_convite public.convites;
  v_email   text;
begin
  if auth.uid() is null then
    raise exception 'sessão necessária' using errcode = '42501';
  end if;

  select * into v_convite from public.convites
  where token = p_token and aceite_em is null
  for update;
  if not found or v_convite.expira_em < now() then
    raise exception 'convite inválido ou expirado' using errcode = 'P0002';
  end if;

  -- O convite é para um email: aceitá-lo com outra conta seria entrar
  -- numa empresa com o link de outra pessoa.
  select email into v_email from auth.users where id = auth.uid();
  if lower(v_email) <> lower(v_convite.email) then
    raise exception 'este convite é para outro email' using errcode = '42501';
  end if;

  insert into public.membros (empresa_id, user_id, papel)
  values (v_convite.empresa_id, auth.uid(), v_convite.papel)
  on conflict (empresa_id, user_id) do nothing;

  update public.convites set aceite_em = now() where id = v_convite.id;
  return v_convite.empresa_id;
end $$;

-- Mudar o papel de alguém. As regras:
--   * é preciso ser administrador;
--   * ninguém mexe num papel igual ou acima do seu, exceto o proprietário;
--   * só o proprietário dá `administrador` ou `proprietario`;
--   * a empresa nunca fica sem proprietário.
create function public.alterar_papel(p_empresa uuid, p_user uuid, p_papel public.papel)
returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_meu   public.papel := public.papel_em(p_empresa);
  v_atual public.papel;
begin
  if v_meu is null or v_meu < 'administrador' then
    raise exception 'sem permissão para gerir pessoas' using errcode = '42501';
  end if;

  select papel into v_atual from public.membros
  where empresa_id = p_empresa and user_id = p_user
  for update;
  if not found then
    raise exception 'essa pessoa não é membro da empresa' using errcode = 'P0002';
  end if;

  if v_meu <> 'proprietario' and (v_atual >= v_meu or p_papel >= 'administrador') then
    raise exception 'só o proprietário mexe em administradores' using errcode = '42501';
  end if;

  if v_atual = 'proprietario' and p_papel <> 'proprietario' and (
    select count(*) from public.membros
    where empresa_id = p_empresa and papel = 'proprietario'
  ) = 1 then
    raise exception 'a empresa ficaria sem proprietário' using errcode = '23514';
  end if;

  update public.membros set papel = p_papel
  where empresa_id = p_empresa and user_id = p_user;
end $$;

-- Remover alguém (ou sair, quando p_user é o próprio).
create function public.remover_membro(p_empresa uuid, p_user uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_meu   public.papel := public.papel_em(p_empresa);
  v_atual public.papel;
begin
  select papel into v_atual from public.membros
  where empresa_id = p_empresa and user_id = p_user
  for update;
  if not found then
    raise exception 'essa pessoa não é membro da empresa' using errcode = 'P0002';
  end if;

  if p_user <> auth.uid() then
    if v_meu is null or v_meu < 'administrador' then
      raise exception 'sem permissão para gerir pessoas' using errcode = '42501';
    end if;
    if v_meu <> 'proprietario' and v_atual >= v_meu then
      raise exception 'só o proprietário remove administradores' using errcode = '42501';
    end if;
  end if;

  if v_atual = 'proprietario' and (
    select count(*) from public.membros
    where empresa_id = p_empresa and papel = 'proprietario'
  ) = 1 then
    raise exception 'a empresa ficaria sem proprietário' using errcode = '23514';
  end if;

  delete from public.membros where empresa_id = p_empresa and user_id = p_user;
end $$;

-- ------------------------------------------------------------------ grants
--
-- Por omissão o Supabase concede tudo a `authenticated` e deixa a RLS
-- filtrar. Aqui retiramos o que nunca deve ser feito diretamente, para que
-- uma policy esquecida no futuro não se transforme numa porta aberta.

revoke insert, update, delete on public.membros from anon, authenticated;
revoke insert, delete on public.empresas from anon;
revoke insert on public.empresas from authenticated;
revoke update on public.convites from anon, authenticated;
revoke all on public.perfis, public.empresas, public.membros, public.convites from anon;

-- Só se pode editar o nome do próprio perfil e as definições da empresa.
revoke update on public.perfis from authenticated;
grant update (nome) on public.perfis to authenticated;
revoke update on public.empresas from authenticated;
grant update (nome, segregacao_funcoes) on public.empresas to authenticated;

revoke execute on function public.criar_perfil() from public, anon, authenticated;
revoke execute on function public.criar_empresa(text) from public, anon;
revoke execute on function public.aceitar_convite(text) from public, anon;
revoke execute on function public.alterar_papel(uuid, uuid, public.papel) from public, anon;
revoke execute on function public.remover_membro(uuid, uuid) from public, anon;
grant execute on function public.criar_empresa(text) to authenticated;
grant execute on function public.aceitar_convite(text) to authenticated;
grant execute on function public.alterar_papel(uuid, uuid, public.papel) to authenticated;
grant execute on function public.remover_membro(uuid, uuid) to authenticated;
