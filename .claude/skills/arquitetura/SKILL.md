---
name: arquitetura
description: Encontrar oportunidades de aprofundamento no código — módulos rasos que deviam ser fundos, regras espalhadas que deviam ter um só sítio, costuras no lugar errado — informadas pelo glossário do domínio e pelos ADRs. Usar quando a pessoa quer melhorar a arquitetura, encontrar refatorações que valem a pena, consolidar módulos acoplados, preparar o terreno para os módulos ERP, ou tornar o código mais testável e mais fácil de navegar por um agente.
---

# Arquitetura

Encontra atrito arquitetural e propõe **aprofundamentos** — refatorações que
transformam módulos rasos em módulos fundos. O objetivo é testabilidade e
navegabilidade, por pessoas e por agentes.

Adaptada de `improve-codebase-architecture` (akitaonrails/my-skills), que
parte de Ousterhout (*A Philosophy of Software Design*) e Feathers (costuras).

## Vocabulário

Usa estes termos, exatamente. Linguagem consistente é o ponto. Definições e
princípios completos em [LINGUAGEM.md](LINGUAGEM.md).

- **Módulo** — tudo o que tem interface e implementação (função, ficheiro,
  pasta, fatia que atravessa camadas).
- **Interface** — tudo o que quem chama tem de saber: tipos, invariantes,
  erros, ordem, configuração. Não só a assinatura.
- **Profundidade** — alavanca na interface: muito comportamento atrás de uma
  interface pequena. **Fundo** vs **raso**.
- **Costura** — onde a interface vive; sítio onde se altera comportamento sem
  editar ali.
- **Adaptador** — algo concreto que satisfaz a interface numa costura.
- **Alavanca** — o que quem chama ganha com a profundidade.
- **Localidade** — o que quem mantém ganha: mudanças, bugs e conhecimento
  concentrados num sítio.

Princípios: **teste da eliminação** (apaga o módulo: a complexidade
desaparece → era passagem; reaparece em N chamadores → merecia existir);
**a interface é a superfície de teste**; **um adaptador é uma costura
hipotética, dois é uma costura real**.

## O que este projeto já decidiu (não re-litigar sem razão forte)

Lê os ADRs da área antes de propor. Os que mais pesam:

- **A autoridade é a base de dados** (ADR-0017) — a costura de segurança é o
  Postgres (RLS, funções, gatilhos). Uma proposta que mova uma regra de acesso
  para TypeScript contraria-o.
- **Núcleo fino e classificação obrigatória** (ADR-0001, ADR-0004) no desktop:
  Core / Module / Plugin / Agent, registado em `CLASSIFICACAO.md`.
- **Só a biblioteca padrão** no desktop (ADR-0002); na web, cada dependência
  entra com uma razão.
- **Copiloto com cliente injetado** (ADR-0018), **carteiro com fila na base**
  (ADR-0019) — já são costuras com dois adaptadores (produção e testes).

Um candidato que contrarie um ADR só aparece se o atrito for real o bastante
para o reabrir, e marcado: *"contraria o ADR-00NN — mas vale reabrir porque…"*.

## Processo

### 1. Explorar

Lê os ADRs da área e o glossário do domínio (empresa, membro, papel, tarefa,
quadro, auditoria, convite, Copiloto, carteiro…; se não existir
`docs/GLOSSARIO.md`, cria-o à medida que os termos se firmam). Depois percorre
o código — com o agente `Explore` em buscas largas — e nota onde há atrito:

- perceber um conceito obriga a saltar entre muitos módulos pequenos?
- módulos rasos, com interface quase tão complexa como a implementação?
- funções puras extraídas só para testar, enquanto os bugs vivem em como são
  chamadas (sem localidade)?
- a mesma regra em dois sítios — o desktop (`src/core/`) e a web
  (`web/lib/dominio/`), ou a interface e a base — que podem divergir?
- partes sem testes, ou difíceis de testar pela interface atual?

### 2. Apresentar candidatos

Lista numerada. Para cada um: **ficheiros**; **problema** (porque o atrito);
**solução** (em linguagem simples); **benefícios** em localidade, alavanca e
em como os testes melhoram. Vocabulário do domínio para o domínio,
vocabulário acima para a arquitetura.

**Não propõe interfaces ainda.** Pergunta: "Qual destes quer explorar?"

### 3. Conversa de desenho

Com o candidato escolhido, percorre a árvore de decisões com a pessoa:
restrições, dependências e a sua categoria ([APROFUNDAR.md](APROFUNDAR.md)),
a forma do módulo aprofundado, o que fica atrás da costura, que testes
sobrevivem. Efeitos à medida que as decisões se firmam:

- um termo novo ou afinado → `docs/GLOSSARIO.md`;
- a pessoa rejeita com uma razão que um explorador futuro precisaria → oferece
  um ADR ("quer que registe isto num ADR para revisões futuras não voltarem a
  sugerir o mesmo?"); razões efémeras não precisam;
- explorar interfaces alternativas → [APROFUNDAR.md](APROFUNDAR.md), secção
  "Desenhar duas vezes".

A implementação de um candidato aceite é trabalho normal (ou, se grande,
**trabalho-profundo**), com a prova planeada em **plano-de-verificacao**.
