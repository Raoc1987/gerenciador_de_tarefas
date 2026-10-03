# Modelo de ameaças — Gerenciador de Tarefas (web)

Lista de cobertura, não substituto de seguir os dados. Cada entrada nomeia o
controlo que **devia** existir e onde vive; a auditoria verifica se todos os
caminhos passam por ele. Quando o código mudar, este ficheiro muda com ele.

## Ativos

- Tarefas, comentários e membros de cada empresa — o dado dos clientes.
- A auditoria (`auditoria`): imutável, e com a empresa do momento.
- Tokens de convite e endereços de email (`convites`, `emails_pendentes`).
- `SUPABASE_SERVICE_ROLE_KEY` — contorna a RLS. Só em
  `web/lib/supabase/servico.ts`, só importada por `app/api/cron/` (ADR-0019;
  guardado por `web/lib/arquitetura.test.ts`).
- `CRON_SECRET`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY` — só no servidor.
- A faturação indireta: chamadas ao Claude (limite diário em `copiloto_uso`)
  e emails enviados (reputação do domínio remetente).

## Atores

| Ator | O que pode legitimamente |
|---|---|
| Anónimo (`anon`) | Ver as páginas públicas e entrar. **Nada** na base: sem tabelas, sem funções (`80_postura_seguranca.sql`). |
| Membro por papel | Leitor < colaborador < supervisor < gestor < administrador < proprietário (`web/README.md`, enum `papel`). |
| Membro de **outra** empresa | Nada da empresa alheia — nem contagens, nem existência. |
| Quem tem um link de convite | Aceitar esse convite, uma vez, dentro do prazo, como a conta em sessão. |
| O Vercel Cron | Chamar `/api/cron/*` com `Authorization: Bearer <CRON_SECRET>`. |
| O Copiloto (modelo) | Ler como a pessoa que pergunta; **propor**, nunca escrever (ADR-0018). Influenciável por qualquer texto que lê. |
| O ficheiro `tarefas.db` importado | Entrada hostil por defeito: lido no browser, só as tarefas seguem (ADR-0020). |
| Contribuidor de PR, dependência, Action | Código que corre no CI e no build. |

## Pontos de entrada e controlos

1. **PostgREST e Realtime diretos**, com a chave publishable — o caminho que
   ignora a interface. Controlo: RLS em todas as tabelas, revokes de
   INSERT/UPDATE/DELETE onde a escrita é só por função, funções security
   definer com `search_path` fixo e verificação de papel **dentro** da função.
   Verificar: cada policy usa `auth.uid()` e o papel na empresa da linha; nada
   confia em colunas que o cliente escreve (`empresa_id`, `criada_por`,
   `responsavel_id`) sem a validar no gatilho; o Realtime só entrega o que a
   RLS deixa ler.
2. **Server Actions** (`web/app/**/acoes.ts`). Controlo: correm como a pessoa
   em sessão; a base decide. Verificar: nenhuma usa a chave de serviço; erros
   não vazam detalhes da base.
3. **Funções RPC** (`criar_empresa`, `aceitar_convite`, `alterar_papel`,
   `remover_membro`, `importar_tarefas`, `indicadores_painel`, …). Verificar:
   papel mínimo; não se promover a si próprio nem acima do próprio papel; a
   empresa nunca fica sem proprietário; limites de tamanho (`importar_tarefas`
   recusa lotes acima de 1000); o modo `gdt.importacao` não fica ligado.
4. **Rotas de cron** (`web/app/api/cron/*`). Controlo: `pedidoAutorizado`
   (`web/lib/emails/cron.ts`) — tempo constante, segredo com 16+ caracteres,
   sem segredo ninguém entra. Verificar: nenhuma outra rota usa a chave de
   serviço; `reclamar_emails` com `skip locked` e idempotência por chave.
5. **Autenticação** (`/entrar`, `/auth/callback`, `/sair`). Controlo:
   `caminhoSeguro` em `seguinte` (redirecionamento aberto), Supabase Auth.
   Verificar: o callback não aceita destinos externos; URLs de redirecionamento
   do Supabase restritos ao site.
6. **Convites** (`/convite/[token]`). Verificar: token com entropia suficiente,
   uso único, expiração, o email do convite vs a conta que aceita, papel do
   convite não acima de quem convidou.
7. **Copiloto** (`web/lib/copiloto/`, `lib/dominio/copiloto.ts`). Ameaça:
   **injeção de instruções** num título, descrição ou comentário de tarefa que
   o modelo lê. Controlo: ferramentas só de leitura, executadas com a sessão de
   quem pergunta; `propor_alteracoes` só devolve propostas validadas por
   `validarProposta`, aplicadas pela pessoa pelo caminho de um formulário;
   limite diário; máximo de voltas. Verificar: nenhuma ferramenta escreve;
   nenhuma proposta contorna a validação; o texto das tarefas não chega ao
   prompt de sistema; erros do modelo não vazam a chave.
8. **Importação do desktop** (`web/lib/importacao/`). Ameaça: SQLite
   malformado (páginas fora do ficheiro, ciclos, tamanhos enormes), payloads
   nos campos. Controlo: leitor escrito à mão, no browser, com limites;
   `importar_tarefas` revalida tudo. Verificar: limites de recursão e tamanho
   no leitor; lotes por tamanho (~800 KB) abaixo do limite das Server Actions.
9. **Exportações** (`web/lib/relatorios/`). Ameaça: **injeção de fórmulas**
   em CSV/XLSX (`=`, `+`, `-`, `@`, tab, CR no início de uma célula), texto
   que quebra o PDF. Controlo: neutralização no CSV (ADR-0021). Verificar: o
   XLSX também (células `inlineStr`, nunca fórmulas); escape de XML; o PDF
   escapa parênteses e barras.
10. **Emails** (`web/lib/dominio/emails.ts`, carteiro). Ameaça: HTML/links
    injetados por títulos ou nomes. Controlo: `escapar` em tudo o que entra no
    HTML. Verificar: todo o interpolado passa por `escapar`; o assunto não
    leva quebras de linha; os links apontam para `urlDoSite()`.
11. **Cabeçalhos HTTP** (`web/next.config.ts`). Verificar: `X-Frame-Options`,
    `nosniff`, `Referrer-Policy`, `Permissions-Policy` em todas as respostas
    (o `npm run ensaio:fumo` prova-o num deploy); CSP fica pendente até haver
    domínio fixo — é risco residual a declarar.
12. **CI, build e deploy** (`.github/workflows/`, `vercel.json`,
    `supabase/config.toml`). Verificar: permissões mínimas; Actions fixadas por
    SHA; a CLI do Supabase fixada por versão e SHA-256; `SUPABASE_DB_URL` só no
    ambiente `producao`; nada de `pull_request_target` com checkout do PR.
13. **Desktop** (`src/`), quando no âmbito: base SQLite local, plugins pelo
    `ContextoPlugin`, atualizações e instalador assinados pelo processo de
    release (`tools/verificar_versao.py`).

## Indicadores de código malicioso

Leads, não prova: novos destinos de rede ou telemetria; leitura de
credenciais, `~/.`, metadados da cloud; `eval`, `new Function`, imports
dinâmicos de URL; blobs base64/hex; Unicode bidi ou homóglifos; ativação por
data, utilizador ou CI; contas ou chaves escondidas; desligar testes, RLS,
TLS, auditoria ou limites; mocks que escondem efeitos reais; limpezas
destrutivas fora do projeto.
