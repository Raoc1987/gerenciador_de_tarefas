# Método de trabalho

Data: 2026-10-08. Vinculativo para pessoas e agentes neste repositório.

Este método vem do ALKMIA (`Raoc1987/ALKMIA`, `docs/BIBLIA.md` Parte I e
`docs/PROJETO-CRIACAO-SENIOR.md`), lido sem nada lá alterar. Os dois produtos
são diferentes, e só veio o que serve aos dois: as regras de como se trabalha,
não as regras do produto (saúde, treino, nutrição ficam lá). Cada regra traz um
incidente **deste** repositório, porque uma regra sem cicatriz própria
esquece-se. O que se trouxe, o que se adaptou e o que se recusou, com o
porquê, está em [`conhecimento/catalogo.json`](conhecimento/catalogo.json), e
`tools/conhecimento.py` analisa-o (ver o fim deste documento).

---

## 1. Níveis de verificação

Toda a afirmação sobre o estado do sistema diz o nível a que foi verificada.
Os níveis não são sinónimos e não se arredondam para cima.

| Nível | Quer dizer | Prova |
|---|---|---|
| **implementado** | o código existe num ramo | o diff |
| **testado** | os testes que o guardam passam, e viu-se pelo menos um falhar | saída dos testes, com a mutação |
| **integrado** | está na `main`, com o CI verde nesse SHA | o SHA e o run |
| **aplicado** | a migração ou a configuração chegou ao ambiente | `supabase migration list`, variáveis no Vercel |
| **verificado em produção** | alguém o viu funcionar lá | `ensaio:fumo`, registos, captura com data |

*Cicatriz (2026-10-07):* o workflow `Base de dados — produção` terminou a verde
depois dos merges de #51 a #56, e nenhuma migração tinha sido aplicada: o
passo "Sem SUPABASE_DB_URL" passou e os outros saltaram. Verde era
**integrado**, não **aplicado**. No mesmo dia, as pré-visualizações do Vercel
diziam "Ready" e respondiam 500 a todos os pedidos, porque o projeto não tinha
nenhuma variável de ambiente.

## 2. O protocolo, em seis passos

Para trabalho novo: funcionalidades, tecnologias, ferramentas. Cada passo tem
uma saída; sem ela, não se passa ao seguinte.

1. **Medir.** Nada se propõe sobre memória, resumo ou registo de tarefas.
   *Saída:* três a seis números, com data e fonte. Se a pergunta não tem
   números que a respondam, o primeiro trabalho é construir a medição.
2. **Propor com o que se rejeita.** Duas listas: o que se faz e o que se
   decidiu não fazer, com o preço de cada.
   *Saída:* a alternativa rejeitada está escrita, com o porquê numa frase.
3. **Decidir o que é do humano.** Preço, nome, identidade publicada, licença,
   lei aplicável, mercado, e tudo o que seja irreversível ou virado para fora.
   *Saída:* decidido por quem devia, ou marcado como suposição com o custo de
   estar errada.
4. **Executar cirurgicamente.** Uma verdade num sítio só; quando tiver de
   viver em dois (TypeScript e um `check` de SQL), um teste compara-os.
   *Saída:* os testes da área passam.
5. **Provar que a prova falha.** Um teste que nunca se viu falhar é decoração.
   Muta-se o código, vê-se o vermelho, repõe-se.
   *Saída:* o PR diz como se viu o teste falhar.
6. **Registar na mesma alteração.** CHANGELOG, ADR, docs de estado: no mesmo
   PR, com o nível de verificação. Um documento de estado desatualizado é pior
   do que nenhum, porque é lido com confiança.

O passo 1 e o 5 são do agente `medidor`; o plano de prova é da skill
`plano-de-verificacao`.

## 3. As regras

Cada uma tem a referência ao ALKMIA de onde veio (M = regra de método da
BIBLIA) e o incidente deste repositório que a justifica aqui.

**R1. Verificar no código e no ambiente, nunca num resumo** (M1).
Um registo de tarefas, um resumo de sessão ou uma descrição de PR dizem o que
alguém pensou. *Cicatriz:* o resumo desta sessão dava a pré-visualização como
"pronta"; os registos do Vercel diziam `Faltam NEXT_PUBLIC_SUPABASE_URL`.

**R2. Implementado não é verificado** (M6). Ver §1.

