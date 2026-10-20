# ADR-0026 — Interruptores de funcionalidade por empresa, na base

Data: 2026-10-20 · Estado: aceite (decidido pelo autor a 2026-10-20)

## Contexto

Antes do primeiro cliente pago é preciso poder ligar uma funcionalidade a
algumas empresas antes das outras, ou desligá-la só numa: uma novidade em
ensaio, um serviço caro, o pedido de um cliente. É a regra "nada vai para todos
ao mesmo tempo" do catálogo de práticas (`docs/conhecimento/catalogo.json`).

O autor pôs uma condição: **uma empresa nunca pode ter acesso a dados de
outra**. Um interruptor é um dado da empresa. Saber que outra empresa tem uma
funcionalidade ligada já seria uma fuga.

## Decisão

1. **Os interruptores vivem na base** (ADR-0017), em duas tabelas:
   - `funcionalidades`: o catálogo, com o valor por omissão de cada uma;
   - `funcionalidades_empresa`: as exceções por empresa, com o motivo.
2. **Só o operador do serviço escreve.** `authenticated` só tem `select`.
   Nenhum papel, nem o proprietário, liga ou desliga uma funcionalidade. Muda-se
   por migração ou com a chave de serviço, e cada mudança fica na auditoria da
   empresa (gatilho `registar_auditoria`).
3. **Cada membro lê só a sua empresa.** A política de leitura é
   `e_membro(empresa_id)`. `funcionalidade_ligada(empresa, código)` responde
   `false` a quem não é membro, seja qual for o valor. Assim não se distingue
   uma funcionalidade ligada noutra empresa, desligada, ou uma empresa que não
   existe.
4. **Quem recusa é a base.** Cada funcionalidade com interruptor tem um gatilho
   ou uma função que recusa quando está desligada. A interface só esconde. O
   primeiro é o Copiloto: a pergunta é recusada na reserva, antes do limite do
   plano e antes de haver custo.

## O que se rejeitou

- **Um serviço externo de feature flags**, ou o Edge Config do Vercel. É um
  sítio a mais com dados das empresas, e a decisão ficava fora da base, onde a
  RLS não chega. O Postgres já tem o que é preciso (avaliador de tecnologia,
  filtro 3: o nativo primeiro).
- **Variáveis de ambiente.** Valem para todas as empresas ao mesmo tempo, que é
  justamente o que se quer evitar.
- **Deixar o proprietário ligar e desligar.** Um interruptor de lançamento é do
  operador. O que é preferência da empresa fica nas definições da empresa.

## Consequências

- Uma funcionalidade nova com risco entra desligada por omissão e liga-se por
  empresa.
- O teste `supabase/tests/53_interruptores.sql` guarda o isolamento. Foi visto a
  falhar com a política aberta a todos e com a verificação de membro tirada da
  função.
- Ainda não há ecrã de operador. Liga-se por SQL, no workflow da base ou com a
  chave de serviço. Um ecrã fica para quando houver mais do que uma mão-cheia
  de empresas.
