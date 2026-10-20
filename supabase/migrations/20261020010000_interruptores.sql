-- Interruptores de funcionalidade por empresa (ADR-0026).
--
-- "Nada vai para todos ao mesmo tempo" (docs/conhecimento/catalogo.json): uma
-- funcionalidade nova ou cara pode ligar-se a algumas empresas antes das outras,
-- ou desligar-se só numa. Quem decide é o operador do serviço (migrações ou a
-- chave de serviço), nunca a própria empresa: nenhum papel, nem o proprietário,
-- escreve nestas tabelas.
--
-- O que nunca pode acontecer: uma empresa saber alguma coisa de outra. Cada
-- membro lê só os interruptores da sua empresa; perguntar por uma empresa de
-- que não é membro responde "desligada", sem distinguir se ela existe.

create table public.funcionalidades (
  codigo             text primary key check (codigo ~ '^[a-z][a-z_]{1,39}$'),
  descricao          text not null check (length(btrim(descricao)) between 2 and 200),
  ligada_por_omissao boolean not null
);

create table public.funcionalidades_empresa (
  id             bigint generated always as identity primary key,
  empresa_id     uuid not null references public.empresas (id) on delete cascade,
  funcionalidade text not null references public.funcionalidades (codigo) on delete cascade,
  ligada         boolean not null,
  motivo         text check (motivo is null or length(motivo) <= 500),
  alterada_em    timestamptz not null default now(),
  unique (empresa_id, funcionalidade)
);

alter table public.funcionalidades enable row level security;
alter table public.funcionalidades_empresa enable row level security;

-- O catálogo não tem nada de nenhuma empresa: quem tem sessão lê-o.
create policy funcionalidades_ler on public.funcionalidades for select to authenticated using (true);
-- Os interruptores de uma empresa só os vê quem é membro dela.
create policy funcionalidades_empresa_ler on public.funcionalidades_empresa for select to authenticated
  using (public.e_membro(empresa_id));

revoke all on public.funcionalidades, public.funcionalidades_empresa from anon, authenticated;
grant select on public.funcionalidades, public.funcionalidades_empresa to authenticated;

create trigger auditar after insert or update or delete on public.funcionalidades_empresa
  for each row execute function public.registar_auditoria();

-- O valor efetivo, sem olhar a quem pergunta: só para gatilhos e funções da base.
create function interno.funcionalidade_efetiva(p_empresa uuid, p_codigo text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(
    (select fe.ligada from public.funcionalidades_empresa fe
      where fe.empresa_id = p_empresa and fe.funcionalidade = p_codigo),
    (select f.ligada_por_omissao from public.funcionalidades f where f.codigo = p_codigo),
    false)
$$;
revoke execute on function interno.funcionalidade_efetiva(uuid, text) from public;

-- O que a interface consulta. Fora da empresa responde sempre false.
create function public.funcionalidade_ligada(p_empresa uuid, p_codigo text) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.e_membro(p_empresa) and interno.funcionalidade_efetiva(p_empresa, p_codigo)
$$;
revoke execute on function public.funcionalidade_ligada(uuid, text) from public, anon;
grant execute on function public.funcionalidade_ligada(uuid, text) to authenticated;

-- O primeiro interruptor: o Copiloto, ligado para todas por omissão. Desligado
-- numa empresa, a base recusa a pergunta antes de haver custo (e antes do
-- limite do plano: os gatilhos BEFORE correm por ordem alfabética).
insert into public.funcionalidades values ('copiloto', 'Copiloto (assistente com IA)', true);

create function public.copiloto_so_se_ligado() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if not interno.funcionalidade_efetiva(new.empresa_id, 'copiloto') then
    raise exception 'o copiloto não está disponível para esta empresa' using errcode = '42501';
  end if;
  return new;
end $$;
revoke execute on function public.copiloto_so_se_ligado() from public, anon, authenticated;

create trigger funcionalidade_ligada before insert on public.copiloto_uso
  for each row execute function public.copiloto_so_se_ligado();
