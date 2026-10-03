-- Subtarefas e dependências: a primeira fatia do modelo de nós (ADR-0023).
--
-- Uma tarefa pode ter tarefa-mãe (`pai_id`), sem limite de profundidade, e
-- pode depender de outras com os quatro tipos de ligação de um cronograma
-- (fim→início, início→início, fim→fim, início→fim) e um desfasamento em dias.
-- As regras que a interface não consegue garantir vivem aqui: a mãe e as
-- tarefas ligadas são da mesma empresa, e não há ciclos — nem na hierarquia
-- nem nas dependências.
--
-- Duas pessoas a ligar tarefas ao mesmo tempo podiam fechar um ciclo entre
-- as duas transações, cada uma a ver o grafo sem a ligação da outra. Por
-- isso as verificações de ciclo tomam um trinco por empresa até ao fim da
-- transação: as ligações de uma empresa gravam-se uma de cada vez.

-- ------------------------------------------------------------------ hierarquia

alter table public.tarefas
  add column pai_id uuid references public.tarefas (id) on delete cascade;

create index tarefas_pai on public.tarefas (pai_id) where pai_id is not null;

create function public.antes_de_gravar_hierarquia() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.pai_id is null or interno.ligado('anonimizar') then
    return new;
  end if;

  perform pg_advisory_xact_lock(hashtextextended('gdt:ligacoes:' || new.empresa_id, 0));

  -- A mãe tem de ser desta empresa e visível a quem grava. A mesma frase
  -- para "não existe" e "é de outra empresa": não se confirma a existência
  -- de tarefas alheias a quem anda a tentar identificadores.
  if not exists (
    select 1 from public.tarefas m
    where m.id = new.pai_id and m.empresa_id = new.empresa_id
      and (auth.uid() is null or public.pode_ver_tarefa(m.empresa_id, m.responsavel_id, m.criada_por))
  ) then
    raise exception 'a tarefa-mãe não existe nesta empresa' using errcode = '23503';
  end if;

  if new.pai_id = new.id or exists (
    with recursive acima (id, pai_id) as (
      select id, pai_id from public.tarefas where id = new.pai_id
      union
      select t.id, t.pai_id from public.tarefas t join acima a on t.id = a.pai_id
    )
    select 1 from acima where id = new.id
  ) then
    raise exception 'uma tarefa não pode ficar dentro de si mesma nem de uma subtarefa sua'
      using errcode = '23514';
  end if;
  return new;
end $$;

create trigger antes_de_gravar_hierarquia
  before insert or update of pai_id on public.tarefas
  for each row execute function public.antes_de_gravar_hierarquia();

-- ---------------------------------------------------------------- dependências

create type public.tipo_dependencia as enum ('fim_inicio', 'inicio_inicio', 'fim_fim', 'inicio_fim');

create table public.dependencias (
  id                 uuid primary key default gen_random_uuid(),
  empresa_id         uuid not null references public.empresas (id) on delete cascade,
  -- A sucessora depende da antecessora: com fim_inicio, só começa quando a
  -- antecessora acabar (mais o desfasamento, que pode ser negativo).
  antecessora_id     uuid not null references public.tarefas (id) on delete cascade,
  sucessora_id       uuid not null references public.tarefas (id) on delete cascade,
  tipo               public.tipo_dependencia not null default 'fim_inicio',
  desfasamento_dias  integer not null default 0 check (desfasamento_dias between -365 and 365),
  criada_por         uuid default auth.uid() references auth.users (id) on delete set null,
  criada_em          timestamptz not null default now(),
  unique (antecessora_id, sucessora_id),
  check (antecessora_id <> sucessora_id)
);

create index dependencias_sucessora on public.dependencias (sucessora_id);
create index dependencias_empresa on public.dependencias (empresa_id);

