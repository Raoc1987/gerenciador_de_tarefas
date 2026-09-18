# ADR-0009 — A concha substitui as abas, e finge ser elas

Data: 2026-09-18 · Estado: aceite

## Contexto

A janela principal era um `ttk.Notebook`: uma fila horizontal de separadores.
Funciona com quatro. O plano de evolução para plataforma prevê Tarefas,
Projetos, Pessoas, Horas, Custos, Estoque, Manutenção, Analytics, BI, Data
Science, Relatórios, Plugins e Administração — **treze**. A partir de cerca de
seis, a fila ou corta ou encolhe a ponto de deixar de se ler.

E havia um problema maior do que a largura. Uma secção nova era uma linha
acrescentada à mão em `gui.py`:

```python
notebook.add(painel_dashboard, text=carregar_texto("dashboard"))
notebook.add(aba_tarefas, text=carregar_texto("tarefas"))
```

Com treze módulos, `gui.py` passaria a conhecer os treze. É o monólito a
voltar pela porta das traseiras — e nenhuma das regras de arquitetura
existentes o apanhava, porque nenhuma fala de quem sabe o quê sobre a
interface.

## Decisão

### A concha implementa a interface do Notebook

`navegacao.Concha` substitui o `ttk.Notebook` e implementa `add`, `forget`,
`tab`, `select`, `tabs` e `index` — incluindo as três formas de `tab_id` que o
Tk aceita: o widget, o índice, e o nome do widget em texto.

Isto não é nostalgia: o contrato dos plugins passa por `AnfitriaoGUI`, que
chama `notebook.add`. **Nenhum plugin instalado na máquina de alguém precisa
de mudar uma linha** para passar a aparecer numa barra lateral. É a mesma
razão pela qual os nomes do SDK estão congelados no ADR-0005 — só que aqui foi
possível mudar a coisa sem mudar o contrato.

A afirmação é verificada: `tests/test_navegacao.py` exercita as três formas de
`tab_id`. Sem isso, "substitui o Notebook" seria uma intenção em vez de um
facto.

### Um destino declara-se; a concha não conhece nenhum

`navegacao.registo` é o mesmo padrão dos indicadores, das fontes de pesquisa,
dos destinos de importação e das políticas: quem tem alguma coisa a mostrar
regista-a, com o grupo, a ordem, a permissão e a funcionalidade de que
depende. A concha desenha o que estiver registado.

Um destino que exija uma permissão que a sessão não tem **não aparece**, e um
grupo que ficaria vazio também não — um título de secção sem nada por baixo é
ruído.

Os grupos são uma lista fechada (`principal`, `operacoes`, `inteligencia`,
`sistema`). Um grupo novo por cada módulo daria uma barra lateral com vinte
secções de um item, que é uma lista e não uma organização.

### O conteúdo é uma pilha, não um ecrã que se refaz

Todos os painéis existem; só um está visível. Destruir e reconstruir ao mudar
de secção perderia o filtro escolhido e a linha selecionada — é o tipo de
coisa que faz um produto parecer que se esquece.

O custo é memória: treze painéis construídos em vez de um. Se um dia um deles
for pesado ao ponto de se notar, a resposta é construí-lo na primeira visita,
não deitar fora o estado de todos.

### A paleta de comandos é outro registo

`Ctrl+K` abre uma lista que encolhe à medida que se escreve. Os comandos são
registados — pela aplicação e pelos plugins — e a paleta não sabe o que
nenhum deles faz. Um comando com uma permissão que a sessão não tem não
aparece; um comando que rebente não leva a aplicação com ele.

Cada secção entra também como "Ir para X": quem já sabe o nome chega lá sem
percorrer a barra lateral.

### A limpeza é da interface, não do núcleo

Quando um plugin é descarregado, os seus destinos e comandos saem. Escrevi
isso primeiro dentro do `PluginManager` — e a regra de camadas apanhou-o: o
Core não importa interface, nem sequer dentro de uma função.

A correção não foi uma exceção. O `AnfitriaoGUI` **já era avisado** pelo
núcleo (`ui.remover_abas`), e vive na camada de interface. A limpeza foi para
lá, onde já havia um aviso à espera de ser usado.

## Consequências

**Boas**

- Uma secção nova não toca em `gui.py`: declara-se.
- Um plugin passa a poder pôr-se na barra lateral e na paleta sem que a
  aplicação o conheça.
- A barra lateral recolhe para ícones; a fila horizontal não tinha como.

**Custos**

- Mais uma peça entre a janela e os painéis.
- A concha tem de continuar a imitar o Notebook enquanto houver plugins
  escritos contra ele — e há um teste a garantir que continua.
- Todos os painéis são construídos ao abrir, mesmo os que ninguém visita.

## O que não se fez

- **Reordenar ou fixar secções** à maneira de quem usa. Precisa de um sítio
  onde guardar a escolha por pessoa, e não há ainda nenhum caso que o peça.
- **Ícones a sério.** Sem dependências (ADR-0002), seriam glifos Unicode cujo
  aspeto muda com a letra instalada, ou desenho à mão em `Canvas`. Há uma
  marca de um caractere por destino, que chega para a barra recolhida.
- **Pesquisa global dentro da barra de topo.** A pesquisa já existe e abre-se
  por `Ctrl+F`; embuti-la na barra é trabalho de apresentação, não de
  capacidade, e fica para quando houver mais fontes registadas.
