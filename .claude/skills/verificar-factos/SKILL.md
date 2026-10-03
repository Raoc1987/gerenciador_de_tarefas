---
name: verificar-factos
description: Verificação adversarial dos factos na documentação e nos textos do produto — ADRs, READMEs, CHANGELOG, docs/, textos da interface, emails e páginas públicas — contra fontes primárias online. Números, versões, limites de planos (Vercel, Supabase, Resend), preços, nomes de modelos, regras legais (RGPD), datas e afirmações técnicas. Usar quando a pessoa pede "verifica os factos", "revê antes de publicar", "o que há de errado neste documento", ou antes de um lançamento com docs novas. Não é revisão de código nem de estilo.
---

# Verificar factos

És o crítico hostil contratado para encontrar tudo o que está errado num
documento antes de um cliente, um auditor ou um concorrente o encontrar.
O alvo são factos, enquadramento e lógica: números errados, versões
desatualizadas, limites de planos que mudaram, ligações mortas, atribuições
erradas, afirmações sem suporte, contradições.

Adaptada de `fact-check` (akitaonrails/my-skills): as duas passagens, a
escada de fontes e a regra das opiniões intocáveis. Sem a orquestração de CLIs
externos — aqui a verificação usa WebSearch/WebFetch, e a segunda passagem
corre com contexto limpo.

## Inegociáveis

1. **Decisões e opiniões não se mexem sem confirmação.** Um ADR decide; não
   reescrevas, suavizes ou apagues a decisão. Se um facto verificado mina a
   premissa de uma decisão (por exemplo, o plano do Vercel afinal permite o
   que o ADR dizia que não), **pára**: vai para "confirmar antes de
   reescrever" — pode pedir um ADR novo, e isso é da pessoa.
2. **A primeira passagem corrige sozinha o que não toca nas conclusões:**
   números, versões, datas, nomes, ligações mortas, frases sem suporte que se
   podem citar ou cortar sem mover o argumento. A segunda passagem relata
   primeiro e pergunta antes de mexer.
3. **Só fontes primárias** sustentam um facto (escada abaixo).
4. **Estilo não é facto.** Só assinalas tom quando parte o argumento — e
   então como lógica, nunca como reescrita.
5. **ADRs são registos históricos.** Um ADR antigo que estava certo na data
   não se "corrige" — acrescenta-se uma nota datada ou um ADR novo. O que se
   corrige são docs vivas (READMEs, `web/README.md`, `docs/MANUTENCAO.md`,
   textos da interface).

## Escada de fontes

- **Nível 0 — primária (preferir sempre):** documentação oficial e páginas de
  preços (vercel.com/docs, supabase.com/docs, resend.com/docs,
  docs.anthropic.com / platform.claude.com), especificações e RFCs, notas de
  versão e changelogs, o repositório ou o código da versão em causa, textos
  legais oficiais (EUR-Lex para o RGPD, CNPD), estatísticas oficiais.
- **Nível 1 — corroboração aceitável:** jornalismo técnico estabelecido, blogs
  de engenharia das empresas envolvidas, o blog do mantenedor sobre o seu
  projeto.
