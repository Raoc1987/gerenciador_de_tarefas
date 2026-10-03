---
name: pos-refatoracao
description: Verificação focada depois de uma refatoração, de uma série de limpezas ou de alguns PRs relacionados que entraram — regressões, vulnerabilidades, abstrações duplicadas, valores mágicos, documentação desatualizada, cobertura em falta e testes instáveis no código que mudou. Usar quando a pessoa diz "depois da refatoração", "entraram uns PRs", "verificação de código limpo", sem precisar de uma auditoria conjunta completa. Revê e relata; só corrige se a pessoa pedir.
---

# Pós-refatoração

Responde a uma pergunta: **deixámos o código tocado mais limpo, seguro e
coberto, ou deixámos regressões e dívida para trás?** Não é uma auditoria de
PR e não reabre trabalho já aceite.

Adaptada de `post-refactor` (akitaonrails/my-skills).

## Âmbito

1. O intervalo que a pessoa nomear, exatamente.
2. Senão, depois de um lançamento: desde a etiqueta anterior.
3. Senão, os últimos 3 a 8 commits ou PRs relacionados.
4. Áreas sem relação no intervalo: agrupa por subsistema (base, web, desktop,
   CI) e revê cada grupo à parte.

Não alarga a revisão de arquitetura — para isso há a skill **arquitetura** —
a menos que um achado mostre risco real.

## 1. A superfície que mudou

Intervalo e shortlog; ficheiros por subsistema; mudanças de dependências,
configuração e esquema; testes acrescentados ou alterados; superfícies que o
utilizador vê. Comandos git baratos e leituras focadas, não o repositório
inteiro.

## 2. O gate local

O que o projeto documenta, para as áreas tocadas:

```bash
git diff --check <intervalo>
supabase/tests/correr.sh                       # base
cd web && npm test && npm run typecheck        # web (o build no CI)
python -m pytest                               # desktop
```

Dependências: os alertas do Dependabot e, com registo disponível,
`npm audit`/`pip-audit`. "Ferramenta indisponível" é uma lacuna de prova, não
um "passou".

## 3. O que as refatorações costumam deixar

No código tocado:

- regressões de comportamento: defaults, serialização, fusos, migrações,
  papéis e RLS, tratamento de erros;
- erros engolidos (`catch {}` sem razão escrita, `except Exception: pass`),
  fallbacks que escondem falhas, `!` e `as` para calar o TypeScript;
- lógica duplicada que devia ser uma só — em especial regras que existem no
  desktop e na web e começaram a divergir;
- abstração a mais: tipos, interfaces ou módulos com um único chamador e
  nenhuma necessidade concreta (o teste da eliminação da skill **arquitetura**);
- valores mágicos que deviam ser constantes nomeadas ou configuração;
- comentários e docs que já não descrevem o comportamento (e prosa com ar de
  IA — skill **humanizar**);
- acoplamento escondido entre módulos (`web/lib/dominio` a importar de `app/`,
  o core do desktop a importar a interface — este tem teste);
- perda de dados, operações destrutivas, fuga de segredos, contorno de papéis.

Inclina-te para correções práticas. Não exijas abstração para lógica de uso
único, a menos que a duplicação já esteja a divergir.

## 4. Qualidade dos testes e instabilidade

O comportamento que mudou tem testes focados? Procura: testes de regressão em
falta; testes que verificam a implementação em vez do comportamento; asserts
sem mensagem (o CONTRIBUTING pede que um teste diga o que obteve); dependência
do relógio de parede, da rede, do fuso da máquina, de estado global, de
escrever fora de pastas temporárias, da ordem dos testes; testes que só
passam sozinhos.

Um teste que pareceu instável: corre exatamente esse alvo de novo, uma vez. Se
passar, relata como "transitório observado", com a prova — não como corrigido.

## 5. Classificar

- **BLOQUEANTE** — regressão provável, vulnerabilidade, perda de dados,
  contorno de papéis ou de isolamento, gate vermelho, instabilidade
  reproduzível.
- **DEVE-CORRIGIR** — lacuna de manutenção ou de testes que vai crescer;
  duplicação com risco de divergir; comportamento novo sem teste focado.
- **MIÚDO** — limpeza que pode esperar.
- **OBSERVAÇÃO** — zona verificada e saudável, ou algo a vigiar.

Cada achado: ficheiro:linha, porque importa, a correção ou a próxima
verificação, e se foi confirmado por comando, teste ou leitura.

## 6. Correções

Por omissão, só relata. Se a pessoa pedir para corrigir: lotes pequenos, gate
focado depois de cada um.

## Relatório

```markdown
## Pós-refatoração

Intervalo: <…>
Gate: verde | vermelho | parcial (<o que faltou>)

### Achados
- [SEVERIDADE] <ficheiro:linha> — <problema>. <ação>

### Cobertura e instabilidade
### Código limpo
### Próximo passo
- <uma ação concreta, ou "nenhum">
```

Sem nada a mudar, di-lo diretamente e lista as verificações que passaram.
