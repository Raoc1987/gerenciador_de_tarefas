---
name: dependencias
description: Tratar PRs de atualização de dependências do Dependabot (npm da web, pip das ferramentas, GitHub Actions) depressa e com segurança — consolidar num só commit, resolver para a versão compatível mais recente, verificar o lote inteiro uma vez, e deixar cada PR não consolidado com uma decisão visível. Só para PRs de bot que tocam apenas em metadados de dependências; o resto vai para a auditoria-pr.
---

# Dependências

Limpa os PRs de atualização sem partir a aplicação e sem levar alterações
locais por arrasto. Vários PRs de atualização são **uma** unidade de trabalho:
consolidar, resolver tudo para a versão compatível mais recente, verificar o
conjunto com uma corrida de testes, corrigir o que isso expuser em commits a
seguir. Testar e fazer merge um a um é exatamente o desperdício a evitar.

Adaptada de `pr-bump` (akitaonrails/my-skills). O `.github/dependabot.yml`
já agrupa as atualizações menores da web num PR semanal.

## Os três ecossistemas deste repositório

| Ecossistema | Onde | O que muda | Cuidados |
|---|---|---|---|
| npm | `web/package.json` (+ `package-lock.json` quando existir) | dependências da plataforma web | build e typecheck só no CI aqui (sem registo npm na sessão) |
| pip | `requirements-dev.txt` | ferramentas de teste e empacotamento | **`requirements.txt` fica vazio** — a aplicação desktop só usa a biblioteca padrão (ADR-0002), e há um teste que o garante |
| github-actions | `.github/workflows/*.yml` | Actions fixadas por SHA | o SHA novo tem de corresponder à etiqueta que o comentário diz (`# vX.Y.Z`) |

## Guardas

- Nunca commitas alterações locais alheias: vê `git status --short --branch`,
  `git diff --stat` e o diff dos ficheiros pretendidos antes do commit.
- Um PR que mexa em código, migrações, workflows além do `uses:`, ou
  configuração que não seja metadado de dependência **não é desta skill**:
  vai para a **auditoria-pr**.
- Nada de formatadores automáticos como "correção". Se o lint falhar por
  estilo antigo, correção pequena e dirigida.
- **Chão da cadeia de fornecimento**: antes de atualizar, confirma que cada
  pacote vem do registo público por omissão (npm, PyPI, github.com para
  Actions) com o nome e versão esperados. Fontes git/path, pacotes renomeados
  ou republicados, nomes vizinhos de pacotes conhecidos, ou **hooks de
  instalação novos** (`preinstall`, `postinstall`, `prepare`) na resolução →
  pára e passa à **auditoria-pr**. Um lockfile bem formado com um pacote
  envenenado passa em todas as verificações de forma.
- Uma Action: o SHA novo tem de existir no repositório da Action e
  corresponder à etiqueta (`git ls-remote https://github.com/<dono>/<repo> refs/tags/<etiqueta>`).
- **Fecha o ciclo de cada PR que NÃO consolidas.** "Adiar", "passar à
  auditoria" ou "recusar" é uma decisão, não um estado: comenta no PR porque
  não entrou (versão maior, build partido, ficheiros a mais, origem suspeita)
  e fecha-o ou liga-o a uma issue de seguimento. Mencioná-lo só no resumo não
  conta.

## Passos

1. **Inventário** — `gh pr list --state open --json number,title,headRefName,author,labels,mergeStateStatus,isDraft,url`
   e, por candidato, `gh pr diff <N> --name-only` e o estado dos checks. Sinais
   de rotina: autor `dependabot[bot]`, só metadados, versão menor ou de
   correção. Um CI vermelho no ramo do Dependabot pode ser lockfile parcial —
   não conclui que a atualização é má antes de a consolidação falhar.
2. **Consolidar na ponta da main**, num ramo novo:
   - npm: `cd web && npm install <pkg>@latest …` dentro dos intervalos do
     `package.json` (sem alargar intervalos nem saltar versões maiores sem a
     pessoa pedir). Sem registo npm na sessão, o lockfile é gerado pelo CI ou
     pela pessoa — di-lo.
   - pip: atualiza `requirements-dev.txt` para a versão mais recente
     compatível.
   - Actions: troca o SHA e o comentário da etiqueta, em todos os workflows
     que usam a Action.
   O objetivo é "a mais recente segura", não a versão exata do PR: menos
   atualizações minúsculas a seguir.
3. **Verificar uma vez, o lote inteiro** — o gate das áreas tocadas
   (`npm test`/`typecheck`, `pytest`, e para Actions o CI). Falhou: reproduz,
   decide se é a dependência, o ambiente ou fragilidade antiga; correção mínima
   num commit à parte; **corrige para a frente** — não desfaças o lote em
   merges individuais. Para isolar um culpado, usa uma árvore de rascunho e
   exprime o resultado no lote (fixar versão, ajustar intervalo, corrigir código).
4. **Commit e push** — só os ficheiros pretendidos; mensagem
   `chore(deps): …` com `Closes #N` por PR consolidado. O `Closes` só fecha
   quando o commit chega ao ramo por omissão — confirma qual é
   (`gh repo view --json defaultBranchRef`). Correções de testes ou CI num
   commit separado.
5. **Depois do push** — confirma que os PRs fecharam e espera pelo CI no SHA
   exato. Deploy só com CI verde e só se pedido.

## Relatório

- PRs fechados.
- Versões diretas e transitivas mudadas, assinalando quando a final é mais
  recente do que a proposta pelo Dependabot.
- Verificações locais e resultado; CI.
- PRs não consolidados e **o estado em que ficaram** (comentado e fechado, ou
  comentado e seguido na issue #N).
- Alterações locais deixadas intencionalmente de fora.
