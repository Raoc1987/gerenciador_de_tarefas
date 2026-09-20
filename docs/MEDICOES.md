# O que foi medido, e o que a medição encontrou

Data: 2026-09-20

A secção **"Não validado"** de [PLATAFORMA.md](PLATAFORMA.md) listava quatro
coisas que existiam mas nunca tinham sido medidas: desempenho (§68),
1366×768 (§81), DPI a 125% e 150% (§82) e navegação por teclado (§60).

A regra 68 do plano diz **"não otimizar sem medir"**. A consequência simétrica
é **não afirmar que está bom sem medir** — e era isso que faltava aqui.

Este documento é o resultado. Inclui os dois defeitos que a medição encontrou,
que é a razão de valer a pena medir.

---

## Como foi medido

Num portátil Windows 11, ecrã 1920×1080, Python 3.14.4. Cada tempo é a
**mediana de sete repetições depois de uma de aquecimento**: a primeira
passagem paga *imports*, caches do SQLite e métricas de fontes, e não é a que
alguém sente ao repetir a operação.

A escala de DPI é posta com `tk scaling` **antes de existir um único widget**,
porque o Tk resolve as métricas de uma fonte quando ela é usada pela primeira
vez. As janelas são fotografadas com `PrintWindow`, que manda a janela
desenhar-se num contexto em memória — não fotografa o ecrã.

### Duas armadilhas, porque quase passaram por medições

**A primeira medição de DPI não media nada.** Punha o `tk scaling` depois de a
janela estar construída, e dava **exatamente os mesmos números a 100% e a
125%** — foi essa igualdade suspeita que denunciou a alavanca desligada. Agora
cada medição imprime a altura em píxeis de uma linha de texto (17 → 22 → 27)
antes de medir o resto, para se ver que a alavanca mexe.

**A memória dava `0.0 MB` com ar de resposta.** Faltavam os `argtypes` no
`ctypes`, e o pseudo-handle do processo (-1) ia truncado a 32 bits num
processo de 64. A chamada falhava em silêncio. **Um zero é mais perigoso do
que um erro, porque parece um número.**

E uma terceira, que estragou as fotografias e não os números: **o tema é
aplicado em `main.py`, não em `gui.criar_janela`**. As primeiras capturas
desta sessão são da aplicação sem aparência nenhuma. As conclusões de
*layout* aguentaram-se; as de aspeto foram refeitas.

---

## §68 — Desempenho

### Arranque

| | |
|---|---|
| Executável congelado, arranque completo até à janela | **1 701 ms** |
| — dos quais, importar os módulos (em desenvolvimento) | 117 ms |
| — construir a janela (em desenvolvimento) | 677 ms |

O número que conta é o primeiro: é o que alguém espera ao abrir o programa.
Abaixo de dois segundos, com descoberta de plugins, janela de sessão e janela
principal pelo meio.

### Memória

| Momento | Memória do processo |
|---|---|
| Antes de importar | 22 MB |
| Depois de importar | 37 MB |
| Com a janela construída | **53 MB** |
| Com 20 000 tarefas no banco | 68 MB |

### O que cresce com o uso

| Tarefas | ler | panorama | **atualizar o painel** | construir o painel |
|---:|---:|---:|---:|---:|
| 0 | 3 ms | 3 ms | **10 ms** | 37 ms |
| 100 | 3 ms | 3 ms | **16 ms** | 43 ms |
| 1 000 | 5 ms | 6 ms | **23 ms** | 56 ms |
| 5 000 | 13 ms | 21 ms | **66 ms** | 125 ms |
| 20 000 | 46 ms | 71 ms | **229 ms** | 383 ms |

**Conclusão: não há nada para otimizar.** Até às cinco mil tarefas — muito mais
do que uma equipa cria num ano — o painel refresca em menos de 70 ms, que é
abaixo do que se nota.

**Construir e atualizar são perguntas diferentes.** A primeira versão desta
medição somava as duas e dizia 677 ms a 20 000 tarefas. Construir acontece uma
vez, quando a secção nasce; atualizar acontece a cada tarefa criada. Confundi-las
transformava um custo pago uma vez num custo pago sempre.

**O que fica em aberto, sem ser urgente:** a 20 000 tarefas, atualizar demora
229 ms **na linha de execução da interface**, e é disparado por eventos de
tarefa. Criar uma tarefa nessa instalação congela a janela por um quinto de
segundo. É a justificação da §59 (trabalho fora da linha da interface) — e
agora tem um número em vez de uma intuição.

Guardado por `tests/test_desempenho.py`, com limites folgados: o que lá está
apanha uma regressão de **ordem de grandeza**, não uma variação de máquina.

---

## §81 e §82 — 1366×768, e a letra a 125% e 150%

Espaço útil considerado: 1366×728 a 100% (a barra de tarefas descontada, e
ela também escala).

| Escala | Altura de uma linha | O conteúdo prefere | Cabe? | Fotografado |
|---|---|---|---|---|
| 100% | 17 px | 1029×528 | sim | correto |
| 125% | 22 px | 1258×573 | sim | correto |
| 150% | 27 px | 1491×588 | **não, em largura** | **correto na mesma** |

A 150% o conteúdo *prefere* 1491 px e só tem 1366 — mas a fotografia mostra
tudo legível e nada cortado. **Preferir mais largura não é o mesmo que não
caber**: as colunas da grelha repartem-se e os cartões encolhem. Reportar
"não cabe" a partir do número teria sido reportar um defeito que não existe.

