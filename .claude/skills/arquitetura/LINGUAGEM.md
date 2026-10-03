# Linguagem

Vocabulário comum de todas as sugestões desta skill. Não trocar por
"componente", "serviço", "API" ou "fronteira" — a consistência é o objetivo.

## Termos

**Módulo** — tudo o que tem interface e implementação, a qualquer escala:
função, ficheiro, pasta, ou uma fatia que atravessa camadas (a importação do
desktop é um módulo: leitor SQLite no browser + `importar_tarefas` na base).
*Evitar*: unidade, componente, serviço.

**Interface** — tudo o que quem chama tem de saber para o usar bem: tipos,
invariantes, restrições de ordem, modos de erro, configuração exigida,
características de desempenho. *Evitar*: API, assinatura (só a parte de tipos).

**Implementação** — o código lá dentro. Distinto de **adaptador**: um
adaptador pode ter implementação grande (o cliente real do Supabase) ou
pequena (um falso em memória nos testes).

**Profundidade** — alavanca na interface: quanto comportamento quem chama (ou
um teste) exercita por unidade de interface que tem de aprender. **Fundo**:
muito comportamento atrás de pouca interface. **Raso**: a interface é quase
tão complexa como a implementação.

**Costura** *(Michael Feathers)* — sítio onde se altera comportamento sem
editar ali; o lugar onde a interface de um módulo vive. Escolher onde pôr a
costura é uma decisão separada do que fica atrás dela. *Evitar*: fronteira
(sobrecarregado pelo contexto delimitado do DDD).

**Adaptador** — algo concreto que satisfaz uma interface numa costura.
Descreve o papel, não o conteúdo.

**Alavanca** — o que quem chama ganha com a profundidade: uma implementação
paga-se em N chamadores e M testes.

**Localidade** — o que quem mantém ganha: mudanças, bugs, conhecimento e
verificação concentrados num sítio. Corrige-se uma vez, fica corrigido em
todo o lado.

## Princípios

- **A profundidade é propriedade da interface, não da implementação.** Um
  módulo fundo pode ser feito de partes pequenas e substituíveis — só não
  fazem parte da interface. Pode ter **costuras internas** (privadas, usadas
  pelos seus próprios testes) além da costura externa.
- **Teste da eliminação.** Imagina apagar o módulo. Se a complexidade
  desaparece, ele não escondia nada (era passagem). Se reaparece em N
  chamadores, merecia existir.
- **A interface é a superfície de teste.** Quem chama e os testes atravessam a
  mesma costura. Se queres testar *por trás* da interface, o módulo tem
  provavelmente a forma errada.
- **Um adaptador é uma costura hipotética; dois é uma real.** Não introduzas
  uma costura sem algo que de facto varie através dela (tipicamente produção e
  teste).

## Relações

Um **módulo** tem uma **interface**; a **profundidade** mede-se contra ela; a
**costura** é onde ela vive; um **adaptador** senta-se na costura e
satisfá-la; a profundidade dá **alavanca** a quem chama e **localidade** a
quem mantém.

## Enquadramentos rejeitados

- **Profundidade como rácio linhas-de-implementação / linhas-de-interface**
  (Ousterhout): premeia encher a implementação. Aqui, profundidade é alavanca.
- **"Interface" como a palavra-chave `interface` do TypeScript ou os métodos
  públicos de uma classe**: estreito demais — interface é tudo o que quem chama
  tem de saber.
