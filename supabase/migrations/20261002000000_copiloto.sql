-- Copiloto (Claude): registo de uso e limite diário por pessoa.
--
-- O Copiloto lê com a sessão de quem pergunta — a RLS aplica-se a ele como a
-- qualquer outro pedido — e não escreve nada: propõe, e a pessoa aplica.
-- Esta tabela existe para o custo: cada pergunta gasta tokens pagos, e uma
-- empresa precisa de saber quanto e de pôr um teto.

create table public.copiloto_uso (
  id             bigint generated always as identity primary key,
  empresa_id     uuid not null references public.empresas (id) on delete cascade,
  user_id        uuid not null default auth.uid() references auth.users (id) on delete cascade,
  tokens_entrada integer not null default 0 check (tokens_entrada >= 0),
  tokens_saida   integer not null default 0 check (tokens_saida >= 0),
  em             timestamptz not null default now()
);

create index copiloto_uso_pessoa_dia on public.copiloto_uso (user_id, em desc);
create index copiloto_uso_empresa on public.copiloto_uso (empresa_id, em desc);

alter table public.copiloto_uso enable row level security;

-- Cada um regista o seu uso, numa empresa de que é membro, e com a hora do
-- servidor — não se escolhe o dia em que se gastou.
create policy copiloto_uso_registar on public.copiloto_uso for insert to authenticated
  with check (user_id = auth.uid() and public.e_membro(empresa_id));
-- Vê o seu; quem administra vê o da empresa.
create policy copiloto_uso_ler on public.copiloto_uso for select to authenticated
  using (user_id = auth.uid() or public.tem_papel(empresa_id, 'administrador'));

revoke all on public.copiloto_uso from anon;
revoke update, delete on public.copiloto_uso from authenticated;

create function public.antes_de_registar_uso() returns trigger
language plpgsql as $$
begin
  new.user_id := auth.uid();
  new.em := now();
  return new;
end $$;

create trigger antes_de_registar
  before insert on public.copiloto_uso
  for each row execute function public.antes_de_registar_uso();

-- Quantas perguntas esta pessoa já fez hoje (no fuso que a aplicação indica).
create function public.copiloto_perguntas_hoje(p_fuso text default 'America/Sao_Paulo')
returns integer
language sql stable security invoker set search_path = '' as $$
  select count(*)::integer from public.copiloto_uso
  where user_id = auth.uid()
    and (em at time zone p_fuso)::date = (now() at time zone p_fuso)::date
$$;

revoke execute on function public.copiloto_perguntas_hoje(text) from public, anon;
grant execute on function public.copiloto_perguntas_hoje(text) to authenticated;
