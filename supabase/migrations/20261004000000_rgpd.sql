-- RGPD: cada pessoa descarrega os seus dados e apaga a sua conta, sem
-- depender de ninguém. As duas coisas decidem-se aqui, como o resto.
--
-- Apagar a conta não apaga o trabalho da empresa: as tarefas, os comentários
-- e as empresas que a pessoa criou ficam, com o autor vazio. A auditoria fica
-- como está (é imutável) e guarda só o identificador, que deixa de levar a
-- alguém quando a conta desaparece.

-- --------------------------------------------------------- modos internos

-- Alguns caminhos legítimos precisam que os gatilhos se afastem: a importação
-- do desktop (datas históricas) e o apagamento de uma conta (o autor muda para
-- vazio). Até aqui isso era uma variável de sessão (`gdt.importacao`), que
-- qualquer ligação com SQL podia ligar à mão. Agora é uma linha numa tabela
-- de um esquema onde ninguém em sessão entra, válida só para a transação que
-- a escreveu: não se forja e não sobrevive a um erro.
create schema interno;
revoke all on schema interno from public;

create table interno.modos (
  transacao xid8 not null default pg_current_xact_id(),
  modo      text not null check (modo in ('importacao', 'anonimizar')),
  primary key (transacao, modo)
);

create function interno.ligar(p_modo text) returns void
language sql security definer set search_path = '' as $$
  insert into interno.modos (modo) values (p_modo) on conflict do nothing
$$;

create function interno.desligar(p_modo text) returns void
language sql security definer set search_path = '' as $$
  delete from interno.modos where transacao = pg_current_xact_id() and modo = p_modo
$$;

create function interno.ligado(p_modo text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from interno.modos where transacao = pg_current_xact_id() and modo = p_modo)
$$;

revoke execute on function interno.ligar(text), interno.desligar(text), interno.ligado(text) from public, anon, authenticated;

-- O autor pode ficar vazio: é o "pessoa removida".
alter table public.empresas    alter column criada_por drop not null;
alter table public.convites    alter column criado_por drop not null;
alter table public.tarefas     alter column criada_por drop not null;
alter table public.comentarios alter column autor_id   drop not null;

create or replace function public.antes_de_gravar_tarefa() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_segregacao boolean;
  -- Só public.importar_tarefas liga isto, e só durante a importação: as
  -- datas que vêm do desktop são história, não o momento de agora. O modo
  -- vive em interno.modos, onde ninguém em sessão escreve.
  v_importacao boolean := interno.ligado('importacao');
begin
  -- Apagar uma conta (apagar_a_minha_conta) tira a pessoa das tarefas que
  -- criou, concluiu ou tinha atribuídas. As regras abaixo são para quem
  -- trabalha nas tarefas, não para isso — e "o autor não muda" impedia-o.
  if interno.ligado('anonimizar') then
    return new;
  end if;

  if tg_op = 'INSERT' then
    new.criada_por    := coalesce(auth.uid(), new.criada_por);
    new.criada_em     := case when v_importacao then coalesce(new.criada_em, now()) else now() end;
    new.concluida_por := null;
    if not v_importacao then new.concluida_em := null; end if;
  else
    -- "is distinct from" e não "<>": com o autor vazio (conta apagada), "<>"
    -- dá null e a regra deixava qualquer pessoa ficar com a tarefa.
    if new.empresa_id is distinct from old.empresa_id or new.criada_por is distinct from old.criada_por
       or new.criada_em is distinct from old.criada_em then
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

create or replace function public.avisar_atribuicao() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_email text;
begin
  if interno.ligado('importacao') or interno.ligado('anonimizar')
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

