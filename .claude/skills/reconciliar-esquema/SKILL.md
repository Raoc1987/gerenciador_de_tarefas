---
name: reconciliar-esquema
description: Comparar o esquema da base de produção do Gerenciador de Tarefas com o que as migrações produzem, por assinaturas md5 por categoria (tabelas, RLS, funções, políticas, gatilhos, restrições, índices, enums, grants), e isolar o objeto divergente. Usar depois de aplicar migrações, antes de um lançamento, ou quando alguém suspeita de uma alteração feita à mão em produção. Só lê; nunca corrige.
---

# Reconciliar o esquema

Vem do ALKMIA (skill de reconciliação por assinaturas), adaptada. Responde a
uma pergunta que o `supabase migration list` não responde: **o que existe em
produção é o que as migrações produzem?** O histórico diz que migrações
correram; o catálogo diz o que existe (`docs/METODO.md`, R7).

## A lista de categorias vive num sítio só

`supabase/reconciliacao/assinaturas.sql`. Esta skill não a repete. O teste
`supabase/tests/85_reconciliacao.sql` corre-a sobre as migrações a cada PR e
falha se o número de categorias mudar sem ninguém o atualizar: uma consulta
partida ou sem permissão devolve **menos** categorias sem dar erro.

## Procedimento

1. **Confirmar o projeto pelo id.** Nunca o ALKMIA (`rwfxyyreozzbcawftbjt`,
   organização `rdqrmwwnbdfhluxqxglf`). Se o conector do Supabase só vir esse,
   pára aqui e diz que o projeto deste produto não está ligado.
2. **Referência:** correr a consulta sobre as migrações. É o que o
   `correr.sh` faz; para ver as linhas, `VERBOSO=1 supabase/tests/correr.sh`
   e procurar o bloco do `85_reconciliacao.sql`, ou correr o ficheiro à mão
   numa base criada pelas migrações.
3. **Produção:** correr o mesmo ficheiro, tal como está, com o conector
   (`execute_sql`, só leitura) ou com `psql "$SUPABASE_DB_URL" -f`.
4. **Comparar categoria a categoria.** Três desfechos, nunca dois:
   - assinatura igual: nada a fazer;
   - assinatura diferente: deriva, ir ao passo 5;
   - categoria só de um lado: deriva da **consulta** (versão ou permissão),
     não da base. Reportar e parar.
5. **Isolar o objeto:** na categoria divergente, correr só o CTE dessa
   categoria nos dois lados (sem o `md5`, com as linhas) e comparar as
   linhas. Comparar sempre o **corpo** (`prosrc`, `qual`, a definição), nunca
   um comentário.
6. **Classificar a origem**, com a confiança:
   - existe em produção e não nas migrações: alteração à mão em produção, ou
     migração local por fazer;
   - existe nas migrações e não em produção: migração por aplicar (confirmar
     com `supabase migration list` e o run do `base-de-dados.yml`, sabendo
     que um run verde não prova que aplicou);
   - existe nos dois com corpo diferente: alguém editou em produção, ou uma
     migração aplicada foi editada depois (proibido pelo `CLAUDE.md`).

## O que não faz

- Não compara **dados**, só estrutura.
- Não vê objetos fora das categorias do SQL. Uma categoria nova acrescenta-se
  no SQL e no número esperado do teste, na mesma alteração.
- Não prova que as migrações correram: prova que o estado final coincide.
- **Não escreve na base.** A correção é uma migração nova, por PR.
