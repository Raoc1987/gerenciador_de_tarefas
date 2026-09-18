# ADR-0005 — O espaço de nomes de topo é partilhado com o mundo

Data: 2026-09-15 · Estado: aceite

## Contexto

`src/` está no `sys.path`. Cada ficheiro e cada pasta diretamente ali ocupa um
nome no **espaço global de módulos do Python** — o mesmo espaço onde estão
todos os pacotes instalados. `src/database.py` não é "o nosso database": é
`database`, para toda a gente dentro do processo.

Isto já custou caro uma vez. O motor de regras nasceu em `src/workflow/`.
Ninguém decidiu esse nome; foi a palavra que apareceu. Meses depois, o
`pyinstaller-hooks-contrib` trazia um `hook-workflow.py` para o pacote
`workflow` do PyPI. Ao empacotar, o PyInstaller viu um módulo chamado
`workflow`, aplicou-lhe o hook desse pacote, o hook tentou importar coisas que
não existem no nosso código, e o build parou.

O que torna esta falha diferente de um bug normal:

- **os 1045 testes continuavam verdes.** O problema não é de comportamento; só
  existe no momento de empacotar;
- **não houve nenhuma alteração nossa a causá-la.** O que mudou foi um ficheiro
  numa dependência de terceiros;
- **a causa está longe do sintoma.** A mensagem de erro fala de um pacote do
  PyPI que nunca instalámos.

Há uma segunda forma da mesma doença, mais silenciosa: se alguma coisa
instalada fizer `import utils` ou `import database`, recebe **o nosso**
módulo. O erro aparece a uma distância arbitrária da causa.

## Decisão

**Um nome de topo é uma decisão, e as decisões escrevem-se.**

1. `docs/architecture/nomes-de-topo.json` lista **todos** os nomes de topo de
   `src/`, cada um com o que faz. `tests/test_arquitetura.py` falha perante um
   nome que não conste dali.

2. A regra para um nome novo: **uma palavra do domínio, em português**. O
   índice de pacotes é um espaço de nomes em inglês; não partilhar a língua é a
   maneira mais barata de não partilhar nomes. Não é elegância — é aritmética.

3. Os nomes genéricos em inglês que restavam passam a português:

   | antes         | depois            |
   |---------------|-------------------|
   | `database.py` | `banco_de_dados.py` |
   | `analytics/`  | `analitica/`      |
   | `reporting/`  | `relatorios/`     |
   | `widgets/`    | `componentes/`    |

   (`workflow/` → `regras/` já tinha acontecido, à força, quando o build parou.)

4. **As exceções são nomeadas, com a razão.** Duas famílias:

   - **`expostos_a_plugins`** — `utils`, `calendar_widget`, `language_manager`,
     `core`. Um plugin já instalado na máquina de alguém escreve `import
     utils`. Renomear parte esse plugin sem aviso e sem forma de o corrigir à
     distância. O risco de colisão é real; partir código que não controlamos é
     pior. Estes nomes estão **congelados**, e um teste verifica que coincidem
     com os `hiddenimports` do `.spec` — o que se promete tem de ir dentro do
     executável.
   - **`excecoes_de_nome`** — `gui` e `main`, internos, genéricos, com a razão
     escrita de terem ficado.

5. O que é **dado guardado** não se renomeia com o módulo:

   - a permissão continua a ser `"analytics.ler"` — está nos papéis, nas
     declarações dos plugins e nas chaves de tradução;
   - os eventos do banco continuam a assinar `origem="database"`. **Uma trilha
     de auditoria não se reescreve.** As linhas já gravadas não mudam, e mudar
     só as novas partiria o histórico em duas metades que não se consultam
     juntas. O nome do ficheiro é assunto nosso; o valor guardado é um facto
     sobre o passado.

## Consequências

**Boas**

- A decisão passa a ser tomada no dia em que o módulo é criado, que é o único
  dia em que é barata.
- As exceções deixam de ser dívida escondida: estão escritas, com o custo de
  cada uma à vista.
- O contrato com os plugins deixa de poder divergir do empacotamento em
  silêncio.

**Custos**

- Um `sed` grande, de uma vez: 56 ficheiros. O histórico do `git blame` fica
  com um degrau nessas linhas.
- Quem conhecia a árvore tem de reaprender quatro nomes.
- A regra não é uma garantia. Nada impede o PyPI de publicar um pacote chamado
  `alertas`. O que a regra faz é tornar isso improvável e, quando acontecer,
  imediatamente visível — o teste de colisão com os hooks corre a cada
  execução.

## Honestidade sobre o alcance

Isto **não** remove a classe de falhas; reduz-lhe a probabilidade e encurta a
distância entre a causa e o sintoma. A cura completa seria pôr tudo debaixo de
um pacote só (`gdt/`), e nesse caso o espaço de topo teria um nome em vez de
trinta e dois. Não foi feito por uma razão concreta: os quatro nomes do SDK
estão congelados por causa dos plugins instalados, e um `gdt/` que tivesse de
manter `utils` e `calendar_widget` no topo à mesma seria meio caminho com o
custo inteiro. Se um dia houver forma de migrar plugins instalados, é essa a
decisão a rever — e é por isso que fica escrita aqui.

## Revisão da condição (2026-09-17)

A condição escrita acima — *"se um dia houver forma de migrar plugins
instalados"* — foi reexaminada depois de o [ADR-0006](ADR-0006-posse-dos-plugins.md)
entrar. **Cumpriu-se em metade, e a metade que falta é a que interessa.**

O que mudou: um plugin que **acompanha a aplicação** já se atualiza sozinho.
A semeadura passou a comparar versões e a conhecer a posse, por isso os quatro
plugins embutidos poderiam ser publicados numa versão nova a importar de
`gdt.utils`, e essa versão chegaria a quem já os tem.

O que não mudou: um plugin **escrito por outra pessoa** — instalado de um
`.zip`, ou vindo de uma futura loja — continua a não ter caminho nenhum. Ele
escreve `import utils` e nós não temos como o reescrever à distância. E é
exatamente por causa desses que os nomes estão congelados; para os nossos
nunca foi preciso congelar nada.

Resta a variante com camada de compatibilidade: mover tudo para `gdt/` e
deixar `utils`, `calendar_widget`, `language_manager` e `core` no topo como
reexportações finas. Reduziria o espaço de topo de trinta e dois nomes para
cinco — mas os cinco que ficavam continuariam a ser os expostos, e é
precisamente o cenário que a decisão original já pesou e chamou "meio caminho
com o custo inteiro". Não há informação nova que mude essa conta: **a decisão
mantém-se**.

O que a tornaria diferente, e vale a pena escrever para não ser preciso
redescobrir: um mecanismo que faça chegar uma mudança nossa a um plugin que
não é nosso. Enquanto isso não existir, mover tudo é pagar um `sed` por toda a
base de código — e um degrau no `git blame` de cada linha — para ficar com os
mesmos nomes arriscados no topo.