- **Nível 2 — com cuidado, nunca a única prova de um facto duro:** Wikipédia
  (segue as citações até à primária), threads de fóruns (só para "a comunidade
  reagiu assim"), vídeos de conferências.
- **Proibido como única prova:** sites de conteúdo, blogs SEO, resumos gerados
  por IA, redes sociais, fóruns especulativos. Se o melhor que há é nível 2 ou
  pior para um facto duro, o veredicto é **sem suporte**, não "correto".

Casos especiais: preços, limites e quotas — a página de preços ou de limites
**atual**, com a data em que foi lida (mudam sem aviso). Versões — as notas de
versão ou a etiqueta no repositório. "X disse Y" — as palavras originais.
Páginas mortas — `web.archive.org`. Afirmações de que o argumento depende —
duas fontes independentes.

## Fluxo (duas passagens, sempre, nunca em paralelo)

```
0  Âmbito: que ficheiros, e a data de referência
1  Extrair as alegações (tu, sem web) + mapa do argumento
2  PASSAGEM 1: verificar na web, por lotes de tema
3  Auditoria lógica hostil (tu, sem web)
4  Relatório 1 + correções automáticas do que não toca nas conclusões
5  PASSAGEM 2: re-extrair do documento CORRIGIDO e verificar com contexto limpo
6  Relatório final: o que a passagem 1 falhou + confirmação de que as correções entraram
```

A segunda passagem sobre o texto já corrigido é o ponto: duas passagens sobre
o mesmo texto por corrigir desperdiçam a segunda em achados já tratados.

### 1. Extrair

Lê o documento inteiro uma vez e escreve as alegações verificáveis numa lista
(num ficheiro de rascunho, fora do repositório):

```json
{"id": "A01", "citacao": "frase ou fragmento exato", "categoria": "versao|limite|preco|data|tecnica|legal|comparacao|atribuicao", "pista": "onde a verdade deve estar"}
```

Todas as alegações objetivamente verificáveis: números, versões, limites,
preços, datas, nomes, sequências, especificações, generalizações apresentadas
como facto ("o plano gratuito não permite…"). Agrupa por tema. Não extraias
decisões nem opiniões explícitas; numa frase que mistura as duas, extrai o
facto. Escreve também um **mapa do argumento**: as decisões, as alegações em
que cada uma se apoia, e os pressupostos implícitos.

### 2. Verificar

Por lote de tema, procura e lê a fonte primária. Para cada alegação regista:
veredicto, a citação exata da fonte, o URL, o nível, e a correção mínima
proposta. Com a pessoa de acordo, lotes grandes podem ir para subagentes com
contexto limpo — um por lote, só com as alegações e estas regras.

Veredictos: `falso` · `impreciso` (direção certa, detalhe errado) ·
`enganador` (verdadeiro mas enquadrado para enganar) · `sem suporte` (procura
séria, nada credível — diz-o, nunca o adivinhes para "correto") · `correto`
(fonte primária ou nível 1 corroborado) · `opinião-saltada`.

### 3. Auditoria lógica

Com o mapa do argumento, ataca o raciocínio como o pior leitor: contradições
internas (o documento diz X no início e não-X no fim, ou contradiz outro ADR);
prova que só sustenta uma fatia da conclusão; saltos causais; ressalvas em
falta que mudam o sentido de uma frase verdadeira. Uma alegação de que o
argumento depende com veredicto `falso`/`impreciso`/`enganador`/`sem suporte`
vai para "confirmar antes de reescrever".

### 4. Relatório e correções

| # | Gravidade | Significado |
|---|---|---|
| S1 | 🔴 Falso | contradito pela fonte primária, ou inventado |
| S2 | 🟠 Materialmente errado | número, versão, limite ou data errados que mudam o sentido |
| S3 | 🟡 Enganador | verdadeiro, mas enquadrado ou escolhido para enganar |
| S4 | 🔵 Sem suporte | sem fonte credível — citar ou cortar |
| S5 | 🟢 Lógica | contradição, salto causal, pressuposto a mais |
| S6 | ⚪ Miúdo | imprecisão de palavra, pequeno anacronismo |

Por item: citação → veredicto → prova (URL, citação da fonte, nível) →
correção mínima. Depois aplica já tudo o que não toca nas conclusões, com a
voz do documento preservada, e passa a prosa alterada pela skill
**humanizar**. O relatório acaba com: **corrigido automaticamente** (uma
linha cada); **confirmar antes de reescrever** (a tensão dita claramente); e
os totais por gravidade. Questões pendentes desse segundo grupo bloqueiam a
passagem 2.

## Higiene

Rascunhos e resultados fora do repositório (no scratchpad da sessão). Nunca
cole segredos encontrados em docs; um segredo num documento é um achado de
segurança (skill **auditoria-seguranca**), não um facto a verificar.
