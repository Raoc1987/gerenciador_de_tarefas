---
name: clonar-dependencias
description: Trazer para uma pasta local ignorada o código-fonte de 1 a 3 dependências centrais (Next.js, React, supabase-js, @supabase/ssr, o SDK da Anthropic, o Postgres/Supabase CLI) na versão exata que o projeto usa, para ler a implementação em vez de confiar na memória. Usar quando a pessoa pede para inspecionar o interior de uma biblioteca, depurar um comportamento que a documentação não explica, ou confirmar uma API que muda depressa. Não para perguntas que a documentação oficial responde.
---

# Clonar dependências

Torna legível, localmente, o código de um punhado de dependências que
importam. A regra que justifica a skill: **APIs que mudam depressa
confirmam-se na fonte, nunca de memória** — Next 16 (`proxy.ts`, `params`
assíncronos), React 19, `@supabase/ssr`, a API do Claude. Uma resposta
sustentada por um ficheiro concreto da versão instalada vale mais do que um
exemplo de blog de uma versão antiga.

Adaptada de `clonedeps` e da regra de "fonte da verdade" de `effect`
(akitaonrails/my-skills).

## 1. Estado existente

Lê `.dependencias/manifesto.json` se existir. Reutiliza os clones que já
servem a tarefa; só planeia de novo se o manifesto faltar, estiver
desatualizado (versão diferente da que o `package.json` resolve) ou não
chegar.

## 2. Plano — pequeno

Percebe primeiro o projeto e a tarefa. Recomenda um repositório só quando o
seu código for mais útil do que a documentação e do que este repositório.
**0 a 3 recomendações fortes** valem mais do que 5 fracas; se nada precisa de
ser clonado, di-lo. Para cada uma:

- nome, URL oficial (HTTPS), a versão que o projeto usa (do `package.json` ou
  do lockfile, quando existir) e a etiqueta ou commit correspondente;
- a subpasta, se for um monorepo (`packages/next`, `packages/ssr`, …);
- porque ajuda, quando, e ressalvas (repositório enorme, etiqueta em falta,
  correspondência de versão incerta).

Nada de dependências minúsculas, transitivas ou só de desenvolvimento, a menos
que sejam o assunto da tarefa.

## 3. Verificar e confirmar

1. Confirma a referência: `git ls-remote <url> refs/tags/<etiqueta>`.
2. Prefere etiquetas ou SHAs fixos. Sem etiqueta exata, explica o recurso.
3. Só URLs HTTPS de forjas públicas. Recusa `file://`, SSH, caminhos locais,
   URLs com credenciais e repositórios privados sem aprovação explícita.
4. Mostra o plano à pessoa e pede confirmação antes de clonar, a menos que ela
   tenha pedido para clonar já.

## 4. Clonar

Para `.dependencias/repos/<dono>__<repo>/` (`/` → `__`, sem `.git`). Um
monorepo clona-se uma vez, com várias entradas no manifesto a apontar para
subpastas diferentes.

```bash
git ls-remote https://github.com/vercel/next.js refs/tags/v16.0.0
git clone --depth 1 --branch v16.0.0 --no-recurse-submodules --filter=blob:none \
  https://github.com/vercel/next.js .dependencias/repos/tmp-vercel__next.js
mv .dependencias/repos/tmp-vercel__next.js .dependencias/repos/vercel__next.js
```

Para um monorepo enorme, clona esparso só a subpasta
(`--sparse` + `git sparse-checkout set packages/next`). Antes de reutilizar um
clone existente, confirma que `git remote get-url origin` é o URL aprovado. Um
clone que falhou apaga-se. **Nunca** corras install, build ou testes de um
repositório clonado.

## 5. Manifesto

`.dependencias/manifesto.json`:

```json
{
  "atualizado": "2026-10-03T00:00:00Z",
  "dependencias": [
    {
      "nome": "next",
      "versao": "16.0.0",
      "repo": "https://github.com/vercel/next.js",
      "ref": "v16.0.0",
      "caminho": ".dependencias/repos/vercel__next.js",
      "subpasta": "packages/next",
      "porque": "proxy.ts e params assíncronos do App Router"
    }
  ]
}
```

Se um clone falhar depois de outros terem corrido, escreve o manifesto dos que
correram.

## 6. Ignorar e registar

`.dependencias/` está no `.gitignore` (acrescenta se não estiver): os clones
são de uma sessão, não do projeto. Numa sessão na cloud o contentor é
efémero — os clones desaparecem com ele, e voltam a clonar-se na próxima.

Não editas os clones. Quando usares uma resposta tirada deles, cita o ficheiro
e a versão (`packages/next/src/server/…@v16.0.0`).

## Limpar

A pedido: apaga `.dependencias/`.