**R3. Erro engolido paga-se em horas** (M3). Nenhum ramo troca um erro real
por uma mensagem genérica sem o registar. Na Vercel ninguém lê `console.error`
de uma rota que respondeu 200. *Cicatriz:* a ação do Copiloto ignorava o erro
do `insert` em `copiloto_uso`; desde os planos, esse insert podia ser recusado
pelo limite, tarde (com os tokens já gastos) e sem rasto. Corrigido: a pergunta
reserva-se antes de chamar o modelo, e a falha a registar os tokens vai para os
registos com o que é preciso para a reconstituir.

**R4. Há três mortes, e cada uma pede um instrumento** (M2, M14, M21).
- escrito e nunca lido: a coluna existe, ninguém a usa;
- lido e nunca escrito: o leitor recebe sempre o valor por omissão, e o
  sintoma parece "ainda não houve dados";
- exportado e nunca importado: o código parece vivo.

Procurar leitores não prova escrita, e vice-versa: verifica-se nos dois
sentidos. A terceira tem detetor: o teste de arquitetura falha com um valor
exportado em `web/lib` que ninguém usa (apanhou `ESTADOS_E_PRIORIDADES`).

**R5. Mudar a forma obriga a enumerar quem a lê** (M13). Antes de mudar um
tipo, um enum ou um formato, lista-se cada leitor e diz-se o que lhe acontece.
*Cicatriz:* `Tarefa` ganhou `pai_id` e um fixture de testes de relatórios
deixou de compilar. O typecheck local não o viu porque excluía os testes; o
CI viu.

**R6. Antes de acusar o código, verificar o instrumento** (método do ALKMIA,
regra 6). *Cicatriz:* o typecheck com stubs desta sessão dava "limpo" porque
o `tsconfig` excluía `*.test.ts`. O instrumento estava a medir menos do que
parecia.
Segunda vez, no PR #59: o erro novo estava na saída, entre dezenas de erros
conhecidos dos stubs, e passou à leitura. Com um instrumento ruidoso, compara-se
a lista de erros com a da base, não se lê a olho.

**R7. Verificar o estado não é verificar o evento** (M16, M20). Um histórico
diz o que aconteceu; não diz o que existe. A lista de deployments, o
`schema_migrations` e o log do CI são históricos. Para saber o que existe,
vai-se à fonte que remove entradas quando a coisa desaparece: o catálogo do
Postgres, a lista de variáveis do Vercel.

**R8. A disciplina falha; o procedimento apanha** (M19). Uma regra que só
existe como intenção quebra-se na primeira distração. Vira teste, hook ou
passo de CI. *Cicatriz:* o primeiro ciclo de merges desta sessão devia parar
à primeira recusa e não parou: os PRs seguintes mudaram de base sem ser
juntados. O segundo ciclo foi um script que sai ao primeiro erro.

**R9. Cobertura conta causas, não casos** (M9). Um teste vale pelas causas
distintas que apanha. Dez casos que falham pela mesma razão são uma guarda.
Por isso cada recusa da base é testada com o motivo verificado
(`t.recusa_por`): recusado pela razão errada não conta.

**R10. A ordem das verificações também é segurança.** Uma regra que responde
antes de verificar o acesso conta coisas a quem não as podia saber.
*Cicatriz:* o gatilho de dependências dizia "é mãe desta tarefa" a quem não
via nenhuma das duas, porque a RLS só atua depois do gatilho. O acesso passou
a ser verificado primeiro.

**R11. O nativo primeiro, e o que sai em troca** (filtros 3 e 7 do avaliador
do ALKMIA). Antes de uma dependência nova: dá para fazer com o Postgres, o
Next ou a biblioteca padrão que já lá estão? E o que sai? *Cicatriz positiva:*
o Stripe entrou sem SDK. A API é HTTP com formulários e o webhook é um HMAC,
o que coube em 150 linhas testadas.

**R12. O que é do autor não se decide sozinho** (passo 3). Preços, licença,
nome legal, textos públicos. *Cicatriz:* os valores dos planos entraram como
proposta marcada como tal no PR #56, à espera de decisão.

## 4. O que NÃO veio do ALKMIA, e porquê

Não veio nada que dependa do produto: os mandamentos de treino, nutrição e
biologia, o design "Onyx & Gold", o agente de movimento, a integridade de
séries de treino. Também ficou lá a doutrina de nomes (dois produtos, duas
marcas, e nada a varrer aqui). O catálogo regista cada recusa com a razão;
`tools/conhecimento.py triagem` mostra o que ainda não foi decidido.

