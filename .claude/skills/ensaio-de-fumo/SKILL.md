---
name: ensaio-de-fumo
description: Ensaiar um deploy publicado da plataforma web (pré-visualização ou produção) — o deploy está de pé, as portas que têm de estar fechadas estão fechadas, os cabeçalhos de segurança vão em todas as respostas — e, quando preciso, percorrer o fluxo no browser. Usar depois de cada deploy de produção, antes de etiquetar uma versão web, ou quando a pessoa pergunta se o site está a funcionar.
---

# Ensaio de fumo

Testa o artefacto publicado, não o código-fonte. Um build verde prova que
compila; o ensaio prova que **o que está no ar** responde como deve.

Adaptada da ideia de `release-smoke-test` e `agent-browser`
(akitaonrails/my-skills): ensaiar o artefacto exato, isolado, e relatar o que
se correu com as limitações à vista.

## 1. Ensaio HTTP (sempre)

```bash
cd web && npm run ensaio:fumo -- https://<deploy>
```

Sem dependências, sem criar contas nem dados. Verifica (ver
`web/lib/ensaio/fumo.ts`): a página inicial abre em `pt-PT`; os cabeçalhos de
segurança vão nas respostas; `/entrar` abre; `/app` sem sessão manda para o
login e lembra o destino; os dois crons recusam sem segredo e com um segredo
errado; um caminho inexistente dá 404.

Saída: `0` tudo verde, `1` alguma verificação falhou, `2` **não chegou à
aplicação**. O `2` é para levar a sério, não para contornar:

- *Proteção de Deployments do Vercel* — defina `VERCEL_AUTOMATION_BYPASS_SECRET`.
- *Proxy ou firewall pelo caminho* — a rede de uma sessão de agente costuma
  barrar `*.vercel.app`. Corre o ensaio de outra rede, ou usa a ferramenta
  `web_fetch_vercel_url` do conector do Vercel para ver as respostas página a
  página (com as mesmas expectativas do ensaio).

Uma falha em todas as páginas com 500 costuma ser configuração: sem
`NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, o
`proxy.ts` rebenta em todos os pedidos. Confirma nos logs do deploy antes de
mexer em código.

Uma verificação nova entra em `VERIFICACOES` com um teste em
`fumo.test.ts` — nunca como passo manual nesta skill.

## 2. Fluxo no browser (quando a mudança é de interface ou de sessão)

O Chromium está instalado e o Playwright encontra-o
(`PLAYWRIGHT_BROWSERS_PATH`); se o projeto fixar outra versão do Playwright,
usa `executablePath: '/opt/pw-browsers/chromium'`. Nunca `playwright install`.

Percorre o caminho que a mudança tocou, com uma conta de ensaio (nunca a de
uma pessoa real): entrar, criar empresa, criar e mover uma tarefa no quadro,
abrir o painel, exportar um relatório. Captura de ecrã de cada passo; a
consola do browser sem erros. Num deploy de produção, os dados de ensaio
apagam-se no fim — ou usa a pré-visualização.

## 3. Depois de um deploy de produção

- Migrações: o workflow `Base de dados — produção` verde no mesmo SHA.
- Supabase: `get_advisors` (segurança) sem avisos novos.
- Logs do Vercel sem erros novos desde o deploy.
- Os crons: na hora seguinte, a execução de `/api/cron/emails` respondeu 200
  ou 503 ("envio não configurado"), nunca 401 (segredo trocado) nem 500.

## Relatório

```markdown
## Ensaio de fumo: <url>

- Deploy: <id/SHA> — alvo: pré-visualização | produção
- Ensaio HTTP: <n/n verdes> | barrado por <motivo>
- Browser: <fluxos percorridos, capturas> | não corrido (porquê)
- Pós-deploy: migrações <…>, advisors <…>, logs <…>, crons <…>
- Limitações: <rede, proteção, o que não se pôde ver>
```
