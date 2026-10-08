# Para o ALKMIA: o que nasceu no Gerenciador de Tarefas

<!-- Gerado por `python tools/conhecimento.py alkmia --escrever` a partir de
     docs/conhecimento/catalogo.json. Não editar à mão: o teste compara. -->

Catálogo de 2026-10-08. Para ler no início de uma sessão no ALKMIA
(`Raoc1987/ALKMIA`). Daqui nada se escreve lá: cada ponto é uma proposta, e
entra pelo protocolo do ALKMIA (`docs/PROJETO-CRIACAO-SENIOR.md`), começando
por **medir de novo**, porque a medição abaixo tem data e o ALKMIA muda.

Os dois produtos são diferentes. Onde uma decisão do ALKMIA contraria a
daqui (por exemplo o M18, direito de uso na aplicação), ganha a do ALKMIA.

## Falta lá, e serve

### Supabase local sem Docker no CI, com as migrações reais

- **Medido:** 2026-10-08, ALKMIA em cb14227: sem Playwright no CI; o test:rpc corre em pglite, que não é o Postgres do Supabase e não tem GoTrue nem PostgREST
- **Como aplicar:** Copiar a forma de supabase/e2e/levantar.sh: GoTrue e PostgREST fixados por versão e SHA-256, um proxy Node em /auth/v1 e /rest/v1, Postgres do runner, migrações reais, e Playwright sobre o build. GOTRUE_JWT_DEFAULT_GROUP_NAME=authenticated é obrigatório.
- **Onde ver aqui:** `.github/workflows/tests.yml`

### Plano que só muda pelo webhook: assinatura verificada, eventos idempotentes e ordenados, caducidade

- **Medido:** 2026-10-08, ALKMIA em cb14227: BIBLIA §4d, faturação não implementada; profiles.plan escrito por um só sítio, o webhook (M18)
- **Como aplicar:** Pegar no padrão, não no código: verificação HMAC com janela de 5 minutos e várias v1; tabela de eventos para idempotência; ignorar eventos mais antigos do que o último aplicado; a coluna do plano sem update para authenticated e um gatilho de segunda barreira; caducidade alguns dias depois do fim do período. Lá o direito de uso fica na aplicação (M18): o padrão serve na mesma para a escrita do plano.
- **Onde ver aqui:** `docs/architecture/ADR-0025-planos-e-faturacao.md`, provado por `supabase/tests/95_planos.sql`

### Catálogo de práticas validado no CI, com triagem do outro projeto

- **Medido:** 2026-10-08, ALKMIA em cb14227: docs/knowledge-graph.json é JSON inválido e parado em 2026-05-15
- **Como aplicar:** Substituir o knowledge-graph por um catálogo como docs/conhecimento/catalogo.json com validação no CI; a triagem passa a correr nos dois sentidos.
- **Onde ver aqui:** `tools/conhecimento.py`, provado por `tests/test_conhecimento.py`

## Existe em parte

### Migrações por supabase db push, nunca pelo editor SQL

- **Medido:** 2026-10-08, ALKMIA em cb14227: a regra existe (CLAUDE.md §1b), mas nenhum workflow corre supabase db push; aplica-se à mão
- **Como aplicar:** Workflow como .github/workflows/base-de-dados.yml: testes primeiro, CLI fixada por versão e SHA-256, ambiente producao com o segredo, concorrência sem cancelar. E a lição de cá: um run verde sem o segredo não aplicou nada (METODO §1), por isso o passo sem segredo tem de falhar ou avisar de forma visível.
- **Onde ver aqui:** `.github/workflows/base-de-dados.yml`

### Enums da base comparados com as listas da web

- **Medido:** 2026-10-08, ALKMIA em cb14227: 31 listas check (x in (...)) nas migrações; só site/lib/rotas-conhecidas.test.ts extrai uma
- **Como aplicar:** Um teste que extrai cada check (coluna in (...)) das migrações e o compara com a constante TypeScript correspondente, pela mesma ordem, com um mapa coluna→constante. O M5 do ALKMIA já pede isto.
- **Onde ver aqui:** `tests/test_vocabulario.py`

## Por medir antes de decidir

### Exportar e apagar a conta por funções da base, testadas dos dois lados

- **Medido:** 2026-10-08, ALKMIA em cb14227: existe site/app/api/user/delete e o desenho DL1 (registo de apagamento e prova de consentimento); não comparado ainda
- **Como aplicar:** Comparar com o DL1 antes de mexer: lá há dados de saúde (art. 9.º) e prova de consentimento, que aqui não existem. O que pode servir: o apagamento numa só função da base, com confirmação pelo email e o teste das tentativas de forjar o modo.
- **Onde ver aqui:** `docs/RGPD.md`, provado por `supabase/tests/90_rgpd.sql`

## Já existe lá: nada a fazer

### Recusas testadas com o motivo verificado (t.recusa_por)

- **Medido:** 2026-10-08, ALKMIA em cb14227: site/scripts/trainer-rpc-integration.mjs verifica a mensagem (ex.: /não encontrado/.test(erroB))
- **Como aplicar:** Nada a fazer.
- **Onde ver aqui:** `supabase/tests/_ajuda.sql`

## Não se aplica hoje: só se a situação aparecer

### Modos internos numa tabela por transação, em vez de variáveis de sessão forjáveis

- **Medido:** 2026-10-08, ALKMIA em cb14227: nenhum current_setting de variável própria em supabase/migrations
- **Como aplicar:** Só se um dia uma regra tiver de ser desligada durante uma importação ou um apagamento: usar uma tabela num esquema sem acesso pela API, com o id da transação, nunca uma variável de sessão (que qualquer sessão define).
- **Onde ver aqui:** `supabase/tests/90_rgpd.sql`

### Verificar o acesso antes de responder com uma regra

- **Medido:** 2026-10-08, ALKMIA em cb14227: nenhum gatilho before insert/update nas migrações
- **Como aplicar:** Quando houver um gatilho que recuse com uma frase sobre os dados: verificar o acesso primeiro, porque a RLS só atua depois do gatilho.
- **Onde ver aqui:** `supabase/tests/25_hierarquia_dependencias.sql`
