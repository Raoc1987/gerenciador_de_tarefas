# ADR-0007 — Uma política só pode recusar

Data: 2026-09-15 · Estado: aceite

## Contexto

O RBAC responde a *"podes concluir tarefas?"*. Toda a regra de acesso que uma
empresa realmente precisa tem a outra forma: *"podes concluir **esta**?"*. É a
diferença entre ter a chave do arquivo e poder mexer numa pasta em concreto.

Parte disto já estava resolvida, e da maneira certa: quem vê que tarefas
decide-se em `tarefas_servico`, a partir da hierarquia. O que faltava era o
caso geral — uma regra que olhe para os **atributos** do objeto (de quem é,
se está concluído, de que unidade é, quando vence) e recuse, sem que o núcleo
saiba o que é uma tarefa.

Havia um risco óbvio em construir isto: um motor de regras genérico sem
nenhuma regra real é a mesma coisa que uma API sem consumidor — a razão pela
qual a API está parada (ver `CLASSIFICACAO.md`). Por isso o mecanismo entra
com uma política a sério a usá-lo.

## Decisão

Um **Pedido** é o par `(ação, objeto)`: `Pedido("concluir", "tarefa", {...})`.
Não é só o objeto. Fingir que a permissão já é a ação obrigaria a inventar uma
permissão nova sempre que se quisesse distinguir "editar" de "apagar" — e a
granularidade dos papéis passaria a ser decidida pelas políticas, que é
exatamente ao contrário.

Uma **Política** é uma função `(sessão, pedido) → motivo | None`, registada
com as ações e os tipos a que se aplica. Três propriedades, nenhuma
negociável:

1. **Só recusa. Nunca concede.** É o que torna seguro deixar um plugin
   registar uma. Uma política mal escrita, no pior caso, tranca alguém de fora
   — visível, reclamável, corrigível. Se pudesse conceder, o pior caso era
   abrir uma porta em silêncio, e ninguém repara numa porta aberta.
2. **Corre depois do papel.** Se o RBAC já disse não, nenhuma política chega a
   ser avaliada. Não há nada a recusar, e não se paga o custo.
3. **Rebenta fechada.** Uma política que levanta uma exceção recusa, com
   registo. Uma regra de acesso partida não pode passar por regra bem
   sucedida.

O motivo devolvido é uma **chave de tradução**, não uma frase: a razão aparece
a quem foi recusado, e esta aplicação fala três línguas. Uma recusa sem razão
é a pior resposta que este módulo pode dar.

`exigir` publica `politica.recusou`, que a auditoria regista. É o que separa
um controlo de um obstáculo: um obstáculo impede e cala-se; um controlo impede
e deixa registo. `pode` **não** publica — a interface chama-o para decidir se
desenha um botão, e registar cada pergunta encheria a trilha de ruído até as
tentativas a sério não se encontrarem lá dentro.

### Onde as políticas se registam

Em `tarefas_servico`, ao importar — não no arranque da interface. Esse módulo
é a porta única para escrever numa tarefa (garantido por
`tests/test_arquitetura.py`), e uma regra de acesso que só existe quando a
janela existe não é uma regra de acesso: um plugin, um teste ou uma futura API
escreveriam sem ela. **A porta traz as suas próprias fechaduras.**

### A primeira política: segregação de funções

Quem cria uma tarefa não a dá por concluída. É o controlo clássico: quem
levanta o trabalho não é quem certifica que ficou feito.

- **Nasce desligada.** Numa boa parte das instalações a pessoa que cria a
  tarefa é a mesma que a faz; ligá-la por omissão tirava a toda a gente a
  capacidade de fechar o próprio trabalho. Uma funcionalidade nova não muda o
  que já funcionava.
- **Não há exceção para o administrador.** Um controlo de segregação que o
  dono da instalação contorna não é um controlo. O caminho para fechar uma
  tarefa própria é outra pessoa fechá-la — ou desligar a funcionalidade, e
  desligá-la fica na trilha, que é precisamente o que um auditor quer ver.
- **Reabrir continua a ser possível.** Travar o caminho de volta seria uma
  armadilha, não um controlo.
- **As tarefas sem dono não são abrangidas.** São as anteriores às contas;
  ninguém as criou, por isso ninguém certifica o próprio trabalho ao fechá-las.

## Consequências

**Boas**

- Regras de negócio sobre acesso deixam de ter de ser espalhadas por `if`s na
  interface e nos serviços: há um sítio, e ele é auditável.
- Um módulo pode trazer as suas regras sobre os seus objetos sem que o núcleo
  aprenda o domínio dele — a mesma inversão das permissões de módulos.
- Os 42 pontos de chamada de `pode`/`exigir` não mudaram: o parâmetro é
  opcional e, sem ele, a resposta é a do papel, como sempre foi.

**Custos**

- Mais uma coisa a saber ao ler uma recusa: "o papel não dá" e "o papel dá mas
  este caso não" passam a ser respostas diferentes. São mesmo diferentes —
  mas quem diagnostica tem de distinguir as duas.
- Uma política corre a cada `exigir` com pedido. São funções puras sobre um
  dicionário pequeno; se um dia deixarem de ser, isto volta a esta mesa.
- `pode(permissao, pedido)` e `exigir(permissao, pedido)` obrigam quem chama a
  montar o pedido, e um pedido montado com o atributo errado dá uma decisão
  errada em silêncio. Por isso as tarefas têm `pedido_sobre()`: quem chama não
  escolhe os atributos à mão.

## O que ficou de fora, e porquê

- **Políticas guardadas em dados** (uma tabela de regras editável na interface)
  em vez de funções em código. Seria a forma completa do ABAC, e é a
  continuação natural. Não entra hoje porque uma linguagem de regras é uma
  superfície pública — assim que alguém guardar regras, elas têm de continuar
  a funcionar — e ainda não há uso real que diga que forma ela deve ter.
- **Políticas que concedem.** Não é uma questão de esforço: é a propriedade que
  torna o resto seguro. Se um dia for preciso conceder por atributo, isso é
  uma permissão nova ou um papel novo, decidido por quem administra.
