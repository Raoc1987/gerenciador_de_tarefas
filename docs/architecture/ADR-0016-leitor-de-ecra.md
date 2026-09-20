# ADR-0016 — Com Tk 8.6, esta aplicação não se usa com leitor de ecrã

Data: 2026-09-20 · Estado: aceite, e é uma má notícia

## Contexto

O [MEDICOES.md](../MEDICOES.md) tinha, na lista do que continuava por
validar: *"leitor de ecrã: os controlos alcançam-se e o foco vê-se, mas
ninguém verificou o que é **anunciado**"*.

Não é possível ouvir o NVDA a partir daqui. O que se pode fazer — e o que se
fez — é ler **a mesma árvore que ele lê**: a árvore de acessibilidade que o
Windows expõe (MSAA/`IAccessible`). É o dado de onde sai tudo o que um leitor
anuncia. Se lá não estiver, não há nada para anunciar.

## O que a medição diz

Com a janela aberta na aba das Tarefas:

| | |
|---|---|
| Controlos acionáveis e visíveis | **15** |
| Janelas nativas por baixo da janela principal | **78**, todas de classe `TkChild` |
| Dessas, **com nome** na árvore de acessibilidade | **0** |
| Papéis encontrados | `cliente` × 78 — nem um botão, nem um campo, nem uma lista |
| A janela principal | nome `Gerenciador de Tarefas`, papel `cliente`, **1 filho** |

Um leitor de ecrã encontra uma janela com um título, e por baixo dela 78
caixas anónimas indistinguíveis umas das outras. Não há um único botão
anunciável, um único campo de texto, uma única etiqueta.

A causa é conhecida e não está neste repositório: **o Tk desenha os seus
próprios widgets** e, na versão 8.6, não implementa `IAccessible` para eles.
Confirmado na instalação em uso — Tcl/Tk **8.6.15**, sem nenhum comando de
acessibilidade registado.

## Decisão

**Declara-se que a aplicação não é utilizável com um leitor de ecrã, e
diz-se porquê.** Não se finge que um atalho de teclado a mais resolve o
problema.

O que **está** verificado e continua a valer (ver MEDICOES.md): todos os
controlos visíveis se alcançam com `Tab`, o foco vê-se — medido a contar
píxeis — e os atalhos funcionam. Isso serve quem não usa rato. **Não serve
quem não vê.** São duas necessidades diferentes, e o produto só responde a
uma.

A única coisa feita de caminho: **o título da janela passa a dizer a secção**
("Tarefas — Gerenciador de Tarefas"). É o único sítio desta aplicação com
algo que um leitor anuncia, e melhora o alt-tab para toda a gente. **Não é
uma correção de acessibilidade** e não é apresentada como tal.

## O que custaria mudar, para quando a pergunta voltar

Por ordem de custo:

1. **Tcl/Tk 9.** Traz trabalho de acessibilidade que o 8.6 não tem. Custo:
   mudar a versão do interpretador empacotado e voltar a medir tudo — não
   há garantia de que resolva, e a medição acima é a forma de saber.
2. **Uma ponte de acessibilidade como dependência.** Rompe o
   [ADR-0002](ADR-0002-graficos-sem-dependencias.md) (zero dependências de
   execução), que é o que hoje mantém o instalador simples e o produto sem
   cadeia de fornecimento.
3. **Outro toolkit** para a camada de interface. É o custo maior, e é o único
   caminho com resultado garantido. A arquitetura ajuda — a lógica de negócio
   **não vive na interface**, e há testes que o garantem —, mas continua a ser
   reescrever todos os ecrãs.

**Nenhuma destas se faz sem alguém a pedir.** Uma migração de toolkit por
antecipação seria a maior mudança da história deste projeto feita sem um
utilizador concreto do outro lado.

## Consequências

- **O produto não pode ser vendido como acessível**, e qualquer requisito de
  concurso público que exija conformidade (EN 301 549, WCAG aplicado a
  software) **não é cumprido**. É melhor saber-se agora do que num caderno de
  encargos.
- A §60 do plano passa a estar dividida no `PLATAFORMA.md`: navegação por
  teclado **validada**, leitor de ecrã **não suportado**, com este ADR como
  razão.
- A medição fica em `MEDICOES.md` com o método, para poder ser repetida no
  dia em que uma das três opções acima for tentada.

## Nota sobre a medição, que quase saiu errada

O instrumento foi conferido antes de se acreditar nele, e ainda bem: a
primeira versão lia o papel de **todas** as janelas como vazio — incluindo o
do ambiente de trabalho do Windows, que tem um. O índice na tabela de métodos
do `IAccessible` estava em 12, que é o `get_accDescription`; o papel é o 13.
Como o nome (10) estava certo, os nomes saíam bem e o erro passava por
resultado.

Sem essa verificação, este documento teria dito "o Tk não expõe papel nenhum"
com um número errado a apoiá-lo — e chegava à mesma conclusão pelo motivo
errado, que é a pior maneira de ter razão.
