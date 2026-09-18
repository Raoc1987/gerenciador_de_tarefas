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
(`tools/testar_instalador.py`, `tools/testar_atualizacao.py`) são pesados e só
correm no agendamento semanal ou a pedido, em **Actions → Run workflow**. Antes
de uma release, corra-os.

---

## Empacotamento

```bash
python tools/build.py           # .exe, e valida-o com --version e --autoteste
python tools/build_installer.py # instalador (requer Inno Setup 6)
```

`tools/build.py` só termina com sucesso depois de executar o executável que
acabou de gerar. Um build que não abre a aplicação não é um build válido.

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

`id`, `name`, `version`, `entry_point` e `min_app_version` são obrigatórios;
`max_app_version` e `permissions` são opcionais. Uma permissão que não esteja
declarada no manifesto é recusada em tempo de execução — declarar é a forma de
o utilizador saber o que o plugin vai fazer antes de o ativar.

`python tools/empacotar_plugin.py <pasta>` produz o `.zip` instalável.

Um plugin que funciona em desenvolvimento e falha no `.exe` costuma ter um
módulo em falta nos `hiddenimports` do `.spec`.

Se mexer num plugin **embutido**, leia primeiro o
[ADR-0006](docs/architecture/ADR-0006-posse-dos-plugins.md): a aplicação só
substitui a cópia instalada enquanto ela for dela e ninguém lhe tiver tocado —
inclusive quando muda só o manifesto, sem subir a `version`. A partir do
momento em que o utilizador instala um pacote seu por cima, o plugin passa a
ser dele e a semeadura deixa de lhe tocar. Não conte com a semeadura para
corrigir a cópia de quem já lhe mexeu.

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
