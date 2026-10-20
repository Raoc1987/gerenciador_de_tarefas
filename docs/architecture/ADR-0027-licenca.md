# ADR-0027 — Licença: AGPL-3.0 na plataforma web, MIT no desktop

Data: 2026-10-20 · Estado: aceite (decidido pelo autor a 2026-10-20: "pode ser
feita o que propõe se for a decisão certa e bem pensada")

## Contexto

O repositório é público e está todo sob MIT desde o início (`LICENSE`, de
2025). A plataforma web vai ser vendida como serviço (ADR-0025). Com MIT,
qualquer pessoa pode pegar no código e alojar um serviço concorrente fechado,
sem devolver nada. O desktop é outro caso: já está publicado (v1.1.0) e
congelado para funcionalidades (ADR-0017).

Medido a 2026-10-20 (`git log --format='%an <%ae>' | sort -u`): os commits são
do autor (Raoc1987 e Rodrigo Costa), do Claude, a trabalhar para o autor, e do
Dependabot (atualizações de versões). Não há contribuições externas, por isso o
autor pode mudar a licença das versões futuras sem pedir a ninguém.

## Decisão

1. **`web/` e `supabase/`: AGPL-3.0-only** (`web/LICENSE`, `supabase/LICENSE`;
   `"license": "AGPL-3.0-only"` em `web/package.json`). Quem alojar uma versão
   modificada como serviço tem de oferecer o código-fonte dessa versão a quem a
   usa (secção 13). Assim, um concorrente não fecha o código que recebeu.
2. **Desktop, ferramentas e o resto: MIT**, como até aqui (`LICENSE` na raiz).
   Mudar um produto publicado e congelado não traria nada.
3. **Licença comercial à parte.** Como titular de todos os direitos, o autor
   pode licenciar a plataforma em termos comerciais a quem não queira a AGPL
   (licenciamento duplo). Para isso continuar possível, quem contribuir para
   `web/` ou `supabase/` concede ao autor o direito de relicenciar o contributo
   (`CONTRIBUTING.md`).
4. `LICENSING.md` diz que licença vale para cada pasta, e um teste
   (`tests/test_licenca.py`) guarda a divisão e o texto da AGPL.

## O que se rejeitou

- **Manter MIT em tudo.** Simples, mas deixa a plataforma ser alojada fechada
  por outro, que é o que mais pesa num produto vendido como serviço.
- **Licença de código disponível** (BSL, FSL, Elastic): protege mais, porque
  proíbe o uso concorrente durante uns anos. Mas não é código aberto (não está
  aprovada pela OSI), afasta quem contribui e tira o argumento de confiança
  junto de empresas que querem poder sair com o código. A AGPL dá quase a mesma
  proteção prática e continua aberta.
- **GPL-3.0.** Não cobre o uso em rede: alojar o serviço não é "distribuir", e
  um concorrente fechava o código na mesma.
- **AGPL-3.0-or-later.** Deixaria a FSF decidir versões futuras; com "-only" a
  decisão fica com o autor.

## Consequências e limites

- **Não é retroativo.** O código publicado até hoje sob MIT continua MIT para
  quem já o tem: um fork de um commit anterior a esta mudança fica com MIT. A
  proteção vale daqui para a frente.
- **O autor não fica obrigado pela própria licença.** A secção 13 obriga quem
  recebe o código, não o titular. Ainda assim, se um dia a plataforma incorporar
  contributos de terceiros sem a concessão do ponto 3, passa a valer para esses
  contributos, e é preciso pôr na interface uma ligação ao código-fonte.
- **Isto não é aconselhamento jurídico.** Duas coisas pedem um jurista antes de
  aceitar o primeiro contributo externo ou de vender a primeira licença
  comercial: a redação da concessão no `CONTRIBUTING.md`, e o estatuto de
  direito de autor do código gerado com IA, que ainda não está assente em todas
  as jurisdições.
- As dependências da web (Next.js, React, supabase-js, o SDK da Anthropic) são
  MIT ou Apache-2.0, compatíveis com a AGPL-3.0.