**§81 e §82: validados.** Num portátil de 1366×768, a 100%, 125% e 150%, a
aplicação mostra tudo.

---

## §60 — Navegação por teclado

| | |
|---|---|
| Controlos acionáveis e visíveis (Painel) | 10 — **10 alcançados com Tab** |
| Controlos acionáveis e visíveis (Tarefas) | 15 — **15 alcançados com Tab** |
| `Ctrl+F` e `Ctrl+K` ligados à janela | sim |

**O foco vê-se**, e isso foi medido a contar píxeis em vez de a olhar: desenha-se
o mesmo controlo com e sem foco e comparam-se as imagens.

| Controlo | Píxeis que o foco muda |
|---|---|
| `Lateral.TButton` | 3 090 |
| `TButton` | 7 272 |
| `TEntry` | 6 243 |
| `TCheckbutton` | 2 328 |

Suspeitei que a barra lateral não mostrasse o foco, por ter `borderwidth=0`.
**A medição disse que não** — 3 090 píxeis mudam. A suspeita estava errada e o
número desfê-la em vez de a confirmar.

**§60: validado para o que se alcança e para o foco se ver.** O leitor de ecrã
é outra pergunta, precisa de outro instrumento, e a resposta está mais abaixo
— não é boa.

---

## O que a medição encontrou, e que foi corrigido

Nenhum dos dois dava erro. É o pior tipo de defeito de interface.

### 1. O painel não tinha deslocamento vertical

A **940×620 — o mínimo que a própria aplicação declarava** — a caixa "Análise"
ficava abaixo da dobra e **não havia como lá chegar**. O dado estava
calculado, estava desenhado, e era inalcançável. Acontecia já a 100%.

Corrigido com `painel/rolo.py`: a grelha passa a viver num contentor que se
desloca, com barra só quando é precisa, e que também anda com o teclado —
`Up`, `Down`, `Page Up`, `Page Down`.

### 2. O tamanho mínimo era em píxeis e não acompanhava a letra

`minsize(940, 620)` estava fixo. A 150%, a aplicação **permitia** uma janela
onde a barra de topo se sobrepunha a si própria: o botão `Ctrl+F` ficava
cortado a `C`, e o seletor de idioma **desaparecia sem aviso**.

Corrigido: as medidas são pensadas a 100% e multiplicadas pela escala em
vigor (`aparencia.em_pixeis`), e **travadas pelo ecrã** — 940×620 a 150% pede
1410×930, e um portátil de 1366×768 não tem lá isso. Um mínimo maior do que o
ecrã é pior do que um mínimo errado: tira a quem lá está a única saída que
tinha.

### 3. De caminho: a razão de o painel estar vazio deixou de aparecer

Ao pôr a grelha dentro do rolo, ela deixou de ser irmã do aviso — e
`pack(before=...)` com um widget de **outro pai não faz nada e não levanta**.
A mensagem "sem permissão para ver isto" desapareceu do ecrã em silêncio, e a
suíte inteira continuou verde. Apanhado a olhar para o resultado, não para o
código.

---

## §60 (segunda metade) — Leitor de ecrã

Não é possível ouvir o NVDA a partir daqui. O que se fez foi ler **a mesma
árvore que ele lê**: a de acessibilidade do Windows (MSAA/`IAccessible`). É o
dado de onde sai tudo o que um leitor anuncia.

| | |
|---|---|
| Controlos acionáveis e visíveis | **15** |
| Janelas nativas por baixo da principal | **78**, todas `TkChild` |
| Dessas, **com nome** na árvore | **0** |
| Papéis encontrados | `cliente` × 78 — nem um botão, nem um campo |
| Janela principal | nome `Gerenciador de Tarefas`, papel `cliente`, 1 filho |

**Veredicto: a aplicação não é utilizável com um leitor de ecrã.** Um leitor
encontra uma janela com título e, por baixo, 78 caixas anónimas
indistinguíveis. A causa não está neste repositório: o Tk desenha os seus
widgets e, no **8.6.15** que aqui corre, não implementa `IAccessible` para
eles. Ver [ADR-0016](architecture/ADR-0016-leitor-de-ecra.md), que também diz
o que custaria mudar.

Isto **não** invalida a primeira metade da §60: alcançar tudo com `Tab` e ver
o foco continuam medidos e a valer. Servem quem não usa rato. Não servem quem
não vê — são duas necessidades, e o produto responde a uma.

### O instrumento foi conferido antes de se acreditar nele

A primeira versão da sonda lia o papel de **todas** as janelas como vazio —
incluindo o do ambiente de trabalho do Windows, que tem um. O índice na tabela
de métodos do `IAccessible` estava em 12 (`get_accDescription`); o papel é o
13. Como o nome (10) estava certo, os nomes saíam bem e o erro passava por
resultado. A conclusão acabou por ser a mesma; o número que a apoiava não era.

É a terceira armadilha desta série, e todas têm a mesma forma: **uma medição
que responde com ar de resposta.**

---

## O que continua por validar

- **Ecrãs acima de 150%** e monitores com escalas diferentes ao mesmo tempo:
  o Windows muda o DPI de uma janela ao arrastá-la entre monitores, e o Tk
  não refaz as fontes sozinho.
- **Desempenho do executável congelado sob carga**: os tempos por operação
  foram medidos em desenvolvimento. O arranque foi medido congelado; o resto
  não.
