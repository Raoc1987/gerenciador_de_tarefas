-- Importação dos dados da aplicação de secretária (ADR-0020).
--
-- O browser lê o tarefas.db e manda as tarefas; esta função grava-as na
-- empresa escolhida, como quem importa, preservando as datas de criação e
-- de conclusão. Reimportar o mesmo ficheiro não duplica nada: cada tarefa
-- traz uma `origem` única por empresa.

alter table public.tarefas add column origem text check (length(origem) <= 200);
create unique index tarefas_origem_unica on public.tarefas (empresa_id, origem) where origem is not null;

create or replace function public.antes_de_gravar_tarefa() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_segregacao boolean;
  -- Só public.importar_tarefas liga isto, e só durante a importação: as
  -- datas que vêm do desktop são história, não o momento de agora.
  v_importacao boolean := coalesce(current_setting('gdt.importacao', true), '') = 'on';
begin
  if tg_op = 'INSERT' then
    new.criada_por    := coalesce(auth.uid(), new.criada_por);
    new.criada_em     := case when v_importacao then coalesce(new.criada_em, now()) else now() end;
    new.concluida_por := null;
    if not v_importacao then new.concluida_em := null; end if;
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

  if tg_op = 'INSERT' and v_importacao and new.estado = 'concluida' then
    -- Concluída no desktop: a data é a de lá, e a segregação de funções não
    -- se aplica a um facto passado.
    new.concluida_por := auth.uid();
    new.concluida_em  := coalesce(new.concluida_em, new.criada_em);
  elsif new.estado = 'concluida' and (tg_op = 'INSERT' or old.estado <> 'concluida') then
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

-- Importar não manda um email por cada tarefa atribuída.
create or replace function public.avisar_atribuicao() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_email text;
begin
  if coalesce(current_setting('gdt.importacao', true), '') = 'on'
     or new.responsavel_id is null
     or new.responsavel_id = auth.uid()
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

-- As datas do desktop chegam como hora local sem fuso; `p_fuso` diz qual era
-- (com as regras de hora de verão desse fuso, que um desvio fixo não tem).
-- Grava um lote de até 1000 tarefas. Devolve quantas entraram, quantas já
-- lá estavam (mesma origem) e quantas foram recusadas (com o motivo das
-- primeiras). Uma tarefa inválida não deita abaixo o lote.
create function public.importar_tarefas(
  p_empresa uuid, p_tarefas jsonb, p_fuso text default 'Europe/Lisbon'
) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_t jsonb;
  v_resp uuid;
  v_inseridas integer := 0;
  v_repetidas integer := 0;
  v_recusadas integer := 0;
  v_motivos jsonb := '[]';
  v_n integer;
begin
  if not public.tem_papel(p_empresa, 'administrador') then
    raise exception 'só quem administra a empresa importa dados' using errcode = '42501';
  end if;
  if not exists (select 1 from pg_timezone_names where name = p_fuso) then
    raise exception 'fuso desconhecido: %', p_fuso using errcode = '22023';
  end if;
  if jsonb_typeof(p_tarefas) <> 'array' or jsonb_array_length(p_tarefas) > 1000 then
    raise exception 'um lote tem no máximo 1000 tarefas' using errcode = '22023';
  end if;

  perform set_config('gdt.importacao', 'on', true);
  for v_t in select * from jsonb_array_elements(p_tarefas) loop
    begin
      v_resp := nullif(v_t ->> 'responsavel_id', '')::uuid;
      if v_resp is not null and not exists (
        select 1 from public.membros where empresa_id = p_empresa and user_id = v_resp
      ) then
        v_resp := null;
      end if;
      insert into public.tarefas (
        empresa_id, titulo, descricao, estado, prazo, etiquetas, responsavel_id,
        criada_em, concluida_em, origem
      ) values (
        p_empresa,
        v_t ->> 'titulo',
        coalesce(v_t ->> 'descricao', ''),
        coalesce(nullif(v_t ->> 'estado', ''), 'a_fazer')::public.estado_tarefa,
        nullif(v_t ->> 'prazo', '')::date,
        coalesce(array(select jsonb_array_elements_text(v_t -> 'etiquetas')), '{}'),
        v_resp,
        nullif(v_t ->> 'criada_em', '')::timestamp at time zone p_fuso,
        nullif(v_t ->> 'concluida_em', '')::timestamp at time zone p_fuso,
        v_t ->> 'origem'
      )
      on conflict (empresa_id, origem) where origem is not null do nothing;
      get diagnostics v_n = row_count;
      if v_n = 1 then v_inseridas := v_inseridas + 1; else v_repetidas := v_repetidas + 1; end if;
    exception when others then
      v_recusadas := v_recusadas + 1;
      if jsonb_array_length(v_motivos) < 10 then
        v_motivos := v_motivos || jsonb_build_object('origem', v_t ->> 'origem', 'motivo', sqlerrm);
      end if;
    end;
  end loop;
  perform set_config('gdt.importacao', '', true);

  return jsonb_build_object(
    'inseridas', v_inseridas, 'repetidas', v_repetidas, 'recusadas', v_recusadas, 'motivos', v_motivos
  );
end $$;

revoke execute on function public.importar_tarefas(uuid, jsonb, text) from public, anon;
grant execute on function public.importar_tarefas(uuid, jsonb, text) to authenticated;
