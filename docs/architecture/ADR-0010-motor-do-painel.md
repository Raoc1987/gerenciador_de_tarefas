# ADR-0010 — O painel desenha o que estiver registado

Data: 2026-09-19 · Estado: aceite

## Contexto

O painel era uma lista fixa escrita à mão: cinco cartões, dois gráficos e uma
caixa de análise, montados dentro de `dashboard_ui.py`.

Um módulo de negócio já podia declarar um **número** — o registo de
indicadores existe desde a etapa dos KPIs. O que não podia era declarar um
**gráfico**, uma tabela ou uma lista. "A análise atravessa todo o produto"
ficava por cumprir exatamente no sítio onde mais se nota.

E havia o problema da largura: cinco cartões lado a lado e dois gráficos numa
linha assumem um ecrã largo. Num portátil a 1366×768 com escala a 125% sobram
cerca de 1090px de janela e 866 de painel — e cada cartão fica com um número e
meia palavra.

## Decisão

### Um widget declara-se, e a grelha desenha

Mesmo padrão dos indicadores, da pesquisa, dos destinos de importação, das
políticas e dos destinos de navegação: `painel.registar(...)` com o id, o
título, o construtor, a **largura em colunas**, a ordem, a permissão e a
funcionalidade de que depende.

O contrato de um widget é pequeno de propósito: `construir(pai)` devolve um
widget do Tk, e se esse widget tiver `atualizar(contexto)` a grelha chama-o
quando os filtros mudarem. Quem não tiver é desenhado uma vez e fica quieto —
o que chega para uma nota ou uma legenda.

### Os dados vão ao widget; o widget não vai aos dados

O `Contexto` leva o período e o panorama **já calculado**. Um widget que fosse
buscar os seus próprios dados abriria a sua própria ligação e acabaria por dar
um número diferente do cartão do lado — que é a falha clássica de um painel, e
é invisível até alguém somar as duas coisas.

É também a forma dos **filtros globais**: hoje tem o período; amanhã a
unidade, o responsável, o estado. Acrescentar um campo não parte um widget que
o ignore, e é por isso que é um objeto e não uma lista de argumentos.

### Quatro colunas, duas, ou uma

A grelha reparte-se pela largura **dela**, com a barra lateral já descontada.
Quatro colunas num ecrã largo; duas no portátil típico; uma numa janela
estreita. Quem pediu quatro colunas num arranjo de duas recebe duas — continua
a ocupar a linha inteira, que é o que queria dizer.

Os widgets são construídos **uma vez**: reconstruí-los ao redimensionar
perderia o que estivesse escolhido dentro deles e piscaria o ecrã a cada píxel
de arrasto do rato.

### Falhar sozinho

Vai haver widgets de plugins nesta grelha. Um que rebente a construir é
registado e saltado; um que rebente a atualizar não impede os seguintes de
serem atualizados. É a mesma regra do resto do motor de plugins.

### Sem permissão, o widget não existe

Não é escondido: não é construído. Um cartão vazio ainda diz que existe um
número que a pessoa não pode ver.

**A primeira execução mostrou o custo disto**, e obrigou a corrigir: sem
`analytics.ler` nenhum widget é visível — incluindo o que ia mostrar a razão.
O painel ficava vazio e calado, que é pior do que dizer "não tem permissão".
A razão passou a viver **no painel**, que existe sempre, e não num widget que
pode não existir.

## Consequências

**Boas**

- Um módulo põe um gráfico no painel principal
  (`contexto.registar_widget_de_painel`), e não só um número.
- O painel serve um portátil sem ser preciso redimensionar a janela antes de
  trabalhar.
- `dashboard_ui.py` deixou de conhecer o conteúdo dos blocos que desenha.

**Custos**

- Mais uma indireção entre o cálculo e o ecrã.
- Todos os widgets registados são construídos ao abrir o painel, mesmo os que
  ficam fora do ecrã.
- **Segunda inversão de dependência para o mesmo problema.** O contrato dos
  plugins vive no Core, que não pode importar interface; já havia um
  fornecedor injetado para a aparência (ADR-0008) e agora há outro para o
  painel. Duas são um padrão. Se aparecer uma terceira, vale a pena juntá-las
  num fornecedor só, e isto fica escrito para essa altura.

## O que não se fez

- **Dashboard Builder** (§19 do plano): escolher widgets e guardar arranjos
  por pessoa. Precisa de um sítio onde guardar a escolha por utilizador, e a
  forma desse sítio depende de haver ou não multiempresa — que é a decisão
  seguinte.
- **Drill-down e drill-through** (§23–24). Precisam de um contrato de
  navegação entre widgets ("abre-me o detalhe disto"), e esse contrato é mais
  fácil de desenhar quando houver um segundo módulo a usá-lo.
- **Filtros além do período.** Os campos existem no contexto; o que não existe
  é interface que os mude, e inventá-la antes de haver um módulo que os leia
  seria construir uma superfície sem utilizador.
