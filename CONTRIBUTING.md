# 🤝 Contribuir

Obrigado pelo interesse. Este guia diz o que é preciso saber antes de abrir um
PR — não repete o que já está no [README](README.md), que explica como pôr o
projeto a correr, como correr os testes e o que fazem o `--autoteste` e o
`--verificar-banco`.

O que este documento acrescenta é a parte que não se adivinha lendo o código:
**as regras que o projeto impõe, porque existem, e quais delas falham um teste
se forem violadas.**

---

## Antes de escrever a primeira linha

O projeto é um gestor de tarefas a crescer para plataforma modular. A regra que
organiza tudo o resto: **os módulos de negócio não entram no núcleo.**

Por isso, nada se escreve antes de estar classificado ([ADR-0004](docs/architecture/ADR-0004-classificacao-obrigatoria.md)).
Quatro perguntas:

1. Quantos módulos precisam disto? Um? Então não é Core.
2. O produto funciona sem isto? Sim? Então é Module ou Plugin.
3. Isto decide alguma coisa, ou só calcula? Decide? Então é Agent.
4. Isto traz uma dependência nova? Então tem de ser Plugin ([ADR-0002](docs/architecture/ADR-0002-graficos-sem-dependencias.md)).

A resposta fica registada em [`docs/architecture/CLASSIFICACAO.md`](docs/architecture/CLASSIFICACAO.md),
e há um teste que falha se aparecer uma peça nova que lá não conste.

Para mudanças grandes, abra primeiro uma *issue*. Uma decisão de arquitetura
discutida antes custa uma conversa; discutida depois custa um PR inteiro.

---

## As regras que um PR tem de respeitar

Estas não são preferências de estilo: cada uma tem um teste em
[`tests/test_arquitetura.py`](tests/test_arquitetura.py) que falha quando é
violada. Uma regra que não falha um teste é uma sugestão ([ADR-0004](docs/architecture/ADR-0004-classificacao-obrigatoria.md)).

| Regra | Porquê | O que falha |
|---|---|---|
| **Só a biblioteca padrão** em `src/` e `plugins/`; `requirements.txt` fica vazio | Mantém o executável pequeno e a instalação sem compilação nativa ([ADR-0002](docs/architecture/ADR-0002-graficos-sem-dependencias.md)) | `test_a_aplicacao_so_usa_a_biblioteca_padrao` |
| **As camadas não se invertem**: o core não importa interface nem análise; análise e relatórios não importam interface | Um núcleo que conhece a janela deixa de ser reutilizável ([ADR-0001](docs/architecture/ADR-0001-nucleo-fino.md)) | `test_o_core_nao_conhece_a_interface` |
| **Um módulo novo em `src/core/` precisa de justificação escrita** em `core-inventory.json` | Sem atrito, tudo acaba no núcleo | `test_tudo_no_core_esta_inventariado` |
| **Nomes de topo em português e declarados** em `nomes-de-topo.json` | `src/` está no `sys.path`: um nome genérico colide com um pacote do PyPI, e foi assim que um build parou com os testes todos verdes ([ADR-0005](docs/architecture/ADR-0005-nomes-de-topo.md)) | `test_todo_o_nome_de_topo_esta_declarado` |
| **Um plugin só toca na aplicação pelo `ContextoPlugin`** — nada de `banco_de_dados`, `gui` ou `PluginManager` | É o que permite mudar o interior sem partir plugins de terceiros | `test_nenhum_plugin_fura_o_contrato` |
| **Nenhum ecrã escolhe a sua própria cor ou letra** — use os tokens da paleta | Onze valores copiados por doze ficheiros davam 3,67 de contraste, abaixo do mínimo da norma; a olho não se vê a diferença para 4,5 ([ADR-0008](docs/architecture/ADR-0008-aparencia.md)) | `test_nenhum_ecra_escolhe_a_sua_propria_cor`, `test_nenhum_ecra_escolhe_a_sua_propria_letra` |
| **Mexer num plugin embutido obriga a subir a `version`** do manifesto | É o número que decide se a correção chega a quem já tem o plugin instalado ([ADR-0006](docs/architecture/ADR-0006-posse-dos-plugins.md)) | `test_mexer_num_plugin_embutido_obriga_a_subir_a_versao` |

