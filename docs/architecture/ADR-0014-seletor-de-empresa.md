# ADR-0014 — O seletor de empresa estreita, nunca alarga

Data: 2026-09-20 · Estado: aceite

## Contexto

O [ADR-0011](ADR-0011-isolamento-entre-empresas.md) isolou as tarefas por
empresa e o [ADR-0012](ADR-0012-dados-de-modulo-por-empresa.md) os dados dos
módulos. Os dois resolvem a mesma metade do problema: **quem pertence a uma
empresa só vê a dela.**

Faltava a outra metade, e o `PLATAFORMA.md` registava-a: **quem não pertence a
empresa nenhuma vê todas ao mesmo tempo, misturadas.** É o caso de quem
instala e administra sem se pôr no organigrama — e é exatamente quem precisa
de conseguir olhar para uma empresa de cada vez, porque é quem tem de resolver
um problema num cliente sem ver os dados dos outros ao lado.

## A parte difícil não é mostrar uma lista

Um seletor de empresa mal feito é uma **escalada de privilégio com ar de
menu.** Se a interface pudesse dizer "agora estou na Rival" e o núcleo
obedecesse, alguém limitado à Acme via a Rival carregando num botão — e o
isolamento inteiro dos dois ADRs anteriores valia zero.

## Decisão

**O seletor filtra dentro do alcance. Não define o alcance.**

1. `organizacao.empresas_ao_alcance()` responde **o que esta sessão já pode
   ver**. Para quem pertence a uma empresa, é só essa. Para quem não está na
   estrutura, são todas.

2. `organizacao.escolher_empresa(id)` **levanta `EmpresaForaDoAlcanceError`**
   se o id não estiver nessa lista. Recusa em vez de ignorar: ignorar deixava
   a interface a mostrar um nome e os dados de outro, que é a pior das três
   respostas possíveis.

3. A escolha entra em `empresa_da_sessao()` **depois** da empresa da conta:

   ```
   empresa da conta  →  se existe, é essa e não há escolha
   escolha da sessão →  só para quem não tem empresa fixa
   ```

   Como tudo — tarefas e dados de módulos — já passava por
   `empresa_da_sessao()`, nada mais precisou de mudar. É o retorno do refactor
   do ADR-0012, que pôs esta decisão num sítio só.

4. **O seletor com menos de duas empresas não aparece.** Um controlo que
   promete uma escolha que não existe é pior do que nenhum controlo.

### A escolha é de quem a fez, e é revalidada a cada leitura

Guarda-se `(utilizador, empresa)` e não só a empresa. Sem o nome, a escolha da
Ana sobrevivia ao fim da sessão dela e passava a valer para quem entrasse a
seguir — numa empresa onde duas pessoas partilham um computador, que é o caso
normal. E o pior é que não daria erro: a pessoa veria menos, e acharia que era
o que havia.

E revalida-se ao ler, em vez de confiar no que ficou guardado: o alcance de
alguém pode encolher com a escolha de pé — é o que acontece quando se põe no
organigrama quem administrava de fora. Uma escolha que deixou de ser válida
vale o mesmo que nenhuma.

## Consequências

**O que se ganha.** Fecha a §44. Quem administra a instalação inteira passa a
poder olhar para um cliente de cada vez, e o número que vê no painel tem um
nome ao lado que diz de quem é. A §10 deixa de ter o "seletor de contexto" em
falta.

**O que isto custa, e fica dito.**

- **Não persiste entre arranques.** É contexto de sessão, como quem está
  autenticado. Guardá-lo faria alguém voltar no dia seguinte a uma vista
  estreitada que já não se lembra de ter escolhido. É fácil de mudar se
  alguém pedir — e a revalidação já lá está, que era a parte difícil.
- **Não há vista de "várias empresas ao mesmo tempo, comparadas".** Ou uma, ou
  todas juntas. Comparar empresas lado a lado é outra funcionalidade, com
  outras perguntas — e nenhuma delas é esta.
- **A escolha não é auditada.** A auditoria ouve `*` e o evento
  `empresa.escolhida` é publicado, por isso fica na trilha; mas ninguém
  desenhou um ecrã para a ler por empresa.

## Alternativa descartada

**Deixar a interface definir o âmbito diretamente.** Era menos código: a
janela passaria o id ao serviço de tarefas. E era exatamente o buraco — o
âmbito passaria a ser um argumento em vez de uma consequência de quem se é.
A regra que se manteve é a do ADR-0007 para as políticas, pela mesma razão:
**uma peça de fora só pode tirar, nunca acrescentar.**
