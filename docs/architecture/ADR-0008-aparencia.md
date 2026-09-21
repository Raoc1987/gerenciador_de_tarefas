# ADR-0008 — A aparência é um sistema, não uma folha de estilo

Data: 2026-09-18 · Estado: aceite

## Contexto

O programa fazia tudo o que promete e parecia de 1998. Não por desleixo — por
omissão: o ttk usa o tema do sistema, e ninguém lhe tinha dito outra coisa.

Ao medir em vez de olhar, o que estava lá era isto:

* **nenhum tema.** O `theme_use` nunca foi chamado, por isso os controlos vinham
  com os biséis do tema `vista`: caixas de texto afundadas, botões em relevo;
* **onze cores em hexadecimal, copiadas por doze ficheiros de interface.** O
  mesmo cinzento de texto secundário escrito à mão em nove sítios;
* **`("Arial", N)` em vinte sítios**, com N a variar entre 8 e 20 sem escala
  nenhuma por trás;
* e o mais concreto: o cinzento do texto secundário dava **3,67** de contraste
  sobre branco. O mínimo da WCAG para texto normal é 4,5. Ninguém errou de
  propósito — foi escolhido a olho, e a olho não se vê a diferença entre 3,67
  e 4,5.

## Decisão

### Um token é um papel, não uma cor

`texto_suave` continua a chamar-se `texto_suave` no modo escuro, onde é mais
claro do que o fundo. Quem usa pede o papel; o valor vem do modo em vigor. É
por isso que o modo escuro custa um dicionário em vez de uma passagem por toda
a base de código.

### O que é discutível fica por conta de quem decide; o que é mensurável é medido

"Bonito" é uma opinião e não se testa. **Legível** é um número:
`tests/test_aparencia.py` mede cada par de cores que aparece mesmo no ecrã,
nos dois modos, contra os limiares da norma. Uma paleta que não passa não
entra.

Dois papéis que a medição obrigou a separar, e que eu tinha juntado num só:

* uma linha que **separa** — a borda de um cartão, uma régua entre secções — é
  decoração, e a norma não lhe exige contraste. Dar-lho transformava cada
  divisória num traço preto a gritar;
* uma linha que **identifica um controlo** — a borda que diz "isto é uma caixa
  onde se escreve" — exige 3:1 quando é a única pista de que ali há um campo.

O mesmo entre **escrever** e **preencher**. Uma cor de texto é puxada para
escura, para dar 4,5:1. A mesma cor numa barra de meio ecrã fica pesada e
suplanta tudo o resto. Um preenchimento precisa de ~3:1 e mais do que isso é
ruído — são listas separadas.

### O tema base é o `clam`

Não por gosto: é o único dos que vêm com o Tk que respeita cores e contornos em
todos os elementos. O `vista` desenha os controlos com imagens do sistema
operativo e ignora quase tudo o que se lhe pede.

### Uma cor de ênfase, usada pouco

O azul aparece no que está selecionado, no foco e no **botão principal de cada
ecrã**. O painel tinha cinco cartões de indicador com cinco cores diferentes —
uma fila assim não tem nada em destaque, tem cinco coisas a disputar a atenção.
A cor ficou para o cartão que diz mesmo alguma coisa sobre o estado.

### É Service, não Core

O núcleo não importa interface nenhuma, e a regra de arquitetura passou a
incluir `aparencia` no conjunto do que o Core não pode tocar — importa
`tkinter`, e quem não pode tocar na interface também não pode tocar no que a
pinta. A aplicação funciona sem isto: fica com o aspeto de origem do Tk, que
era o que tinha antes.

### Os plugins não ficam de fora

Os widgets ttk de um plugin herdam o tema sem pedir nada — as classes de estilo
são globais. Para o que o ttk não alcança (desenhar num `Canvas`), o contexto
oferece `cor()`, `fonte()` e `espaco()`. Um plugin que escreva `"#7a8794"` fica
a ser o único sítio claro de uma janela escura.

## Consequências

**Boas**

- Um ecrã novo herda o aspeto sem fazer nada.
- O modo escuro existe, e é uma escolha guardada em vez de uma reescrita.
- A acessibilidade passou de "ninguém verificou" para "falha a construção".

**Custos**

- Mais uma indireção: `cores()["texto_suave"]` em vez de `"#7a8794"`. É o
  preço de o modo escuro alcançar o que quer que seja.
- O modo só muda ao reabrir a aplicação: os widgets são construídos com as
  cores em vigor. É o mesmo comportamento que as funcionalidades já têm, e
  trocar isso obrigava a reconstruir a janela inteira a meio.
- A escala fechada recusa um tamanho de letra solto. É de propósito, e vai
  incomodar alguém um dia.

## O que não se fez, e porquê

- **Cantos arredondados nos controlos.** O ttk não os sabe desenhar, e
  fazê-los obrigaria a substituir cada botão por um `Canvas` — perdendo o
  comportamento de teclado, o foco e a acessibilidade que o widget traz de
  origem. Aparência não vale isso.
- **Ícones.** Sem dependências (ADR-0002), seria desenhá-los à mão em `Canvas`
  ou depender de glifos Unicode cujo aspeto muda com a letra instalada. Fica
  para quando houver um caso que os exija.
- **Seguir o modo claro/escuro do sistema operativo.** O Tk não o expõe de
  forma portável, e lê-lo do registo do Windows seria código específico de uma
  plataforma no arranque. A escolha é explícita e fica guardada.