E duas que nascem do produto, não da arquitetura:

- **A auditoria não guarda o conteúdo das tarefas.** Que a tarefa 12 foi
  removida é um facto auditável; o que ela dizia não é assunto da trilha. Um
  campo novo em `antes`/`depois` tem de constar da lista explícita em
  `core/auditoria.py` — sem isso, a auditoria passava a ser a maior fuga de
  dados da aplicação.
- **Os dados do utilizador vivem fora da pasta do programa.** Banco,
  configurações e plugins ficam em `%APPDATA%`, nunca junto do executável: é o
  que faz com que atualizar ou reinstalar não apague nada.

---

## Testes

```bash
python -m pytest
```

São mais de mil, e passam todos antes de qualquer PR ser aceite. Os que
constroem janelas Tkinter são ignorados sozinhos onde não há interface gráfica.

O que se espera de um teste novo:

- **Que falhe antes da correção.** Um teste escrito depois do código, que passa
  à primeira, não prova que apanha o defeito. Confirme que fica vermelho.
- **Que diga o que obteve quando falha.** Uma linha `assert x == y` sem
  mensagem obriga quem lê o registo do CI a adivinhar.
- **Que teste a regra, não a implementação.** Renomear uma função interna não
  devia partir vinte testes.

Para ver onde a suíte não chega: `python -m pytest --cov=src --cov-report=term-missing`.

---

## Documentação que acompanha a mudança

| Se o PR… | …atualize também |
|---|---|
| muda comportamento visível | `CHANGELOG.md`, secção "Não lançado" ([Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)) |
| toma uma decisão de arquitetura | um ADR novo em `docs/architecture/`, com **Decisão** e **Consequências** |
| acrescenta um módulo em `src/core/` | `core-inventory.json` |
| acrescenta um nome de topo em `src/` | `nomes-de-topo.json` |
| acrescenta uma funcionalidade | `docs/architecture/CLASSIFICACAO.md` |
| mexe num plugin embutido | a `version` do manifesto e `plugins-embutidos.json` (`python tools/inventario_plugins.py`) |
| muda uma rotina de manutenção | `docs/MANUTENCAO.md` |

Um documento que fica a mentir é pior do que documento nenhum — e há testes que
falham quando estas listas ficam para trás do código.

---

## Commits e PRs

Formato usado no projeto:

```
tipo(escopo): o que muda, em minúsculas e sem ponto final
```

