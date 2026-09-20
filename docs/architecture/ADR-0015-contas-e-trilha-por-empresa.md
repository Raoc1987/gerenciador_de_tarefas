# ADR-0015 — As contas e a trilha seguem a regra que as tarefas já seguiam

Data: 2026-09-20 · Estado: aceite

## Contexto

O `PLATAFORMA.md` registava, na §44: *"auditoria, contas e configuração
continuam por isolar"*. Fui medir antes de mexer, numa instalação com duas
empresas e a Ana como administradora **dentro da Acme**:

| O que a Ana conseguia | |
|---|---|
| ver o nome e o papel de `bruno_secreto`, empregado da Rival | sim |
| ver na trilha o que ele tinha feito | sim |
| **mudá-lo para a Acme** | sim |
| **desativá-lo** | sim |
| **apagar-lhe a conta** | sim |
| **repor-lhe a palavra-passe** — que é entrar na conta dele | sim |

As tarefas dela já estavam isoladas. As contas e a trilha não.

## A leitura fácil deste achado está errada

A primeira explicação que me ocorreu foi "falta um papel de administrador de
empresa". Não falta. Ler contas exige `utilizadores.gerir` e ler a trilha
exige `sistema.admin` — as duas só as tem `administrador`, que é o papel do
dono da instalação e concede **tudo**.

O que se estava a ver não era um papel em falta. Era **uma regra aplicada a
um sítio e não aos outros**: o produto já decidiu que *o âmbito dos dados é a
empresa de quem está em sessão, seja qual for o papel* — é o que
`empresa_da_sessao()` diz, e é por isso que as tarefas da Ana já estavam
certas. As contas e a trilha simplesmente não perguntavam.

## Decisão

**As contas e a trilha passam pelo mesmo `empresa_da_sessao()` que as tarefas
e os dados dos módulos.**

1. `utilizadores.listar()` devolve as contas da empresa da sessão.
2. `definir_papel`, `definir_unidade`, `definir_ativo`, `remover` e
   `alterar_senha` **levantam** `ContaDeOutraEmpresaError` sobre uma conta de
   outra empresa. Levantam, e não devolvem `False`: um `False` silencioso
   deixava quem administra a pensar que a alteração tinha resultado.
3. `definir_unidade` verifica também o **destino**. Sem isso faltava metade —
   não mexer nas contas deles, mas poder mandar as minhas para lá é a mesma
   fuga vista do outro lado.
4. A auditoria grava `empresa_id`: a empresa de quem agiu, **no momento em
   que agiu**. Pela mesma razão que a tarefa grava a unidade — se a pessoa
   mudar de empresa amanhã, o que fez continua a pertencer a onde foi feito.

### O que fica de fora, e porquê

**`obter()` não é filtrado.** É o que a autenticação usa para encontrar a
conta *antes* de haver sessão; filtrá-lo trancava toda a gente fora da
aplicação. Quem souber o nome exato de alguém de outra empresa consegue ler-lhe
a linha. O que está fechado é descobri-lo (`listar`) e mexer-lhe (tudo o
resto).

**As contas sem lugar na estrutura continuam visíveis e administráveis.**
`criar()` não recebe unidade: toda a conta nasce sem lugar, e alguém tem de
lho poder dar. Consequência: um administrador de empresa pode mexer na conta
de quem administra a instalação. `_garantir_que_sobra_administrador` impede
que a última seja apagada, mas não é isolamento — é outro controlo a apanhar
o caso pior. Fica dito como está.

## A escolha difícil: linhas de trilha sem empresa

Uma linha gravada por quem administra a instalação fica com `empresa_id`
nulo. Pode ser vista por todos, ou só por quem também não tem empresa. As
duas hipóteses custam alguma coisa:

* **visível a todos** — o `alvo` pode ser o nome de um empregado de outra
  empresa. Um administrador da Acme lê "alguém desativou `bruno_secreto`" e
  fica a saber que existe um `bruno_secreto`;
* **só para quem administra a instalação** — um auditor da Acme não vê o que
  o dono da instalação fez dentro da Acme.

**Escolheu-se a segunda**, porque entre deixar escapar o nome de um empregado
de outro cliente e esconder de um auditor uma ação do dono da instalação, o
primeiro é o que não se pode desfazer.

Ao contrário das tarefas, portanto: uma tarefa sem unidade é histórico que
ninguém pode perder de vista e fica visível a todos; uma linha de trilha sem
empresa não. As duas regras são diferentes de propósito, porque as duas
perguntas são diferentes.

## Consequências

**O que se ganha.** Fecha a §44 no que ela tinha de real. O que era possível
antes — apagar a conta de um empregado de outro cliente — deixa de ser.

**O que isto custa, e fica dito.**

- **Quem está dentro de uma empresa deixa de poder montar a estrutura de
  outra.** É a regra a funcionar, mas apanhou dois testes existentes que
  faziam a configuração já dentro da sessão da Ana. Quem monta uma instalação
  multiempresa administra-a **de fora do organigrama**.
- **Com o seletor de empresa ([ADR-0014](ADR-0014-seletor-de-empresa.md))
  estreitado, também não se administra fora dele.** Enquanto se está dentro
  de uma empresa, age-se *como* ela. A saída é voltar a "todas as empresas".
- **As linhas de trilha anteriores à v14 ficam com `empresa_id` nulo**, e
  passam a ser lidas só por quem administra a instalação. Deduzir-lhes a
  empresa a partir da conta de hoje seria reescrever o passado a cada mudança
  de organigrama. Numa instalação com uma empresa ou nenhuma **não muda nada**:
  o filtro nunca chega a aplicar-se.

## A parte da §44 que não existia

A mesma linha do `PLATAFORMA.md` dizia "configuração". Fui ver o que lá está:
modo claro/escuro e idioma são preferências **da pessoa ou da máquina**;
retenção da auditoria e funcionalidades ativas são decisões **da instalação**.
Nenhuma chave é de uma empresa.

**Não havia nada para isolar**, e a linha do documento estava errada. Inventar
configuração por empresa para cumprir uma frase seria construir uma
funcionalidade a partir de um erro de escrita.
