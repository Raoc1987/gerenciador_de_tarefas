-- Copiloto: uma pergunta que o modelo não chegou a responder devolve-se.
--
-- Desde 20261008000000_copiloto_reserva.sql a pergunta reserva-se antes de
-- chamar o modelo. Se o modelo falhar (limite de pedidos, ligação, erro da API),
-- a reserva ficava e contava para o limite do dia e do plano sem resposta.
--
-- Libertar não pode ser um botão ao alcance de quem pergunta: com ele, um membro
-- libertava a reserva enquanto a resposta ainda estava a ser gerada e tinha
-- respostas sem gastar o plano. Por isso a reserva leva o hash de uma chave
-- aleatória que só o servidor conhece (gerada na ação, nunca enviada ao
-- browser), e só quem tem a chave a liberta. Uma reserva feita sem chave nunca
-- se liberta.

alter table public.copiloto_uso
  add column chave_hash text check (chave_hash ~ '^[0-9a-f]{64}$');

comment on column public.copiloto_uso.chave_hash is
  'sha256 (hex) da chave de libertação; só o servidor conhece a chave.';

create function public.copiloto_libertar_reserva(p_uso bigint, p_chave text)
returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  -- Só a própria reserva, ainda sem tokens (sem resposta registada), recente,
  -- e só com a chave certa.
  delete from public.copiloto_uso
   where id = p_uso
     and user_id = auth.uid()
     and tokens_entrada = 0 and tokens_saida = 0
     and em > now() - interval '15 minutes'
     and chave_hash is not null
     and chave_hash = encode(pg_catalog.sha256(convert_to(coalesce(p_chave, ''), 'UTF8')), 'hex');
  return found;
end $$;

revoke execute on function public.copiloto_libertar_reserva(bigint, text) from public, anon;
grant execute on function public.copiloto_libertar_reserva(bigint, text) to authenticated;
