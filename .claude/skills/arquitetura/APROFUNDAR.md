# Aprofundar

Como aprofundar um conjunto de módulos rasos em segurança, conforme as suas
dependências. Usa o vocabulário de [LINGUAGEM.md](LINGUAGEM.md).

## Categorias de dependência

A categoria decide como o módulo aprofundado se testa através da costura.

1. **Em processo** — cálculo puro, estado em memória, sem I/O (as regras de
   `web/lib/dominio/`, a análise do desktop). Sempre aprofundável: junta os
   módulos e testa pela interface nova. Sem adaptador.
2. **Substituível localmente** — há um substituto de teste: o Postgres efémero
   de `supabase/tests/correr.sh` para a base, SQLite em memória para o
   desktop. Aprofundável; o módulo testa-se com o substituto a correr. A
   costura é interna.
3. **Remoto mas nosso** — os nossos próprios serviços através da rede (hoje:
   a base vista pela web através do PostgREST). Define uma **porta** na
   costura; a lógica fica no módulo fundo; o transporte entra como adaptador.
   Testes com um adaptador em memória; produção com o cliente real.
4. **Externo de verdade** — terceiros que não controlamos (Claude, Resend,
   Vercel Cron). O módulo recebe a dependência como porta injetada; os testes
   dão um adaptador falso. É o desenho do Copiloto (cliente injetado) e do
   carteiro (função `enviar` injetada).

## Disciplina das costuras

- **Um adaptador é uma costura hipotética; dois é uma real.** Não metas uma
  porta sem pelo menos dois adaptadores justificados (produção e teste). Uma
  costura com um adaptador é só indireção.
- **Costuras internas vs externas.** Não exponhas costuras internas na
  interface só porque os testes as usam.

## Testes: substituir, não empilhar

- Os testes antigos dos módulos rasos passam a ser desperdício quando existem
  testes na interface do módulo aprofundado — apagam-se.
- Os testes novos vivem na interface do módulo aprofundado. **A interface é a
  superfície de teste.**
- Verificam resultados observáveis pela interface, não estado interno.
- Sobrevivem a refatorações internas: se um teste muda quando a implementação
  muda, está a testar por trás da interface.

## Desenhar duas vezes

Para explorar interfaces alternativas de um candidato escolhido ("Design It
Twice", Ousterhout — a primeira ideia raramente é a melhor):

1. **Enquadra o problema** para a pessoa: as restrições que qualquer interface
   nova tem de cumprir, as dependências e a sua categoria, e um esboço de
   código só para tornar as restrições concretas (não é proposta).
2. **Gera desenhos radicalmente diferentes**, cada um com uma restrição:
   - minimizar a interface — 1 a 3 pontos de entrada, alavanca máxima em cada;
   - maximizar flexibilidade — muitos casos de uso e extensão;
   - otimizar para o chamador mais comum — o caso por omissão trivial;
   - (se aplicável) portas e adaptadores para as dependências que atravessam
     a costura.
   Com subagentes e a pessoa de acordo, um por restrição, em paralelo, cada um
   com um briefing técnico independente (caminhos, acoplamento, categoria, o
   que fica atrás da costura) e os dois vocabulários. Sem subagentes, faz-los
   tu, um de cada vez, sem deixar o primeiro contaminar os outros.
3. Cada desenho traz: a interface (tipos, métodos, parâmetros, invariantes,
   ordem, erros); um exemplo de uso; o que esconde; a estratégia de
   dependências; os compromissos.
4. **Apresenta e compara** em prosa — por profundidade, localidade e posição
   da costura — e dá a tua recomendação, com opinião. Se partes de desenhos
   diferentes combinam bem, propõe o híbrido.
