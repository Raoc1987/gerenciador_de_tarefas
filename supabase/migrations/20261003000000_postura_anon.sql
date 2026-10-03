-- O papel `anon` (pedidos sem sessão) não executa nenhuma função do schema
-- public.
--
-- As funções de ajuda da RLS são security definer e o Supabase dá EXECUTE a
-- `anon` por omissão. Nenhuma recebe a identidade de quem pergunta — todas
-- leem auth.uid(), nulo sem sessão — por isso não havia fuga; era uma camada
-- de defesa em falta, e o verificador de segurança do Supabase assinala-a.
-- `anon` também não chega a nenhuma tabela (os revokes das migrações
-- anteriores), por isso as policies nunca precisam destas funções para ele.

revoke execute on function public.e_membro(uuid) from public, anon;
revoke execute on function public.papel_em(uuid) from public, anon;
revoke execute on function public.tem_papel(uuid, public.papel) from public, anon;
revoke execute on function public.ve_todas_as_tarefas(uuid) from public, anon;
revoke execute on function public.pode_ver_tarefa(uuid, uuid, uuid) from public, anon;
revoke execute on function public.pode_escrever_tarefa(uuid, uuid, uuid) from public, anon;

-- Funções de gatilho: só o gatilho as chama, como nas migrações anteriores.
revoke execute on function public.auditoria_imutavel() from public, anon, authenticated;
revoke execute on function public.antes_de_registar_uso() from public, anon, authenticated;

-- E as que vierem: uma função nova em public deixa de nascer executável por
-- `anon`. Quem precisar dela sem sessão tem de o dizer com um grant explícito.
-- São precisos os dois: o EXECUTE para PUBLIC é um privilégio por omissão
-- global, e um revoke dentro de um schema não anula um grant global — só
-- desfaz grants feitos nesse schema, como o do Supabase para `anon`.
-- Vale também para as funções de uma extensão criada depois desta migração:
-- quem as usar precisa de um grant explícito (os testes falham se faltar).
alter default privileges revoke execute on functions from public;
alter default privileges in schema public revoke execute on functions from anon;