## 5. O prompt de sessão

Para colar no início de uma sessão de trabalho novo. Curto de propósito.

```
Gerenciador de Tarefas — trabalho novo.

Lê CLAUDE.md e docs/METODO.md. O pedido: <descrever>.

Segue os seis passos do METODO §2 e não saltes o primeiro:
1. Mede antes de propor, com data e fonte. Se uma premissa minha estiver
   errada, corrige-a com a medição à frente.
2. Propõe com duas listas: o que fazes e o que não fazes, com o preço.
3. Pergunta-me o que é meu (preço, licença, nome, textos públicos, tudo o
   irreversível). Não inventes nenhum.
4. Executa cirurgicamente. A autoridade é a base (ADR-0017).
5. Prova, e prova que a prova falha: mostra o vermelho.
6. Regista no mesmo PR, com o nível de verificação (METODO §1).

Diz-me o que ficou por verificar e porquê. Sem pontuações nem listas de
vistos: números com data, e o que eles não dizem.
```

## 6. As ferramentas

| O quê | Onde | Para quê |
|---|---|---|
| Catálogo de práticas | `docs/conhecimento/catalogo.json` | o que se usa nos dois projetos, com os critérios e a decisão |
| Analisador | `python tools/conhecimento.py relatorio` | quanto do método está guardado por procedimento e quanto só em prosa; dívidas; desencontros com o repositório |
| Triagem | `python tools/conhecimento.py triagem --alkmia <caminho>` | práticas novas do outro projeto ainda por decidir (só leitura) |
| Nota para o ALKMIA | `docs/conhecimento/PARA-O-ALKMIA.md`, gerada por `python tools/conhecimento.py alkmia --escrever` | o que nasceu aqui e serve lá, com a medição feita lá e como aplicar; ler no início de uma sessão no ALKMIA |
| Agente `medidor` | `.claude/agents/medidor.md` | passos 1 e 5: números com data e fonte, só leitura |
| Agente `escrutinador-de-promessas` | `.claude/agents/escrutinador-de-promessas.md` | o que o produto afirma em público contra o que o código sustenta |
| Agente `avaliador-de-tecnologia` | `.claude/agents/avaliador-de-tecnologia.md` | os sete filtros antes de adotar uma dependência ou serviço |
| Hook do teste colocado | `.claude/hooks/teste-do-ficheiro.mjs` | depois de editar `web/lib/x.ts`, corre `x.test.ts` e só fala se falhar |
| Skill `reconciliar-esquema` | `.claude/skills/reconciliar-esquema/` | compara o esquema de produção com as migrações, por assinaturas |
| Ensaio do publicado | `.github/workflows/ensaio-publicado.yml` | o ensaio de fumo a cada deploy pronto no Vercel e, com `PRODUCAO_URL` definida, de hora a hora na produção |

## 7. O que corre a cada mudança

Cada camada apanha uma classe de quebra que as outras deixam passar. Nenhuma
se mede por "há testes": cada uma tem um mínimo que falha o CI.

| Camada | Onde | O mínimo que a guarda |
|---|---|---|
| Regras da base | `supabase/tests/correr.sh` | cada função de `public` e `interno` corre em pelo menos um teste (o Postgres conta as chamadas); exceções em `funcoes-sem-chamada.txt`, com a razão |
| Domínio e bibliotecas | `npm run test:cobertura` | cada módulo de `web/lib` alcançado por um teste (`arquitetura.test.ts`), e um mínimo de linhas, ramos e funções que só sobe |
| A aplicação inteira | `web/e2e/` no CI | Supabase local com as migrações reais, o build de produção e um browser; cada página visitada por um ensaio |
| O que está publicado | `ensaio-publicado.yml` | cada deploy pronto e a produção de hora a hora; barrado pela proteção do Vercel fica como aviso |
| O próprio CI | `tests/test_workflows.py` | Actions fixadas por SHA, `permissions:` em cada workflow |

*Cicatriz (2026-10-08):* antes destes mínimos, 3 módulos de `web/lib` não
tinham teste nenhum e ninguém o sabia; a contagem de chamadas mostrou que as
funções da base estavam todas exercidas, mas só porque se mediu.
