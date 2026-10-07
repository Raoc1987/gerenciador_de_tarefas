-- Planos e faturação (ADR-0025).
--
-- Os limites de cada plano são regras de negócio e vivem aqui: quantas
-- pessoas, quantas tarefas por concluir, quantas perguntas ao Copiloto por
-- mês. A interface mostra-os e avisa antes; quem recusa é a base.
--
-- O plano de uma empresa só muda por aplicar_faturacao, que só a chave de
-- serviço chama (a rota do webhook, depois de verificar a assinatura do
-- fornecedor de pagamentos). Ninguém em sessão, nem a pessoa proprietária,
-- escolhe o plano escrevendo na tabela.

create type public.plano as enum ('gratuito', 'equipa', 'empresa');

-- Os valores são dados, não código: mudam por migração, com o histórico no
-- git. null = sem limite.
create table public.planos (
  codigo                  public.plano primary key,
  nome                    text not null,
  max_membros             integer check (max_membros > 0),
  max_tarefas_abertas     integer check (max_tarefas_abertas > 0),
  copiloto_perguntas_mes  integer check (copiloto_perguntas_mes >= 0),
  preco_mensal_centimos   integer not null check (preco_mensal_centimos >= 0),
  ordem                   integer not null unique
);

insert into public.planos values
  ('gratuito', 'Gratuito', 5,    200,  50,    0,     1),
  ('equipa',   'Equipa',   25,   5000, 1000,  4900,  2),
  ('empresa',  'Empresa',  null, null, 10000, 19900, 3);

alter table public.planos enable row level security;
create policy planos_ler on public.planos for select to authenticated using (true);
revoke all on public.planos from anon;
revoke insert, update, delete, truncate on public.planos from authenticated;

alter table public.empresas
  add column plano     public.plano not null default 'gratuito',
  -- Fim do período pago. Passados 3 dias sem renovação confirmada, a empresa
  -- conta como Gratuito mesmo que o aviso do fornecedor se tenha perdido.
  add column plano_ate timestamptz;

-- O que identifica a empresa no fornecedor de pagamentos fica fora do
-- alcance da API: não é segredo, mas também não é da conta dos membros.
create table interno.faturacao (
  empresa_id     uuid primary key references public.empresas (id) on delete cascade,
  cliente        text,
  subscricao     text,
  atualizado_em  timestamptz not null
);

-- Cada evento do fornecedor aplica-se uma vez: os webhooks repetem-se.
create table interno.eventos_faturacao (
  id           text primary key,
  recebido_em  timestamptz not null default now()
);

-- ------------------------------------------------------------- plano efetivo

create function public.plano_efetivo(p_empresa uuid) returns public.plano
language sql stable security definer set search_path = '' as $$
  select case
    when e.plano_ate is not null and e.plano_ate < now() - interval '3 days' then 'gratuito'::public.plano
    else e.plano
  end
  from public.empresas e where e.id = p_empresa
$$;

-- Escrever o plano à mão é recusado a quem está em sessão. Corre com os
-- direitos de quem chama (security invoker), por isso current_user é o papel
-- do pedido; dentro de aplicar_faturacao, que é security definer, é o dono.
create function public.plano_so_pela_faturacao() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (new.plano is distinct from old.plano or new.plano_ate is distinct from old.plano_ate)
     and current_user in ('authenticated', 'anon') then
    raise exception 'o plano muda só pela faturação' using errcode = '42501';
  end if;
  return new;
end $$;

create trigger plano_so_pela_faturacao
  before update on public.empresas
  for each row execute function public.plano_so_pela_faturacao();

-- ----------------------------------------------------------------- limites
--
-- Um trinco por empresa: dois convites aceites ao mesmo tempo não passam
-- os dois pelo último lugar livre.

create function public.limite_de_membros() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_plano public.planos;
  v_n integer;
begin
  select p.* into v_plano from public.planos p where p.codigo = public.plano_efetivo(new.empresa_id);
  if v_plano.max_membros is null then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtextextended('gdt:limite:' || new.empresa_id, 0));
  select count(*) into v_n from public.membros where empresa_id = new.empresa_id;
  -- Um convite pendente guarda um lugar: convidar para lá do limite seria
  -- prometer o que a aceitação vai recusar.
  if tg_table_name = 'convites' then
    v_n := v_n + (select count(*) from public.convites
                  where empresa_id = new.empresa_id and aceite_em is null and expira_em > now());
  end if;
  if v_n >= v_plano.max_membros then
    raise exception 'o plano % permite até % pessoas: mude de plano para juntar mais',
      v_plano.nome, v_plano.max_membros using errcode = '23514';
  end if;
  return new;
end $$;

create trigger limite_do_plano before insert on public.membros
  for each row execute function public.limite_de_membros();
create trigger limite_do_plano before insert on public.convites
  for each row execute function public.limite_de_membros();

create function public.limite_de_tarefas() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_plano public.planos;
  v_n integer;
begin
  -- Só conta o que abre uma tarefa: criar uma por concluir, ou reabrir.
  if new.estado = 'concluida'
     or (tg_op = 'UPDATE' and old.estado <> 'concluida')
     or interno.ligado('anonimizar') then
    return new;
  end if;
  select p.* into v_plano from public.planos p where p.codigo = public.plano_efetivo(new.empresa_id);
  if v_plano.max_tarefas_abertas is null then
    return new;
  end if;
  perform pg_advisory_xact_lock(hashtextextended('gdt:limite:' || new.empresa_id, 0));
  select count(*) into v_n from public.tarefas where empresa_id = new.empresa_id and estado <> 'concluida';
  if v_n >= v_plano.max_tarefas_abertas then
    raise exception 'o plano % permite até % tarefas por concluir: conclua ou apague algumas, ou mude de plano',
      v_plano.nome, v_plano.max_tarefas_abertas using errcode = '23514';
  end if;
  return new;