create function public.antes_de_gravar_dependencia() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_empresa_ant uuid;
begin
  -- Primeiro o acesso, e só depois as regras: as frases abaixo dizem coisas
  -- sobre as tarefas (de quem é mãe, de que depende) que só pode ouvir quem
  -- as vê. A RLS também o verifica, mas só depois deste gatilho.
  if auth.uid() is not null and not (
    exists (select 1 from public.tarefas t where t.id = new.sucessora_id
            and public.pode_escrever_tarefa(t.empresa_id, t.responsavel_id, t.criada_por))
    and exists (select 1 from public.tarefas t where t.id = new.antecessora_id
                and public.pode_ver_tarefa(t.empresa_id, t.responsavel_id, t.criada_por))
  ) then
    raise exception 'não pode ligar estas tarefas' using errcode = '42501';
  end if;

  -- A empresa vem das tarefas, não do cliente.
  select empresa_id into new.empresa_id from public.tarefas where id = new.sucessora_id;
  select empresa_id into v_empresa_ant from public.tarefas where id = new.antecessora_id;
  if new.empresa_id is null or v_empresa_ant is distinct from new.empresa_id then
    raise exception 'as duas tarefas têm de ser da mesma empresa' using errcode = '23503';
  end if;
  if new.antecessora_id = new.sucessora_id then
    raise exception 'uma tarefa não depende de si própria' using errcode = '23514';
  end if;
  new.criada_por := auth.uid();
  new.criada_em  := now();

  perform pg_advisory_xact_lock(hashtextextended('gdt:ligacoes:' || new.empresa_id, 0));

  -- Mãe e subtarefa não se ligam: a mãe resume as filhas, e ligá-las faria
  -- a mãe esperar por si própria.
  if exists (
    with recursive acima (id, pai_id) as (
      select id, pai_id from public.tarefas where id = new.sucessora_id
      union
      select t.id, t.pai_id from public.tarefas t join acima a on t.id = a.pai_id
    )
    select 1 from acima where id = new.antecessora_id
  ) or exists (
    with recursive acima (id, pai_id) as (
      select id, pai_id from public.tarefas where id = new.antecessora_id
      union
      select t.id, t.pai_id from public.tarefas t join acima a on t.id = a.pai_id
    )
    select 1 from acima where id = new.sucessora_id
  ) then
    raise exception 'uma tarefa não depende da sua tarefa-mãe nem de uma subtarefa sua'
      using errcode = '23514';
  end if;

  -- Ciclo: se a antecessora já depende, direta ou indiretamente, da
  -- sucessora, esta ligação fechava o círculo.
  if exists (
    with recursive antes (id) as (
      select antecessora_id from public.dependencias where sucessora_id = new.antecessora_id
      union
      select d.antecessora_id from public.dependencias d join antes a on d.sucessora_id = a.id
    )
    select 1 from antes where id = new.sucessora_id
  ) then
    raise exception 'esta dependência fecharia um ciclo' using errcode = '23514';
  end if;
  return new;
end $$;

create trigger antes_de_gravar
  before insert on public.dependencias
  for each row execute function public.antes_de_gravar_dependencia();

create trigger auditar after insert or delete on public.dependencias
  for each row execute function public.registar_auditoria();

revoke execute on function public.antes_de_gravar_hierarquia() from public, anon, authenticated;
revoke execute on function public.antes_de_gravar_dependencia() from public, anon, authenticated;

-- ------------------------------------------------------------------------- RLS
--
-- As subconsultas a `tarefas` correm com a RLS de quem pede: uma ligação só
-- se vê quando se veem as duas pontas, e só se cria ou apaga quando se pode
-- escrever na tarefa que fica à espera.

alter table public.dependencias enable row level security;

create policy dependencias_ler on public.dependencias for select to authenticated
  using (
    exists (select 1 from public.tarefas t where t.id = sucessora_id)
    and exists (select 1 from public.tarefas t where t.id = antecessora_id)
  );

create policy dependencias_criar on public.dependencias for insert to authenticated
  with check (
    exists (select 1 from public.tarefas t where t.id = sucessora_id
            and public.pode_escrever_tarefa(t.empresa_id, t.responsavel_id, t.criada_por))
    and exists (select 1 from public.tarefas t where t.id = antecessora_id)
  );

create policy dependencias_apagar on public.dependencias for delete to authenticated
  using (
    exists (select 1 from public.tarefas t where t.id = sucessora_id
            and public.pode_escrever_tarefa(t.empresa_id, t.responsavel_id, t.criada_por))
  );

revoke all on public.dependencias from anon;
revoke update, truncate on public.dependencias from authenticated;
grant select, insert, delete on public.dependencias to authenticated;
