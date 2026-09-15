# ADR-0006 — Um plugin embutido é da aplicação; um plugin instalado é do utilizador

Data: 2026-09-15 · Estado: aceite

## Contexto

Os plugins que acompanham a aplicação (`plugins/available/`) são copiados para
a pasta do utilizador no primeiro arranque. A regra da semeadura era uma só, e
estava escrita na docstring: *nunca substituir um plugin já instalado — a
versão do utilizador manda, mesmo que seja mais antiga.*

A intenção era boa e a consequência não foi pensada: **um plugin que acompanha
a aplicação era instalado uma vez e nunca mais.** Nenhuma correção de
segurança, nenhuma permissão nova, nenhuma tradução nova chegava a uma
instalação que já existisse. Subir a versão do plugin não resolvia nada,
porque a versão não era sequer consultada.

Descobriu-se pelo sintoma. O Calendar passou a declarar no manifesto as
permissões de que precisa (commit `0fc4c06`); numa instalação a sério, o
autoteste continuou a dar:

```
[FALHA] ativar plugin calendar — O plugin não declarou a permissão 'tarefas.ler' no manifesto.
```

O manifesto corrigido estava no repositório. O manifesto em disco, na máquina
de quem já tinha o programa, era o antigo — e continuaria a sê-lo para sempre.

Com um diretório de dados limpo passava tudo. Não era uma regressão do código:
era um buraco no caminho de atualização, que só se vê em quem já usa o
produto.

## Decisão

Um plugin instalado passa a ter **dono**, e o dono decide quem lhe pode tocar.

| Posse | Quem o pôs lá | A semeadura pode substituí-lo? |
|---|---|---|
| **embutido** | a aplicação, na semeadura | **sim** — quando a versão embutida é mais recente e ninguém lhe mexeu |
| **utilizador** | o próprio, de um `.zip` (ou da futura loja) | **não** — só com uma ação explícita dele |

Quem instala por último é o dono. Instalar um pacote próprio por cima de um
plugin embutido transfere-o para o utilizador, e a semeadura deixa de lhe
tocar.

Para saber se "ninguém lhe mexeu" não basta a posse: guarda-se também a
**impressão digital** do conteúdo no momento em que foi instalado
(`core.plugin_package.impressao_da_pasta`). No arranque, a pergunta é feita a
cada plugin embutido e tem quatro respostas possíveis
(`SemeaduraDecisao`):

| Decisão | Situação | O que acontece |
|---|---|---|
| `INSTALAR` | não está em disco | instala |
| `ATUALIZAR` | é nosso, intacto, e a versão embutida é mais recente | **substitui** |
| `EM_DIA` | é nosso e está igual | nada |
| `MODIFICADO` | é nosso, mas o conteúdo já não é o que lá pusemos | nada — fica retido |
| `DO_UTILIZADOR` | passou a ser dele | nada — fica retido |

Uma exceção deliberada: um plugin **nosso cujo manifesto não se consegue ler**
é reposto mesmo que a impressão não bata certo. Uma pasta ilegível não é uma
personalização que valha a pena preservar, e deixá-la como está é deixar o
plugin partido à espera de um clique.

**A versão é o contrato.** A semeadura compara versões; corrigir um plugin
embutido sem lhe subir a versão é publicar uma correção que nunca sai do
repositório — exatamente o que aconteceu com o Calendar. Por isso há um
inventário (`plugins-embutidos.json`) com a versão e a impressão de cada um, e
um teste que falha quando o conteúdo muda e o número fica na mesma.

**Os dois casos retidos têm saída.** A tela *Configurações → Plugins* oferece
**Repor originais**: diz quais vai sobrepor, e só age depois de um sim. Não é
o arranque a decidir por ninguém — é o utilizador a desfazer uma escolha que
foi dele.

### Classificação (ADR-0004)

A posse de um plugin é **Core**: vive em `core/plugin_manager.py` e
`core/plugin_registry.py`, ao lado do resto do ciclo de vida dos plugins.
Não é uma funcionalidade nova — é uma regra que faltava ao Plugin Engine, que
já lá estava classificado como Core. Não entra nada de novo no inventário do
núcleo.

## Consequências

**Boas**

- Uma correção num plugin embutido chega a quem já o tem instalado. Era o que
  não acontecia, e é a razão de tudo isto.
- Um plugin que o utilizador instalou continua intocável — que era a intenção
  da regra antiga, agora com um critério em vez de uma suposição.
- A trilha de auditoria diz quem substituiu o quê: o evento
  `plugin.atualizado` passa a registar também a proveniência, e portanto a
  distinguir "a aplicação repôs um plugin seu" de "alguém instalou um pacote".
- Mexer num plugin embutido sem subir a versão deixa de ser possível sem
  reparar nisso.

**Custos**

- Mais uma migração de banco (v12) e mais duas colunas na tabela `plugins`.
- Alterar um plugin embutido passa a ter dois passos em vez de um: subir a
  versão e correr `python tools/inventario_plugins.py`.
- **A adoção tem um preço, e é preciso dizê-lo.** Uma instalação anterior a
  esta versão não regista de quem é cada plugin nem o que a aplicação lá pôs.
  Na primeira semeadura depois da atualização, os plugins embutidos que
  estiverem em disco são adotados pela aplicação, com o conteúdo de hoje como
  ponto de partida. Quem tiver editado à mão um plugin embutido **antes** desta
  versão não é reconhecível, e a primeira atualização embutida passa-lhe por
  cima. A alternativa — não adotar nada — deixava a proteção por estrear e o
  Calendar por corrigir em todas as instalações que existem. Daqui para a
  frente, uma modificação feita à mão é detetada e respeitada.
- A impressão digital lê todos os ficheiros de cada plugin embutido no
  arranque. São quatro plugins pequenos; se um dia forem muitos ou grandes,
  isto volta a ser uma decisão.

## Como se sabe que está a ser cumprido

`tests/test_plugin_semeadura.py` percorre as cinco decisões, a adoção, a
reposição, o registo na auditoria — e o caso de origem, em
`test_correcao_de_permissoes_chega_a_uma_instalacao_existente`: um plugin
instalado sem as permissões que precisa, um embutido corrigido, e a correção a
chegar.

`tests/test_arquitetura.py` guarda as duas regras que impedem a recaída:

- `test_mexer_num_plugin_embutido_obriga_a_subir_a_versao` — o conteúdo mudou
  e a versão não: falha, e diz o que fazer;
- `test_cada_plugin_embutido_declara_o_acesso_que_usa` — um manifesto sem
  `permissions` é um esquecimento, não uma afirmação. Foi este que apanhou o
  segundo caso, no plugin de atualizações.

`tests/test_gui.py` cobre a reposição pela tela, incluindo o caso em que não
há nada a repor.