create or replace function public.importar_tarefas(
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

  perform interno.ligar('importacao');
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
  perform interno.desligar('importacao');

  return jsonb_build_object(
    'inseridas', v_inseridas, 'repetidas', v_repetidas, 'recusadas', v_recusadas, 'motivos', v_motivos
  );
end $$;

-- ------------------------------------------------------------ exportar

-- Tudo o que é da pessoa, em todas as empresas, mesmo nas que já deixou:
-- o direito de acesso não depende de ainda ser membro. Por isso é security
-- definer, e por isso só olha para auth.uid().
create function public.exportar_os_meus_dados() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  v_eu uuid := auth.uid();
begin
  if v_eu is null then
    raise exception 'é preciso ter sessão iniciada' using errcode = '42501';
  end if;
  return jsonb_build_object(
    'gerado_em', now(),
    'conta', (select jsonb_build_object('id', u.id, 'email', u.email) from auth.users u where u.id = v_eu),
    'perfil', (select to_jsonb(p) from public.perfis p where p.id = v_eu),
    'empresas', coalesce((
      select jsonb_agg(jsonb_build_object('empresa', e.nome, 'papel', m.papel, 'entrou_em', m.entrou_em) order by e.nome)
      from public.membros m join public.empresas e on e.id = m.empresa_id
      where m.user_id = v_eu), '[]'),
    'tarefas', coalesce((
      select jsonb_agg(jsonb_build_object(
               'empresa', e.nome, 'titulo', t.titulo, 'descricao', t.descricao, 'estado', t.estado,
               'prioridade', t.prioridade, 'prazo', t.prazo, 'etiquetas', t.etiquetas,
               'criada_por_mim', t.criada_por = v_eu, 'atribuida_a_mim', t.responsavel_id = v_eu,
               'concluida_por_mim', t.concluida_por = v_eu, 'criada_em', t.criada_em)
             order by t.criada_em)
      from public.tarefas t join public.empresas e on e.id = t.empresa_id
      where v_eu in (t.criada_por, t.responsavel_id, t.concluida_por)), '[]'),
    'comentarios', coalesce((
      select jsonb_agg(jsonb_build_object('empresa', e.nome, 'tarefa', t.titulo, 'corpo', c.corpo, 'criado_em', c.criado_em)
             order by c.criado_em)
      from public.comentarios c join public.tarefas t on t.id = c.tarefa_id join public.empresas e on e.id = c.empresa_id
      where c.autor_id = v_eu), '[]'),
    'notificacoes', (select to_jsonb(n) - 'user_id' from public.preferencias_notificacao n where n.user_id = v_eu),
    'copiloto', coalesce((
      select jsonb_agg(to_jsonb(c) - 'user_id' order by c.em) from public.copiloto_uso c where c.user_id = v_eu), '[]'),
    'auditoria', coalesce((
      select jsonb_agg(jsonb_build_object('acao', a.acao, 'entidade', a.entidade, 'em', a.em) order by a.em)
      from public.auditoria a where a.actor_id = v_eu), '[]')
  );
end $$;

-- -------------------------------------------------------------- apagar

-- Confirma-se com o próprio email, para um clique não apagar uma conta.
-- Uma empresa não fica sem proprietário: quem é o único proprietário de uma
-- empresa com mais pessoas tem de passar a propriedade antes. Uma empresa
-- onde a pessoa está sozinha apaga-se com ela.
create function public.apagar_a_minha_conta(p_confirmacao text) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_eu    uuid := auth.uid();
  v_email text;
  v_bloq  boolean;
begin
  if v_eu is null then
    raise exception 'é preciso ter sessão iniciada' using errcode = '42501';
  end if;
  select email into v_email from auth.users where id = v_eu;
  if v_email is null or lower(btrim(coalesce(p_confirmacao, ''))) <> lower(v_email) then
    raise exception 'para confirmar, escreva o email da sua conta' using errcode = '22023';
  end if;

  select exists (
    select 1 from public.membros m
    where m.user_id = v_eu and m.papel = 'proprietario'
    and not exists (select 1 from public.membros o
                    where o.empresa_id = m.empresa_id and o.user_id <> v_eu and o.papel = 'proprietario')
    and exists (select 1 from public.membros o where o.empresa_id = m.empresa_id and o.user_id <> v_eu)
  ) into v_bloq;
  if v_bloq then
    -- Sem o nome da empresa na frase: a interface só mostra frases nossas,
    -- e um nome com pontuação deixava de passar por uma.
    raise exception 'é a única pessoa proprietária de uma empresa com mais gente: passe a propriedade a outra pessoa antes de apagar a conta'
      using errcode = '42501';
  end if;

  delete from public.empresas e
  where exists (select 1 from public.membros m where m.empresa_id = e.id and m.user_id = v_eu)
    and not exists (select 1 from public.membros m where m.empresa_id = e.id and m.user_id <> v_eu);

  perform interno.ligar('anonimizar');
  update public.tarefas set criada_por = null where criada_por = v_eu;
  update public.tarefas set concluida_por = null where concluida_por = v_eu;
  update public.tarefas set responsavel_id = null where responsavel_id = v_eu;
  update public.comentarios set autor_id = null where autor_id = v_eu;
  update public.empresas    set criada_por = null where criada_por = v_eu;
  update public.convites    set criado_por = null where criado_por = v_eu;
  perform interno.desligar('anonimizar');

  -- O resto (perfil, pertenças, preferências, uso do Copiloto, emails por
  -- enviar) vai em cascata.
  delete from auth.users where id = v_eu;
end $$;

revoke execute on function public.exportar_os_meus_dados() from public, anon;
revoke execute on function public.apagar_a_minha_conta(text) from public, anon;
grant execute on function public.exportar_os_meus_dados() to authenticated;
grant execute on function public.apagar_a_minha_conta(text) to authenticated;
