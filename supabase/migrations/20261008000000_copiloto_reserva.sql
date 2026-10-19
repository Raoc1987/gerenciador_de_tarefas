-- Copiloto: a pergunta reserva-se ANTES de chamar o modelo (docs/METODO.md, R3).
--
-- Até aqui o uso registava-se depois da resposta, e o erro desse insert era
-- ignorado. Desde os planos (20261007000000_planos.sql) esse insert pode ser
-- recusado pelo limite do mês: a recusa chegava tarde (os tokens já estavam
-- gastos) e não ficava em lado nenhum. Agora a aplicação insere a linha de uso
-- primeiro, sem tokens; o gatilho do plano recusa ali, antes de haver custo, e
-- a frase chega à pessoa. Os tokens acrescentam-se a seguir por esta função,
-- porque a tabela não tem update para ninguém em sessão.

create function public.copiloto_registar_tokens(p_uso bigint, p_entrada integer, p_saida integer)
returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  if p_entrada < 0 or p_saida < 0 then
    raise exception 'os tokens não podem ser negativos' using errcode = '22023';
  end if;
  -- Só a própria reserva, só uma vez, e só enquanto é recente: não se reescreve
  -- o custo de perguntas antigas nem o de outra pessoa.
  update public.copiloto_uso
     set tokens_entrada = p_entrada, tokens_saida = p_saida
   where id = p_uso
     and user_id = auth.uid()
     and tokens_entrada = 0 and tokens_saida = 0
     and em > now() - interval '15 minutes';
  return found;
end $$;

revoke execute on function public.copiloto_registar_tokens(bigint, integer, integer) from public, anon;
grant execute on function public.copiloto_registar_tokens(bigint, integer, integer) to authenticated;
