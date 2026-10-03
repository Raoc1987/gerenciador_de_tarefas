-- Ajudas dos testes SQL. Correm com os direitos de quem chama (não são
-- security definer), por isso a RLS aplica-se ao que executam.

create schema t;
grant usage on schema t to anon, authenticated, service_role;

create function t.pessoa(p_email text) returns uuid language sql as $$
  insert into auth.users (email) values (p_email) returning id
$$;

-- Passa a ser `p_user` nos pedidos seguintes (a seguir: `set role authenticated`).
create function t.sessao(p_user uuid) returns void language sql as $$
  select set_config('request.jwt.claims', json_build_object('sub', p_user)::text, false)
$$;

create function t.ok(p_condicao boolean, p_nome text) returns text language plpgsql as $$
begin
  if p_condicao is not true then
    raise exception 'FALHOU: %', p_nome;
  end if;
  return 'ok  ' || p_nome;
end $$;

-- Executa e espera uma recusa (qualquer erro). Devolve 'ok' se foi recusado.
create function t.recusa(p_sql text, p_nome text) returns text language plpgsql as $$
begin
  begin
    execute p_sql;
  exception when others then
    return 'ok  ' || p_nome || '  (' || sqlerrm || ')';
  end;
  raise exception 'FALHOU (era para ser recusado): %', p_nome;
end $$;

-- Como t.recusa, mas a recusa tem de ser pelo motivo certo: um erro de
-- sintaxe ou de permissão errada não conta como "recusado pela regra".
create function t.recusa_por(p_sql text, p_motivo text, p_nome text) returns text language plpgsql as $$
begin
  begin
    execute p_sql;
  exception when others then
    if position(lower(p_motivo) in lower(sqlerrm)) = 0 then
      raise exception 'FALHOU (recusado, mas pelo motivo errado): % — %', p_nome, sqlerrm;
    end if;
    return 'ok  ' || p_nome || '  (' || sqlerrm || ')';
  end;
  raise exception 'FALHOU (era para ser recusado): %', p_nome;
end $$;

-- Quantas linhas um comando tocou: a RLS em UPDATE/DELETE não dá erro,
-- simplesmente não encontra a linha.
create function t.linhas(p_sql text) returns integer language plpgsql as $$
declare n integer;
begin
  execute p_sql;
  get diagnostics n = row_count;
  return n;
end $$;

grant execute on all functions in schema t to anon, authenticated, service_role;
