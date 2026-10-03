# ADR-0021 — Os relatórios da web voltam a ser escritos à mão

Data: 2026-10-02 · Estado: aceite

## Contexto

O desktop exporta relatórios em PDF, XLSX e CSV com escritores próprios, sem
reportlab nem openpyxl ([ADR-0002](ADR-0002-graficos-sem-dependencias.md)). O
[ADR-0017](ADR-0017-plataforma-web.md) disse que o ADR-0002 deixava de valer
para a web, porque numa aplicação servida as dependências são a forma normal de
não reescrever o que já existe.

Para os relatórios, a conta dá ao contrário. As bibliotecas de PDF e de Excel
para JavaScript pesam centenas de KB a vários MB, trazem as suas próprias
dependências e correm numa função do servidor com limites de tamanho e de
arranque — para produzir documentos que o desktop já produz em ~600 linhas
testadas. E o mesmo relatório nos dois produtos é uma vantagem para quem está
a migrar.

## Decisão

**Os exportadores do desktop são portados para TypeScript**, com o mesmo
desenho (`web/lib/relatorios/`):

- `modelo.ts` — um relatório é uma lista de secções (indicadores, lista,
  tabela) já calculadas; quem constrói não sabe o formato, quem exporta não
  sabe de onde vêm os números;
- `pdf.ts` — Helvetica e Helvetica-Bold (sem embutir fontes), texto em WinAnsi,
  paginação com cabeçalho de tabela repetido e rodapé numerado;
- `xlsx.ts` + `zip.ts` — um ZIP de XML; texto em `inlineStr`, números como
  números, códigos com zero à esquerda como texto, cabeçalho a negrito;
- `csv.ts` — `;` e BOM, como o desktop.

**Duas correções em relação ao desktop**, encontradas a validar os ficheiros:

- o PDF passa a **A4 deitado** e as colunas curtas (datas, estado, prioridade)
  ficam com a largura de que precisam antes de a coluna da tarefa ficar com o
  resto — ao alto, com sete colunas, as datas saíam cortadas ("02/09/20…");
- o CSV **neutraliza fórmulas**: um título começado por `=`, `+`, `-` ou `@`
  leva um apóstrofo à frente, para o Excel não o executar ao abrir. No XLSX não
  é preciso — o texto vai em `inlineStr`, que nunca é fórmula.

**O relatório lê com a sessão de quem o pede** (`relatorios/exportar`): a RLS
decide que tarefas entram, como na lista. Um colaborador exporta as suas.

## Como se prova

- `web/lib/relatorios/relatorios.test.ts`: o XLSX é aberto de volta (ZIP, CRC
  de cada entrada, relações entre partes, células); no PDF, cada entrada do
  `xref` aponta para o seu objeto e cada `/Length` bate com o fluxo; WinAnsi,
  escapes, colunas que não se cortam, CSV com BOM e fórmulas neutralizadas;
- validado à parte com o `pdftotext` (Poppler): o PDF abre, as páginas contam-se
  e o texto sai com os acentos, parênteses, barras e aspas curvas certos.

## Consequências

- **Não foi aberto no Excel nem no LibreOffice.** O LibreOffice do ambiente onde
  isto foi escrito não abria nenhum ficheiro, nem um CSV de duas linhas; o XLSX
  foi verificado pela estrutura e relido célula a célula. O escritor é o mesmo
  que o desktop valida com o openpyxl, mas a confirmação num Excel real fica
  por fazer.
- **O PDF não tem gráficos**, como no desktop: o painel é o sítio para os ver.
- **Caracteres fora do WinAnsi** (emoji, alfabetos não latinos) saem como `?`
  no PDF. No XLSX e no CSV saem intactos.
- O ZIP não comprime: um relatório de 5000 tarefas em XLSX tem alguns MB.
