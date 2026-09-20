# ADR-0012 — Quem é dono do esquema é quem isola

Data: 2026-09-20 · Estado: aceite

## Contexto

O [ADR-0011](ADR-0011-isolamento-entre-empresas.md) isolou as **tarefas** por
empresa, e disse em voz alta o que não fazia: os dados dos módulos continuavam
para a instalação inteira. Um módulo de negócio — o Estoque, e todos os que
vierem — guardava os seus itens sem noção nenhuma de empresa.

A resposta óbvia era **um ficheiro por empresa**: `core/plugin_dados.py` já dá
a cada plugin o seu SQLite, e bastaria dar-lhe um por empresa. Foi a primeira
coisa que pensei fazer.

## O que mudou a decisão

Ao ler o Estoque antes de mexer nele, o facto decisivo: **o esquema é
inteiramente do módulo.** As tabelas estão declaradas dentro dele
(`CREATE TABLE itens (...)`), com as suas próprias migrações. A plataforma
nunca as vê.

Daí decorre o que trava a solução óbvia: **a plataforma não sabe quais das
tabelas de um módulo são por empresa e quais são da instalação.** As
definições do módulo, uma tabela de referência, um catálogo partilhado — nada
disso é por empresa. Separar ficheiros tomaria essa decisão por ele, e
tomá-la-ia mal, sem sequer poder olhar para o que estava a separar.

E havia um segundo problema, pior: o ficheiro que já existe teria de ser
atribuído a **alguma** empresa. Qualquer regra para escolher qual seria um
palpite, e o custo de errar era o inventário inteiro a desaparecer do ecrã.

## Decisão

**A plataforma responde; o módulo decide.**

`contexto.empresa()` devolve a empresa de quem está em sessão, ou `None`
quando não há isolamento. Um módulo que guarde dados por empresa **carrega a
coluna ele próprio**, na sua tabela e na sua migração — porque é ele que sabe
quais das suas tabelas a merecem.

A decisão de **se** há isolamento passou para `core.organizacao
.empresa_da_sessao()`: estava dentro do serviço de tarefas, e os plugins
precisavam da mesma resposta. Duas implementações da mesma decisão divergem, e
a que divergisse seria uma fuga de dados. As três isenções do ADR-0011 — uma
empresa ou nenhuma, sessão sem unidade, estrutura que não responde —
continuam a valer, agora para toda a gente.

O refactor foi feito **sem tocar num único teste**, o que é a prova que
interessa de que não mudou comportamento nenhum.

### A regra dos dados anteriores à estrutura, outra vez

Uma linha com `empresa = NULL` é anterior à estrutura e não pertence a
empresa nenhuma: fica visível a toda a gente. É exatamente a regra das
tarefas, e existe pela mesma razão — sem ela, criar a segunda empresa fazia
desaparecer o inventário inteiro do ecrã.

### O Estoque como prova

Não é uma demonstração: é o módulo real, migrado.

* `itens` ganhou `empresa`, e o `UNIQUE (codigo)` passou a `UNIQUE (empresa,
  codigo)` — os códigos vêm dos fornecedores, e duas empresas repetem-nos
  naturalmente;
* `movimentos` **não** ganhou coluna: um movimento pertence ao item, e o item
  à empresa. Duplicar a coluna seria criar duas versões da mesma verdade;
* o âmbito aplica-se também ao `obter`, e não só ao `listar`. É a forma
  clássica de um isolamento ter buracos: o item não aparece na lista mas abre
  pelo id — e `exigir`, que guarda **a escrita**, passa por `obter`.

Isto obrigou a uma capacidade que o contrato não tinha, e que entrou antes:
substituir uma tabela que tem filhos ([ver o modo próprio de `migrar`](../../README.md)).

## Consequências

**Boas**

- Um módulo pode ser multiempresa sem que a plataforma adivinhe nada sobre as
  suas tabelas.
- A decisão de isolamento vive num sítio só, para tarefas e para módulos.
- O Estoque é um exemplo a sério de como se faz, e não uma nota na
  documentação.

**Custos**

- **A plataforma deixa de poder garantir o isolamento dos dados de um
  módulo.** Um módulo mal escrito — ou malicioso — que ignore
  `contexto.empresa()` vê tudo. Está escrito aqui porque é o custo real desta
  decisão, e não pode ser resolvido sem a plataforma passar a ser dona do
  esquema, que é o monólito de volta.
- Mais uma coisa que quem escreve um módulo tem de saber. A documentação do
  SDK di-lo, e o Estoque mostra-o.

## O que continua por fazer

- **Não há seletor de empresa.** A empresa é a de quem está em sessão.
- **A auditoria, as contas e a configuração** não estão isoladas.
- **Não há verificação** de que um módulo respeita o âmbito. Um teste de
  arquitetura não o consegue ver: o SQL de um módulo é texto que a plataforma
  não interpreta. O que existe é o exemplo e o contrato escrito.