`tipo` é `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. O corpo da
mensagem é onde se explica **porquê** — que sintoma apareceu, que alternativa
foi posta de lado e o que custou a decisão. O código diz o que faz; a mensagem
existe para dizer o resto.

Um PR bom:

- faz **uma** coisa, e cabe numa revisão de cabeça fresca;
- descreve o que mudou, o que ficou de fora e porquê;
- não traz ficheiros gerados (`dist/`, `build/`, `installer/Output/`, `.coverage`);
- passa no CI — `pytest` em Windows e Linux, Python 3.10 e 3.13, mais o
  `--autoteste` e a construção do executável.

O CI corre a cada *push* e a cada PR. Os ensaios do instalador e da atualização
(`tools/testar_instalador.py`, `tools/testar_atualizacao.py`) são pesados: não
correm em cada PR, mas correm no agendamento semanal, a pedido em
**Actions → Run workflow**, e sempre que se marca uma versão.

---

## Empacotamento

```bash
python tools/build.py           # .exe, e valida-o com --version e --autoteste
python tools/build_installer.py # instalador (requer Inno Setup 6)
```

`tools/build.py` só termina com sucesso depois de executar o executável que
acabou de gerar. Um build que não abre a aplicação não é um build válido.

---

## Como sai uma versão

A release sai de uma **etiqueta**, não de cada integração: isto instala-se em
máquinas de outras pessoas, e cada versão publicada é uma versão que alguém
pode ter.

1. `core/version.py` sobe primeiro — é a fonte única da versão, lida pela
   aplicação, pelo PyInstaller e pelo Inno Setup.
2. O `CHANGELOG.md` fecha a secção "Não lançado": as notas da release saem de
   lá (`tools/notas_da_versao.py`), revistas como o resto, em vez de escritas à
   pressa na caixa do GitHub.
3. `git tag v1.2.3 && git push origin v1.2.3` dispara o `release.yml`, que
   antes de construir seja o que for confirma que a etiqueta diz o mesmo que o
   código (`tools/verificar_versao.py`), corre a suíte, constrói o executável e
   o instalador, e corre **sempre** os dois ensaios — atualização e instalador
   de ponta a ponta.

A etiqueta não define a versão: **confirma-a**. Uma etiqueta que não bate certo
com `core/version.py` faz o workflow parar antes de publicar seja o que for —
fica a etiqueta, não fica a release, e essa etiqueta tem de ser apagada antes de
se voltar a tentar.

---

## Plugins

Um plugin é uma pasta com `plugin.json` e um ponto de entrada:

```json
{
  "id": "exemplo",
  "name": "Exemplo",
  "version": "1.0.0",
  "min_app_version": "1.0.0",
  "entry_point": "plugin.py",
  "permissions": ["tarefas.ler"]
}
```

`id`, `name`, `version`, `entry_point` e `min_app_version` são obrigatórios
e `max_app_version` é opcional. O `permissions` é opcional para o carregador mas
exigido aos plugins embutidos por um teste — e **ausente não é o mesmo que
vazio**: vazio afirma "não acede a nada", ausente é um esquecimento. Uma
permissão não declarada é recusada em tempo de execução, o que faz o plugin
instalar-se para falhar mais tarde.

`python tools/empacotar_plugin.py <pasta>` produz o `.zip` instalável.

Um plugin que funciona em desenvolvimento e falha no `.exe` costuma ter um
módulo em falta nos `hiddenimports` do `.spec`.

Se mexer num plugin **embutido**, suba a `version` do manifesto e
regenere o inventário com `python tools/inventario_plugins.py` — há um teste que
compara a impressão digital do conteúdo com a versão declarada e falha quando o
conteúdo muda e o número fica na mesma. Não é burocracia: foi assim que o
Calendar passou a declarar as permissões de que precisava e continuou a falhar a
ativação, durante uma versão inteira, em todas as instalações que já existiam.

O [ADR-0006](docs/architecture/ADR-0006-posse-dos-plugins.md) explica o resto:
a aplicação só substitui a cópia instalada enquanto ela for dela e ninguém lhe
tiver tocado. A partir do momento em que o utilizador instala um pacote seu por
cima, o plugin passa a ser dele e a semeadura deixa de lhe tocar — não conte com
ela para corrigir a cópia de quem já lhe mexeu.

---

## Reportar um problema

Uma *issue* útil traz, além do que aconteceu e do que era esperado:

- a versão — `GerenciadorDeTarefas.exe --version`, ou a entrada do programa
  em *Aplicações instaladas* do Windows (a janela não a mostra);
- o Windows e, se correr a partir do código, a versão do Python;
- `%APPDATA%\GerenciadorDeTarefas\logs\app.log` — **confirme que não leva dados
  que não queira partilhar** antes de o anexar;
- para suspeitas de dados corrompidos, a saída de `--verificar-banco`;
- para problemas de arranque, a de `--autoteste`.

---

## Licença

Ao contribuir, aceita que o seu contributo seja distribuído sob a licença
[MIT](LICENSE) do projeto.