end $$;

create trigger limite_do_plano before insert or update of estado on public.tarefas
  for each row execute function public.limite_de_tarefas();

-- Perguntas ao Copiloto contam por empresa e por mês civil de Lisboa.
create function interno.copiloto_usadas_mes(p_empresa uuid) returns integer
language sql stable security definer set search_path = '' as $$
  select count(*)::integer from public.copiloto_uso
  where empresa_id = p_empresa
    and date_trunc('month', em at time zone 'Europe/Lisbon') = date_trunc('month', now() at time zone 'Europe/Lisbon')
$$;

create function public.limite_do_copiloto() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_plano public.planos;
begin
  select p.* into v_plano from public.planos p where p.codigo = public.plano_efetivo(new.empresa_id);
  if v_plano.copiloto_perguntas_mes is not null
     and interno.copiloto_usadas_mes(new.empresa_id) >= v_plano.copiloto_perguntas_mes then
    raise exception 'o plano % permite % perguntas ao copiloto por mês, e já foram todas',
      v_plano.nome, v_plano.copiloto_perguntas_mes using errcode = '23514';
  end if;
  return new;
end $$;

create trigger limite_do_plano before insert on public.copiloto_uso
  for each row execute function public.limite_do_copiloto();

-- ------------------------------------------------- o que a interface consulta

create function public.uso_do_plano(p_empresa uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  v_plano public.planos;
begin
  if not public.e_membro(p_empresa) then
    raise exception 'não é membro desta empresa' using errcode = '42501';
  end if;
  select p.* into v_plano from public.planos p where p.codigo = public.plano_efetivo(p_empresa);
  return jsonb_build_object(
    'plano', v_plano.codigo,
    'nome', v_plano.nome,
    'plano_ate', (select plano_ate from public.empresas where id = p_empresa),
    'membros', jsonb_build_object(
      'usados', (select count(*) from public.membros where empresa_id = p_empresa),
      'maximo', v_plano.max_membros),
    'tarefas_abertas', jsonb_build_object(
      'usados', (select count(*) from public.tarefas where empresa_id = p_empresa and estado <> 'concluida'),
      'maximo', v_plano.max_tarefas_abertas),
    'copiloto_mes', jsonb_build_object(
      'usados', interno.copiloto_usadas_mes(p_empresa),
      'maximo', v_plano.copiloto_perguntas_mes)
  );
end $$;

-- ----------------------------------------------------------------- faturação

-- O que a rota de checkout precisa para abrir uma sessão de pagamento. Só a
-- pessoa proprietária paga pela empresa.
create function public.preparar_faturacao(p_empresa uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if not public.tem_papel(p_empresa, 'proprietario') then
    raise exception 'só a pessoa proprietária gere a faturação' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'plano', public.plano_efetivo(p_empresa),
    'cliente', (select cliente from interno.faturacao where empresa_id = p_empresa),
    'email', (select email from auth.users where id = auth.uid())
  );
end $$;

-- Aplica um evento do fornecedor, já verificado pela rota do webhook. Devolve
-- false quando não muda nada: evento repetido, empresa que já não existe, ou
-- evento mais antigo do que o último aplicado (os webhooks chegam fora de
-- ordem).
create function public.aplicar_faturacao(
  p_evento text, p_criado timestamptz, p_empresa uuid, p_plano public.plano,
  p_ate timestamptz, p_cliente text, p_subscricao text
) returns boolean
language plpgsql security definer set search_path = '' as $$
declare
  v_ultimo timestamptz;
begin
  insert into interno.eventos_faturacao (id) values (p_evento) on conflict do nothing;
  if not found then
    return false;
  end if;
  if not exists (select 1 from public.empresas where id = p_empresa) then
    return false;
  end if;
  perform pg_advisory_xact_lock(hashtextextended('gdt:faturacao:' || p_empresa, 0));
  select atualizado_em into v_ultimo from interno.faturacao where empresa_id = p_empresa;
  if v_ultimo is not null and p_criado < v_ultimo then
    return false;
  end if;
  update public.empresas set plano = p_plano, plano_ate = p_ate where id = p_empresa;
  insert into interno.faturacao (empresa_id, cliente, subscricao, atualizado_em)
  values (p_empresa, p_cliente, p_subscricao, p_criado)
  on conflict (empresa_id) do update
    set cliente = coalesce(excluded.cliente, interno.faturacao.cliente),
        subscricao = coalesce(excluded.subscricao, interno.faturacao.subscricao),
        atualizado_em = excluded.atualizado_em;
  return true;
end $$;

revoke execute on function public.plano_efetivo(uuid) from public, anon;
grant execute on function public.plano_efetivo(uuid) to authenticated;
revoke execute on function public.uso_do_plano(uuid) from public, anon;
grant execute on function public.uso_do_plano(uuid) to authenticated;
revoke execute on function public.preparar_faturacao(uuid) from public, anon;
grant execute on function public.preparar_faturacao(uuid) to authenticated;
revoke execute on function public.aplicar_faturacao(text, timestamptz, uuid, public.plano, timestamptz, text, text)
  from public, anon, authenticated;
grant execute on function public.aplicar_faturacao(text, timestamptz, uuid, public.plano, timestamptz, text, text)
  to service_role;
revoke execute on function public.limite_de_membros() from public, anon, authenticated;
revoke execute on function public.limite_de_tarefas() from public, anon, authenticated;
revoke execute on function public.limite_do_copiloto() from public, anon, authenticated;
revoke execute on function public.plano_so_pela_faturacao() from public, anon, authenticated;
revoke execute on function interno.copiloto_usadas_mes(uuid) from public, anon, authenticated;
