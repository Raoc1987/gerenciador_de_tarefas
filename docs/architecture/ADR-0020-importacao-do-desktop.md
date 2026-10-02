# ADR-0020 — Importar do desktop: o browser lê o tarefas.db, a base grava como quem importa

Data: 2026-10-02 · Estado: aceite

## Contexto

O [ADR-0017](ADR-0017-plataforma-web.md) congelou a aplicação de secretária
e deixou por fazer o caminho dos dados de quem a usa para a web. Sem ele, mudar
de produto é recomeçar do zero — e quem tem anos de tarefas não muda.

Havia três portas de entrada possíveis:

- **o CSV que o desktop já exporta**: é um relatório, não um formato de troca —
  secções, cabeçalhos traduzidos em três idiomas, estados por extenso
  ("Atrasada"), datas só com o dia, e sem o autor de cada tarefa;
- **enviar o `tarefas.db` ao servidor**: a base inclui a auditoria e cresce
  para dezenas de MB, e os pedidos ao alojamento têm um teto de poucos MB;
- **ler o `tarefas.db` no browser** e enviar só as tarefas.

## Decisão

**O browser lê o ficheiro.** `web/lib/importacao/sqlite.ts` é um leitor
mínimo do formato SQLite — só árvores B de tabela, páginas de overflow e o
formato de registo, escrito a partir da especificação pública — sem
dependências. Lê `tarefas` e `utilizadores`; o resto do ficheiro (contas,
palavras-passe, auditoria) **nunca sai do computador**. Recusa ficheiros em
modo WAL, em vez de ler metade.

**A conversão é pura** (`web/lib/importacao/desktop.ts`): o texto único do
desktop vira título (e descrição, quando é longo ou tem várias linhas), o
prazo aceita `AAAA-MM-DD` e `dd/mm/aaaa`, as datas sem fuso do desktop ganham
o fuso de Brasília, e cada tarefa leva a etiqueta `importado` e uma `origem`
estável (`desktop:<id>:<criada_em>`). Quem importa escolhe, para cada
utilizador do desktop, o membro da web que fica com as suas tarefas — com uma
sugestão pelo nome ou pelo início do email.

**A base grava** (`public.importar_tarefas`), em lotes de até 1000:

- só quem **administra** a empresa importa;
- o autor de cada tarefa é **quem importa** (é a pessoa que responde por estes
  dados agora), e cada uma fica na auditoria;
- as **datas de criação e conclusão são as do desktop** — sem isso, o painel
  diria que tudo foi criado e concluído hoje. O gatilho de tarefas só aceita
  datas vindas de fora quando a própria função liga o modo de importação,
  numa definição local à transação; fora dela, a data continua a ser a de
  agora (há um teste para isso);
- a segregação de funções não se aplica a uma conclusão que já aconteceu;
- importar não manda um email por cada tarefa atribuída;
- **reimportar não duplica**: `(empresa_id, origem)` é único;
- uma tarefa inválida não deita abaixo o lote: é contada e o motivo devolvido;
- um responsável que não é membro da empresa fica vazio, em vez de recusar a
  tarefa.

Os lotes que o browser envia são cortados por número (500) **e por tamanho**
(~800 KB), porque as Server Actions recusam pedidos acima de 1 MB.

## Como se prova

- `web/lib/importacao/amostras/gerar.py` gera bases **com o código do próprio
  desktop** (as migrações reais de `src/banco_de_dados.py`): uma pequena com
  acentos, autores e uma tarefa concluída; uma grande com 2999 tarefas, uma
  apagada e textos de 12 KB em páginas de overflow;
- o leitor foi comparado linha a linha com o SQLite do Python nas duas bases —
  iguais — e os testes fixam esse resultado (`desktop.test.ts`), além de
  validar cada uma das 2999 tarefas convertidas com as regras de um
  formulário;
- `supabase/tests/70_importacao_desktop.sql`: quem pode importar, datas
  preservadas, segregação, sem duplicados, sem emails, auditoria, e que o modo
  de importação não fica ligado nem serve fora dela.

## Consequências

- **O leitor SQLite é código nosso para manter.** É pequeno e só lê, mas um
  ficheiro corrompido de forma criativa pode dar um erro pouco claro; o pior
  caso é a importação não começar — nada é escrito antes de a leitura acabar.
- **O fuso é assumido.** O desktop guardava a hora local sem fuso; assume-se o
  de Brasília. Uma tarefa criada às 23h30 noutro fuso pode aparecer no dia
  errado do gráfico.
- **Só as tarefas vêm.** Contas, estrutura de unidades, regras de automação,
  plugins e a auditoria do desktop ficam no desktop. As contas não podiam vir
  de qualquer forma — a web usa outro sistema de autenticação, e as
  palavras-passe não se transportam.
- As cópias de segurança `.zip` do desktop ainda não se aceitam; é preciso o
  `tarefas.db`.
