# ADR-0013 — Uma notificação tem destinatário

Data: 2026-09-20 · Estado: aceite

## Contexto

A cadeia da análise estava feita até ao penúltimo elo:

```
tarefa → evento → métrica → painel → modelo → previsão → alerta → ???
```

`src/alertas.py` publicava `analise.alerta` no barramento, e uma regra de
automação podia agir sobre ele. Mas **não havia sítio onde uma pessoa o
lesse**. Um aviso que só existe no barramento é um aviso que ninguém recebeu.

A §42 do plano pedia um Notification Center, e a §10 registava que a barra de
topo tinha pesquisa, comandos e sessão — e não tinha notificações.

## O defeito que apareceu ao medir, antes de escrever

Antes de construir a caixa, fui ver a quem pertencia o que ela ia guardar. A
memória da vigilância (`alertas_vistos`) era **uma linha por chave, para a
instalação inteira**. Com duas empresas, isto é o que acontecia — medido, não
suposto:

| Passo | Resultado |
|---|---|
| Ana (Acme) avalia, com 20 tarefas atrasadas | `insight_atrasadas` anunciado, memória gravada |
| Bruno (Rival) avalia, sem atrasos nenhuns | a chave da Ana não está no âmbito dele |
| — | publica **`analise.resolvido`** e **apaga a memória da Ana** |

A Acme continuava com 20 tarefas atrasadas. A plataforma tinha acabado de
anunciar que o problema estava resolvido, e de esquecer que alguma vez o
tinha dito.

Construir a caixa por cima disto daria uma caixa cujo conteúdo dependia de
quem tivesse entrado por último. Por isso esta decisão tem duas metades, e a
primeira é a que tornava a segunda possível.

## Decisão

**Quem é avisado é uma pessoa, não uma instalação.**

1. `alertas_vistos` passa a ter `destinatario`, com chave primária
   `(destinatario, chave)`. A avaliação corre com o âmbito de quem a
   desencadeou — a vigilância já dizia que "não vê mais do que quem a
   desencadeou" — por isso a memória do que foi dito é de quem o ouviu.

2. `src/notificacoes.py` (**Service**, ADR-0004) guarda o que foi anunciado a
   cada pessoa e o que essa pessoa já leu. **Não aceita um destinatário como
   argumento**: responde sempre pela sessão. Não se consegue vazar o que a API
   não sabe dizer — e uma assinatura que aceitasse um nome punha a fuga a uma
   chamada de distância, à espera de que alguém a escrevesse por engano.

3. `src/notificacoes_ui.py` (**UI**) mostra: um sino na barra de topo com o
   número por ler, e um centro que abre por baixo dele.

### Guarda-se a chave, nunca a frase

Uma notificação guarda a chave de tradução e os parâmetros. O produto fala
três idiomas e o idioma muda em execução: uma frase gravada em texto ficava
congelada no idioma do dia em que aconteceu, e quem trocasse para inglês
ficava com uma caixa metade numa língua e metade noutra.

A exceção é a ação `notificar` das automações, que guarda o texto já feito. A
diferença não é descuido: uma frase que alguém escreveu na sua língua não tem
tradução para onde ir buscar, e fingir que tinha deixava a caixa a mostrar a
chave em vez do aviso.

### É uma caixa de correio, não um painel de estado

`analise.resolvido` **não** apaga nem esconde nada. Uma notificação diz o que
era verdade às 14:05, e isso continua a ter sido verdade às 14:05. Quem quer
saber como as coisas estão **agora** tem o painel, que é o sítio para essa
pergunta.

## Consequências

**O que se ganha.** A cadeia fecha. Os alertas que já existiam passam a ter
onde ser lidos, cada pessoa vê os seus, e a §41 deixa de prometer notificações
que não existiam — `notificar` passa a ser uma ação a sério das regras.

**O que isto custa, e fica dito.**

- **Uma caixa por ler pode mostrar um alarme que já passou.** É a consequência
  direta de ser correio e não estado. A alternativa — retirar avisos — era
  pior: uma caixa que se reescreve sozinha deixa de ser uma prova do que foi
  dito.
- **Uma pessoa só é avisada quando usa a aplicação.** A vigilância corre a
  partir de eventos de tarefas, na sessão de quem os provoca. Quem não entrar
  não recebe nada, e ao entrar recebe o que for verdade nesse momento — não o
  histórico do que aconteceu na sua ausência. Isto já era assim; o que muda é
  que agora está escrito.
- **Na primeira abertura depois da atualização, cada pessoa é avisada uma vez
  do que ainda for verdade.** As linhas antigas de `alertas_vistos` ficam com
  `destinatario` vazio: não se sabe a quem foram anunciadas, e inventar um
  dono seria escrever no banco uma coisa que nunca aconteceu. **Não se apaga
  nada** — é o mesmo efeito de `esquecer_tudo()`, que já estava documentado.
- **A plataforma não pode garantir o que um módulo põe num aviso.** Como no
  [ADR-0012](ADR-0012-dados-de-modulo-por-empresa.md): a caixa entrega a quem
  está em sessão, e o que lá vai dentro é da responsabilidade de quem o
  escreve. O que a plataforma garante é que não vai para mais ninguém.

## Alternativas descartadas

**Uma secção na barra lateral em vez de um sino.** Reutilizava a concha e não
custava nada — mas um centro de notificações a que é preciso navegar é um
centro que não se consulta. O sino tem de estar onde o olho passa.

**Notificações com permissão de leitura.** Um aviso é endereçado a uma pessoa;
pedir-lhe uma permissão para ler o que lhe foi dirigido é uma pergunta sem
resposta boa. Quem precisa de ver o que o sistema anunciou tem a auditoria,
que é a trilha e tem as suas próprias regras.

**Apagar por retenção, como a auditoria.** A auditoria tem de guardar por
omissão, porque é prova. Uma caixa de correio tem o problema oposto — cresce.
A regra aqui é um limite por pessoa que só descarta **lidas**, das mais
antigas para as mais recentes. O que ainda não foi lido nunca é apagado para
dar lugar a nada: a pessoa não ficaria a saber, e não ficaria a saber que não
ficou a saber.
