# 📝 Gerenciador de Tarefas / Task Manager

[![GitHub license](https://img.shields.io/github/license/Raoc1987/gerenciador_de_tarefas)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/Raoc1987/gerenciador_de_tarefas)](https://github.com/Raoc1987/gerenciador_de_tarefas/releases)
[![GitHub issues](https://img.shields.io/github/issues/Raoc1987/gerenciador_de_tarefas)](https://github.com/Raoc1987/gerenciador_de_tarefas/issues)

Plataforma desktop modular de gestão, com o gestor de tarefas como núcleo:
dashboard com indicadores e análise, múltiplos idiomas, calendário, banco
SQLite e um **sistema de plugins** com instalação, ativação, atualização e
remoção pela própria interface.

Só usa a biblioteca padrão do Python — sem dependências externas em execução.

## 🌐 Idiomas / Languages

- [Português (BR)](README.md)
- [English (US)](README.en.md)

---

## 📦 Instalação (utilizador)

1. Descarregue `GerenciadorDeTarefas-Setup.exe` da
   [página de releases](https://github.com/Raoc1987/gerenciador_de_tarefas/releases).
2. Execute o instalador. Por omissão instala só para o seu utilizador e **não
   pede permissões de administrador**; no primeiro ecrã pode escolher instalar
   para todos os utilizadores.
3. Abra pelo Menu Iniciar.

Onde ficam as coisas:

| O quê | Onde |
|---|---|
| Programa | `%LOCALAPPDATA%\Programs\GerenciadorDeTarefas` (ou `Program Files`) |
| Banco de dados | `%APPDATA%\GerenciadorDeTarefas\tarefas.db` |
| Configurações | `%APPDATA%\GerenciadorDeTarefas\config\` |
| Plugins instalados | `%APPDATA%\GerenciadorDeTarefas\plugins\installed\` |
| Logs | `%APPDATA%\GerenciadorDeTarefas\logs\app.log` |

Os seus dados ficam **fora** da pasta do programa: atualizar ou reinstalar não
os afeta. A desinstalação só os apaga se responder "sim" a uma pergunta
explícita.

---

## 💻 Desenvolvimento

```bash
git clone https://github.com/Raoc1987/gerenciador_de_tarefas.git
cd gerenciador_de_tarefas
pip install -r requirements-dev.txt
python src/main.py
```

Requer **Python 3.10+** com Tkinter (incluído no instalador oficial do Python
para Windows). `requirements.txt` está vazio de propósito: a aplicação não tem
dependências de execução. `requirements-dev.txt` traz `pytest` e `pyinstaller`.

### Testes

```bash
python -m pytest
```

Alguns testes constroem janelas Tkinter reais e são automaticamente ignorados
em ambientes sem interface gráfica.

Para ver onde a suíte não chega:

```bash
python -m pytest --cov=src --cov-report=term-missing
```

### Verificar o banco de dados

```bash
python src/main.py --verificar-banco
```

Mostra a versão do schema e o resultado de `PRAGMA integrity_check`. Abre o
banco **só de leitura**: é um diagnóstico, não aplica migrações nem repara
nada. É o primeiro passo quando se suspeita de dados corrompidos — ver
`docs/MANUTENCAO.md`.

### Verificar uma instalação

```bash
python src/main.py --autoteste
```

Verifica banco, idiomas, recursos, plugins e — o mais importante — **abre a
aplicação pelo caminho verdadeiro**: o mesmo `abrir_aplicacao()` que o
duplo-clique usa, confirmando que a janela de início de sessão e a janela
principal chegam mesmo a estar visíveis.

Essa última parte existe porque faltava: o autoteste construía a janela
principal diretamente e dava "OK" enquanto o programa, aberto a sério, ficava
a correr sem nada no ecrã. Uma verificação que não passa pelo caminho do
utilizador não diz nada sobre ele.

O arranque é verificado **numa área de dados temporária**, sempre. Criar a
conta de administrador na instalação real trancaria o utilizador fora do seu
próprio programa — passaria a existir uma conta, e o ecrã de primeira
utilização nunca mais apareceria.

Devolve código de saída diferente de zero se algo falhar, e nunca fica
pendurado: uma aplicação que não abre espera para sempre, por isso há um
limite de tempo que transforma o bloqueio numa falha comunicada. Funciona
também no executável empacotado:

```bash
dist\GerenciadorDeTarefas\GerenciadorDeTarefas.exe --autoteste --relatorio relatorio.txt
```

---

## 📊 Dashboard e análise

A aba **Dashboard** mostra, para o período escolhido (7, 30, 90 ou 365 dias):

- **Criadas** e **Concluídas** no período, com a variação face ao período
  anterior;
- **Pendentes**, **Atrasadas** e **taxa de conclusão** — estado atual;
- conclusões por dia, com média móvel e previsão a tracejado;
- distribuição entre concluídas, em dia e atrasadas;
- **análise em texto**: atrasos, produtividade, tendência, dias atípicos.

O dashboard atualiza-se sozinho quando uma tarefa muda — não é preciso
carregar em nada.

Duas regras que o produto respeita e que os testes garantem:

- **Só se compara o que é comparável.** "Criadas" e "concluídas" são fluxos e
  têm variação percentual; "pendentes" e "atrasadas" são fotografias do
  presente e não a têm, porque o histórico de estado não é guardado.
- **Sem dados suficientes, não há conclusão.** Menos de 4 pontos não geram
  tendência nem previsão, menos de 7 não geram deteção de anomalias, e uma
  variação abaixo de 10% não vira notícia. Cada frase mostra o número em que
  se baseia.

Os cálculos vivem em `src/analytics/` e não dependem da interface: a mesma
métrica serve dashboard, alertas e (no futuro) relatórios.

---

## 📄 Relatórios

No Dashboard, **Exportar** gera um relatório do período escolhido em **PDF**,
**Excel (XLSX)** ou **CSV**, com os indicadores, a análise e a lista de
tarefas — os mesmos números que estão no ecrã, porque a construção lê a
análise em vez de recalcular.

O XLSX e o PDF são escritos à mão, sem openpyxl nem reportlab: o executável
continua sem dependências (ver ADR-0002). Para isso não ficar pela fé, os
testes **leem de volta** o que foi gerado, com openpyxl e pypdf — bibliotecas
de teste que não entram no executável.

## 🔍 Auditoria

`Configurações → Auditoria` mostra o que aconteceu: tarefas criadas,
concluídas, reabertas e removidas, plugins instalados, ativados, atualizados
e removidos, e o arranque e o encerramento da aplicação.

- Só regista o que é **auditável** — uma lista explícita, não tudo o que passa.
- **Não guarda o conteúdo das tarefas**: interessa que a tarefa 12 foi
  removida e quando, não o que dizia.
- A tela é **só de leitura**. A trilha só é reduzida por retenção explícita
  (`core.auditoria.aplicar_retencao(dias)`), que diz sempre quantos registos
  removeu.
- Falhar a registar **nunca** interrompe quem está a trabalhar.

Visível apenas para quem tem a permissão `sistema.admin`.

---

## 👤 Contas e início de sessão

Na **primeira utilização** o programa pede que crie a conta de administrador.
**Não existe palavra-passe pré-definida** — palavras-passe de fábrica são das
formas mais fiáveis de deixar um sistema aberto.

Depois disso, a aplicação pede credenciais ao abrir.

| Papel | Tarefas | Análise e relatórios | Gestão |
|---|---|---|---|
| Administrador | vê e edita todas | tudo, incluindo exportar | contas, plugins, auditoria |
| Gestor | vê e edita todas | tudo, incluindo exportar | plugins |
| Supervisor | vê e edita todas | ver | — |
| Colaborador | **só as suas** | ver (as suas) | — |
| Visualizador | vê todas, não edita | ver | — |

As tarefas passam a ter dono: quem as cria. Um Colaborador vê e edita as suas;
os outros papéis veem as de toda a gente, com o nome de quem criou cada uma e
um filtro **Só as minhas**.

As tarefas criadas **antes** de existirem contas ficam sem dono e continuam
visíveis para todos — não se inventa um dono que nunca existiu.

A regra vive num sítio só (`src/tarefas_servico.py`) e vale para tudo: a
janela, o dashboard, os relatórios e os **plugins** — um plugin não consegue
ver o que a sua sessão não pode ver.

`Configurações → Utilizadores` (para quem tem `utilizadores.gerir`) permite
criar contas, mudar papéis, ativar/desativar, redefinir palavras-passe e
remover.

Como as palavras-passe são guardadas: derivadas com **PBKDF2-HMAC-SHA256**,
320 000 iterações e sal próprio por conta. O que fica no banco não permite
voltar atrás, e o formato guarda o custo usado — quando o custo subir, quem
entrar é regravado com o novo, sem perder a conta.

Outras salvaguardas:

- 5 tentativas falhadas bloqueiam a conta durante 5 minutos;
- a mensagem de erro **nunca** diz se o que falhou foi o nome ou a
  palavra-passe;
- nunca é possível ficar sem administrador ativo: remover, desativar ou
  despromover o último é recusado com explicação;
- entradas, saídas e tentativas falhadas ficam na auditoria.

> **Limite declarado:** o banco de dados **não é cifrado**. A autenticação
> protege o uso da aplicação, não o ficheiro em `%APPDATA%`. Quem tiver acesso
> à conta Windows tem acesso aos dados.

---

## 🧩 Plugins

### Usar

`Configurações → Plugins` mostra os plugins instalados, com estado e ações:

```
PLUGINS                                   [+ Instalar Plugin]
┌──────────────────────────────────────────────────────────┐
│ Calendar Integration  v1.0.0                             │
│ Mostra as tarefas num calendário mensal.                 │
│ Status: Ativo                                            │
│ [Desativar] [Atualizar] [Remover]                        │
└──────────────────────────────────────────────────────────┘
```

- **Instalar**: `+ Instalar Plugin` → escolher um `.zip` → validação →
  instalação → oferta de ativação.
- **Atualizar**: escolher um `.zip` com versão mais recente. A versão anterior
  é guardada e reposta automaticamente se a atualização falhar.
- **Remover**: pede confirmação e pergunta à parte se também quer apagar a
  configuração e os dados desse plugin.

Desativar **não** desinstala, e o estado sobrevive ao reinício.


### Pesquisa global (Ctrl+F)

Uma caixa que procura em tudo o que existir. **Cada parte da aplicação regista
o que sabe procurar**; a pesquisa junta as respostas e agrupa-as por origem —
sem o agrupamento, "Engenharia" três vezes não diz se são três unidades ou uma
unidade, uma tarefa e uma regra.

O módulo de pesquisa não sabe o que é uma tarefa. É o mesmo padrão do catálogo
de ações do motor de regras, e permite a um módulo novo aparecer aqui sem
tocar numa linha dele.

**Uma pesquisa é a porta lateral mais fácil de abrir sem querer.** Junta tudo
o que existe numa lista, e se uma fonte não aplicar as permissões de onde os
dados vêm, um colaborador que procure "orçamento" vê a tarefa do colega — e a
aplicação passa a contradizer-se a si própria. Por isso cada fonte passa pela
camada que aplica as permissões, nunca pelo banco, e há um teste que verifica
que é assim que continua a ser.

Na prática, com o mesmo termo:

| Quem procura | O que encontra |
|---|---|
| Administrador | tarefas, contas, automações |
| Gestor | tarefas (todas) |
| Colaborador | só as suas tarefas |

Encontra sem acentos e sem maiúsculas — obrigar a escrever "orçamento" com
cedilha para encontrar o que já se sabe que existe é hostil. Um termo com
menos de duas letras não devolve nada: "tudo" não é um resultado de pesquisa,
é a base de dados no ecrã. E procura **quando a escrita pára**, não a cada
tecla.

## Auditoria: de quê para quê

A trilha dizia que alguém mudou o papel de uma conta. Não dizia **de que papel
para que papel** — e numa auditoria a sério é essa a pergunta.

Os eventos passam a levar `antes` e `depois`, e a trilha mostra a mudança:

```
utilizador.alterado   bruno    papel: colaborador -> gestor
unidade.alterada      2        nome: Engenharia -> Engenharia e Produto
funcionalidade.alterada painel ligada: sim -> não
```

**Não basta quem publica mandar.** Cada evento declara que campos podem ter o
valor guardado, e o resto é descartado — a mesma lista de permissões que já
protegia o detalhe. Sem ela, um publicador distraído punha uma senha ou o
conteúdo de uma tarefa na trilha, e a auditoria passava a ser a maior fuga de
dados da aplicação. Verificado: um evento com `senha_hash` e notas privadas
sai da trilha apenas com `papel: gestor -> administrador`.

O que **não** está na lista é deliberado: nada de tarefas. Que a tarefa 12 foi
concluída é um facto auditável; o que ela dizia não é assunto da trilha.

## Da análise ao alerta

A análise sabia dizer que há tarefas atrasadas, que o ritmo caiu ou que um dia
foge ao padrão — mas só o dizia a quem abrisse o painel. A vigilância
(`src/alertas.py`) fecha o último elo:

```
tarefa -> evento -> métrica -> painel -> modelo -> previsão -> alerta -> regra -> ação
```

Publica `analise.alerta` e `analise.resolvido`. A partir daí uma regra pode
agir, sem que a análise saiba que a automação existe.

**O problema difícil aqui não é detetar: é não repetir.** "Há 15 tarefas
atrasadas" continua verdade amanhã. Se cada avaliação anunciasse, uma regra
ligada a ela criava a mesma tarefa todos os dias — e um alerta que se repete é
um alerta que se deixa de ler. Por isso a vigilância lembra-se do que já disse:

| Situação | O que acontece |
|---|---|
| Conclusão nova | É anunciada |
| A mesma, na mesma gravidade | Silêncio — mesmo que os números mudem |
| A gravidade **agrava** | Anunciada outra vez: atenção → crítico é notícia |
| Melhora sem resolver | Silêncio |
| Deixa de se aplicar | Anuncia-se que passou, e esquece |

O estado é guardado no banco, não em memória: senão cada arranque anunciava
tudo outra vez. Boas notícias não disparam automações — ficam no painel, que é
onde se vai vê-las.

Reavalia quando uma tarefa é criada, concluída, reaberta ou removida. É uma
análise completa de cada vez: para o volume de uma aplicação de secretária
chega bem, e se um dia não chegar, o sítio para tratar disso é aqui e só aqui.

## Automação por regras

**Quando** acontece X, **se** Y, **então** faz Z. É um Service: atravessa os
módulos, não tem domínio próprio e não é um Agent — executa regras que uma
pessoa escreveu, não decide nada.

O motor **não conhece tarefas nem inventário**. Quem tem uma ação para
oferecer regista-a; o motor liga o que aconteceu ao que fazer. É isso que
permite a um módulo novo participar sem tocar no motor, e que impede o motor
de se tornar o sítio onde todos os domínios se encontram.

Exemplo real, com dois módulos que não se conhecem:

> Quando `estoque.em_falta` **e** `saldo < 5` → criar a tarefa
> `"Encomendar item {id} (restam {saldo})"`

### O que impede uma regra de se comer a si própria

"Quando uma tarefa é criada, cria uma tarefa" é fácil de escrever sem dar por
isso, e sem defesa bloqueia a aplicação no primeiro disparo com o banco a
encher. Três defesas, todas com teste:

| | |
|---|---|
| **Profundidade máxima** | Uma cadeia de regras diferentes pára ao 5.º nível |
| **Uma regra não se repete na mesma cadeia** | Apanha o ciclo A→B→A, que é o que passa despercebido |
| **Reagir a `*` é recusado** | Ao guardar a regra: reagir a tudo inclui reagir ao que a própria regra provoca |

Atingir um limite é dito em voz alta (evento e registo): parar em silêncio
seria pior do que o ciclo, porque as regras deixavam de correr sem ninguém
perceber porquê.

Uma ação que falha é registada e as restantes continuam — uma automação
partida não pode impedir alguém de criar uma tarefa. E a ação corre com as
permissões de quem provocou o evento: **uma regra não é a forma de fazer por
automação o que não se pode fazer à mão.**

As condições são declarativas (campo, operador, valor) e o texto das ações é
preenchido por substituição escrita à mão — não há `str.format`, que navegaria
dentro dos objetos, nem `eval`. Uma regra guardada no banco é texto que alguém
pode alterar, e texto alterável não deve virar código a correr.

## Funcionalidades da instalação

`Configurações → Funcionalidades` (administradores). Liga e desliga partes do
produto **nesta instalação**.

Não é o mesmo que permissões, e confundi-las é o erro que este módulo existe
para evitar:

| Pergunta | Quem responde |
|---|---|
| Esta **pessoa** pode fazer isto? | `core/permissoes.py` |
| Esta **instalação** tem isto, de todo? | `core/funcionalidades.py` |

As duas combinam-se: um administrador com todas as permissões do mundo não
exporta relatórios se a instalação não os tiver.

Tudo nasce ligado — atualizar não tira nada a ninguém. Desligar é deliberado,
exige `sistema.admin` e fica na trilha de auditoria, porque muda o que toda a
gente vê. O efeito é visível ao reabrir a aplicação: as abas e o menu são
construídos no arranque.

As funcionalidades são **declaradas**, não inventadas: perguntar por uma chave
que não está no catálogo levanta erro em vez de devolver `False`. Uma pergunta
com um erro de escrita a responder "está desligada" é a forma mais silenciosa
de desligar alguma coisa sem querer.

O que ficou de fora é tão deliberado quanto o que entrou: as tarefas, as
contas e os plugins são o produto; a cópia de segurança não se desliga (uma
opção que deixa ficar sem rede não é uma opção); e a trilha de auditoria tem
o seu próprio mecanismo — parar de registar é uma decisão de conformidade, não
uma preferência.

## Módulos e ferramentas incluídos

Todos entram como plugins, todos se desinstalam, e nenhum tem uma linha no
núcleo a saber que existe.

| | Categoria | O que faz | O que pede |
|---|---|---|---|
| **Calendar** | Plugin | Tarefas num calendário mensal | `tarefas.ler`, `tarefas.escrever` |
| **Atualizações** | Plugin | Avisa de versões novas, com consentimento | nada |
| **Estoque** | Module | Itens, entradas, saídas, aviso de mínimo | nada ao núcleo; traz `estoque.ler` e `estoque.escrever` |
| **Calculadora** | Plugin | Simples, científica, conversões, financeira | nada |

### Calculadora

Quatro modalidades numa aba: **simples** (com memória), **científica**
(expressões por extenso, graus/radianos, histórico), **conversões**
(comprimento, massa, área, volume, tempo, dados, velocidade, temperatura) e
**financeira** (prestação, tabela de amortização completa, juros compostos,
IVA, variação percentual).

Três decisões que explicam o resto:

**Sem `eval()`.** A forma rápida de avaliar `2+3*4` em Python é `eval`, e é a
errada: `eval` executa *código*, não aritmética. Numa aplicação com tarefas,
contas e inventário de uma empresa, uma caixa de texto ligada ao `eval` é um
buraco por onde entra tudo. Há um analisador escrito à mão que só conhece
números, operadores e uma lista fechada de funções — e um teste que falha se
algum dia aparecer um `eval` na pasta.

**Dinheiro em `Decimal`, nunca `float`.** `0.1 + 0.2` não dá `0.3` em binário,
e numa tabela a 360 meses esse erro acumula até as parcelas deixarem de somar
o empréstimo. A última parcela absorve os cêntimos do arredondamento, para o
saldo final ser **exatamente** zero.

**Sem moedas.** Converter euros em dólares exige taxas de hoje, e isso exige
rede, uma chave de API e um fornecedor — coisas que esta aplicação não tem, e
que fariam sair da máquina o que alguém está a calcular. Uma taxa gravada no
código seria pior: daria um número errado com ar de certo. As unidades que
estão aqui são definições exatas ou constantes físicas, e não mudam.

Também escolhe entre taxa mensal **nominal** (anual ÷ 12) e **equivalente**
(composta) — são números diferentes, e quem calcula é que decide, em vez de
descobrir mais tarde que o programa escolheu por si.

## Cópia de segurança

`Configurações → Cópia de segurança` (administradores). Guarda num ZIP as
tarefas, as contas, a estrutura da empresa, a trilha de auditoria, as
configurações e os dados dos plugins.

**Uma cópia leva dados, nunca código.** Os plugins instalados ficam de fora de
propósito: um ficheiro de cópia anda por e-mail e por pen, e se trouxesse
código, restaurar a cópia de alguém passava a executar o que essa pessoa lá
pusesse. Os ids e as versões ficam registados no manifesto, para se saber o
que reinstalar.

Ficam também de fora os registos (`logs/`) — são diagnóstico, não dados.

Restaurar:

1. valida o ficheiro inteiro antes de tocar em nada — caminhos com `..`,
   absolutos, ligações simbólicas e ficheiros fora dos sítios conhecidos são
   recusados, tal como nos pacotes de plugins;
2. recusa uma cópia feita por uma versão **mais recente** da aplicação: ler um
   esquema do futuro é ler colunas que não se conhecem. Uma cópia mais antiga
   é aceite e migrada;
3. confirma que o banco de dentro abre;
4. **só então** guarda o estado atual em `antes-do-restauro.zip` e substitui.

Se alguma coisa falhar antes do ponto 4, nada foi tocado. Depois de restaurar,
feche e reabra a aplicação: quem está a correr tem ligações ao banco anterior.

## Plugins incluídos

| Plugin | O que faz | Estado inicial |
|---|---|---|
| **Calendar Integration** | calendário mensal com as tarefas de cada dia | instalado, por ativar |
| **Verificação de Atualizações** | avisa quando há uma versão nova | instalado, **desativado** |

O plugin de atualizações segue três regras:

1. **Não contacta a internet sem autorização.** Na primeira vez pergunta, e
   diz que endereço vai consultar. A resposta fica guardada e muda-se na aba
   *Atualizações*.
2. **Não descarrega nem instala nada.** Se aceitar a atualização, abre a
   página oficial da versão no navegador — quem descarrega e instala é você, a
   partir da fonte original. Um programa que se atualiza sozinho em silêncio
   passa a executar o que lhe mandarem, se a fonte for comprometida.
3. **Nunca interrompe o trabalho.** A verificação corre em segundo plano e,
   se falhar, fica só no registo.

Por omissão consulta os *releases* do repositório do projeto, mas aceita
qualquer endereço HTTPS que devolva `{"versao": ..., "notas": ..., "url": ...}` —
uma empresa pode apontar para o seu próprio servidor, em
`%APPDATA%\GerenciadorDeTarefas\config\plugins\atualizacoes.json`.

### Criar um plugin

Estrutura mínima:

```
meu_plugin/
├── plugin.json
├── plugin.py
└── idiomas/          (opcional)
    ├── pt.json
    └── en.json
```

`plugin.json`:

```json
{
  "id": "meu_plugin",
  "name": "O Meu Plugin",
  "version": "1.0.0",
  "author": "Você",
  "description": "O que o plugin faz.",
  "min_app_version": "1.0.0",
  "entry_point": "plugin.py",
  "permissions": ["tarefas.ler"]
}
```

Regras do manifesto:

- `id`: 2 a 64 caracteres, minúsculas, dígitos, `_` ou `-`; tem de ser igual
  ao nome da pasta e único entre os plugins instalados;
- `version` e `min_app_version`: versão semântica (`1.2.3`);
- `max_app_version`: opcional, inclusivo;
- `entry_point`: arquivo `.py` dentro da pasta do plugin (sem `..`, sem
  caminho absoluto);
- `permissions`: opcional. O acesso de que o plugin precisa. Omitir é pedir
  nada, não é pedir tudo.

### Permissões declaradas

Um plugin instalado é código de outra pessoa a correr na máquina de quem lhe
confia os dados. O manifesto tem de declarar de que acesso precisa; o
utilizador vê essa lista no gestor de plugins e outra vez antes de o ativar.

O que o plugin recebe é a **interseção** de duas coisas, e ambas têm de deixar
passar:

| | |
|---|---|
| o que o plugin **declarou** | senão, `PermissaoNaoDeclaradaError` |
| o que a **sessão** pode fazer | senão, `PermissaoNegadaError` |

Declarar `tarefas.ver_todas` não faz um plugin ver tudo: faz com que possa ver
tudo *se* quem está a usar a aplicação também puder.

Um plugin pode pedir: `tarefas.ler`, `tarefas.escrever`, `tarefas.ver_todas`,
`analytics.ler`, `relatorios.ler`, `relatorios.exportar`.

Nenhum plugin pode pedir `plugins.gerir`, `utilizadores.gerir` ou
`sistema.admin` — um manifesto que as peça é recusado na instalação. Não são
capacidades de negócio: um plugin que instala plugins deixa de ter fronteira,
e um que cria contas concede-se a si próprio o que quiser.

### Módulos auxiliares do plugin

Um plugin pode trazer mais ficheiros ao lado do `plugin.py`. Importe-os com
**import relativo**:

```python
from . import modelo          # funciona em qualquer sítio, incluindo dentro
                              # de uma função
```

O ponto de entrada é carregado como pacote com raiz na pasta do plugin, por
isso `from .` resolve sempre e cada plugin fica com os **seus** ficheiros —
dois plugins podem ambos ter um `utils.py` sem se atrapalharem.

`import modelo` (sem o ponto) também funciona, mas só no topo do `plugin.py`.
Adiado para dentro de uma função, falha: o nome simples não fica reservado a
ninguém, de propósito. Se ficasse, o primeiro plugin a carregar decidia o
código que o segundo executa.

### Permissões do próprio módulo

Um módulo de negócio tem permissões que o núcleo não pode conhecer — não há
`estoque.ler` no `Permissao` da aplicação, nem devia haver. O manifesto
declara-as:

```json
"provides_permissions": {
  "estoque.ler":     ["administrador", "gestor", "colaborador", "visualizador"],
  "estoque.escrever": ["administrador", "gestor", "colaborador"]
}
```

Passam a existir **enquanto o módulo estiver carregado**, e saem com ele.

A regra de segurança é o espaço de nomes: um módulo só pode definir permissões
com o seu próprio id à frente. O pior que consegue conceder é acesso aos
**seus** dados — as tarefas, as contas e o sistema continuam a ser decisão de
quem administra, e um manifesto que tente `tarefas.ver_todas` é recusado na
instalação.

Uma permissão que ninguém registou é negada a toda a gente, **incluindo ao
administrador**: dizer que sim a um nome que não existe esconderia um erro de
escrita de quem administra e mostrá-lo-ia só a quem não administra.

```python
if self.contexto.pode("estoque.escrever"):   # esconder o botão
    ...
self.contexto.exigir("estoque.escrever")     # ou recusar no serviço
```

### Dados próprios

Um módulo de negócio precisa de tabelas. Não as cria no banco da aplicação:
cada plugin tem o **seu** ficheiro SQLite, na sua área de dados.

```python
class Estoque(Plugin):
    def inicializar(self):
        self.contexto.dados.migrar(
            1, "CREATE TABLE itens (id INTEGER PRIMARY KEY, nome TEXT)"
        )
        self.contexto.dados.migrar(
            2, "ALTER TABLE itens ADD COLUMN quantidade INTEGER DEFAULT 0"
        )

    def registar(self, nome, quantidade):
        self.contexto.dados.executar(
            "INSERT INTO itens (nome, quantidade) VALUES (?, ?)", (nome, quantidade)
        )
```

- `migrar(versao, *sql)` aplica um passo **uma só vez**, por ordem crescente;
  pode ficar no código para sempre. Um passo corre inteiro ou não corre —
  incluindo `CREATE`/`ALTER`, para uma migração falhada a meio não deixar o
  esquema num estado de que nunca mais sai;
- `executar`, `executar_muitos`, `consultar`, `consultar_um` para o dia a dia,
  e `conectar()` quando várias escritas têm de acontecer juntas ou nenhuma;
- o ficheiro só nasce na primeira escrita: um plugin que nada guarda não
  deixa nada atrás de si;
- o caminho vem do id do plugin — o plugin não escolhe onde grava, e não
  alcança os dados da aplicação nem os de outro plugin;
- remover o plugin **com os dados** leva este ficheiro; removê-lo sem os dados
  preserva-o para uma reinstalação.

Guardar dados próprios não exige permissão: são os dados do próprio plugin.

Para esconder um botão em vez de o deixar falhar:

```python
if self.contexto.pode(Permissao.TAREFAS_ESCREVER):
    ...
```

`plugin.py`:

```python
from core.plugin_api import Plugin


class MeuPlugin(Plugin):
    def inicializar(self):
        """Chamado uma vez, ao carregar."""

    def ativar(self):
        """Passa a funcionar: regista abas, liga eventos."""
        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba"),   # segue o idioma
            self._construir,
        )

    def _construir(self, pai):
        from tkinter import ttk
        return ttk.Label(pai, text=self.contexto.traduzir("ola"))

    def desativar(self):
        """Para de funcionar; as abas são removidas pela aplicação."""

    def finalizar(self):
        """Liberta recursos antes de o módulo ser descartado."""
```

Se o módulo definir mais do que uma subclasse de `Plugin`, indique qual usar
com `PLUGIN_CLASS = MeuPlugin`.

#### O que o plugin pode usar

Tudo chega pelo `self.contexto` — um plugin **não** importa `database` nem
`gui`:

| Atributo | Para quê |
|---|---|
| `contexto.tarefas` | `listar()`, `listar_por_data(data)`, `adicionar(descrição, data)` |
| `contexto.ui` | `registrar_aba(id, título, construtor)`, `notificar(mensagem)` |
| `contexto.traduzir(chave, padrão, **fmt)` | textos do plugin e da aplicação |
| `contexto.config()` / `guardar_config(dados)` | configuração privada do plugin |
| `contexto.diretorio_dados` | pasta gravável só deste plugin |
| `contexto.diretorio_plugin` | pasta onde o plugin está instalado |
| `contexto.subscrever(padrão, ouvinte)` | reagir a eventos (`"tarefa.*"`, `"plugin.ativado"`…) |
| `contexto.publicar(nome, **dados)` | emitir eventos próprios (use um prefixo seu) |
| `contexto.logger` | log já nomeado com o id do plugin |
| `contexto.app_version` | versão da aplicação a correr |

`contexto.ui` é `None` quando não há interface (por exemplo, em testes): teste
antes de usar.

Ciclo de vida:

```
DISCOVER → VALIDATE → INSTALL → REGISTER → LOAD → ACTIVATE
        → RUN → DEACTIVATE → UNLOAD
```

Uma exceção em qualquer destes passos é registada no log, marca o plugin como
"com erro" e **não afeta a aplicação nem os outros plugins** — o mesmo vale
para um ouvinte de eventos que rebente: quem publicou não fica a saber e os
outros ouvintes continuam. As subscrições de um plugin são canceladas quando
ele é desativado.

#### Empacotar e instalar

```bash
python tools/empacotar_plugin.py plugins/available/calendar
# -> dist/plugins/calendar-1.0.0.zip
```

Depois, na aplicação: `Configurações → Plugins → + Instalar Plugin`.

O `.zip` é tratado como conteúdo não confiável: caminhos com `..`, caminhos
absolutos, ligações simbólicas, pacotes sem manifesto ou demasiado grandes são
recusados, e **nada é executado a partir do `.zip`** — a extração vai para uma
área temporária, é revalidada e só depois promovida a plugin instalado.

O plugin `plugins/available/calendar` serve de exemplo completo.

---

## 🏗️ Arquitetura

```
                    APLICAÇÃO
                        │
             ┌──────────┴──────────┐
             │                     │
           CORE              PLUGIN MANAGER
             │                     │
      ┌──────┼──────┐       ┌──────┼──────┐
      │      │      │       │      │      │
   Tarefas  BD   Idiomas  Instalar Ativar Atualizar
```

```
gerenciador_de_tarefas/
├── src/
│   ├── main.py                 # entrada; --version, --autoteste
│   ├── gui.py                  # janela principal (abas + menu)
│   ├── plugin_ui.py            # tela de plugins e pontos de extensão da GUI
│   ├── database.py             # SQLite com migrações versionadas
│   ├── language_manager.py     # idiomas da aplicação e dos plugins
│   ├── calendar_widget.py      # calendário reutilizável
│   ├── dashboard_ui.py         # aba Dashboard
│   ├── tarefas_servico.py      # quem vê e edita que tarefas
│   ├── utils.py
│   ├── auditoria_ui.py         # tela de auditoria
│   ├── login_ui.py             # início de sessão e primeiro administrador
│   ├── utilizadores_ui.py      # gestão de contas
│   ├── textos.py               # apresentação partilhada dos insights
│   ├── analytics/              # métricas, séries, insights (sem interface)
│   ├── reporting/              # relatórios e exportação (PDF/XLSX/CSV)
│   ├── widgets/                # gráficos desenhados em Canvas
│   └── core/
│       ├── version.py          # nome e versão (fonte única)
│       ├── eventos.py          # barramento de eventos
│       ├── permissoes.py       # papéis e permissões (RBAC)
│       ├── auditoria.py        # trilha do que aconteceu
│       ├── seguranca.py        # derivação de palavras-passe
│       ├── utilizadores.py     # contas e autenticação
│       ├── paths.py            # recursos vs. dados do utilizador vs. temporários
│       ├── config.py           # configuração da app e por plugin
│       ├── log.py
│       ├── plugin_api.py       # manifesto, contexto e classe base Plugin
│       ├── plugin_manager.py   # ciclo de vida dos plugins
│       ├── plugin_package.py   # validação e extração segura de .zip
│       ├── plugin_registry.py  # estado dos plugins no banco
│       └── plugin_sources.py   # fontes: zips locais, embutidos, loja (futura)
├── plugins/available/          # plugins que acompanham a aplicação
│   ├── calendar/
│   └── atualizacoes/
├── assets/idiomas/             # pt.json, en.json, es.json
├── assets/icon.ico
├── installer/setup.iss         # instalador Inno Setup
├── tools/                      # build, instalador, empacotar plugin, ícone
├── docs/architecture/          # visão, ADRs e roadmap
├── tests/                      # 545 testes
├── docs/AUDIT.md               # auditoria do estado inicial do projeto
└── GerenciadorDeTarefas.spec   # receita do PyInstaller
```

Princípios:

- **O núcleo não conhece plugins concretos.** O `PluginManager` conhece a
  infraestrutura; a lógica de cada plugin é só dele.
- **A versão vive num sítio só** (`core/version.py`) e é lida pela aplicação,
  pelo PyInstaller e pelo Inno Setup.
- **Dados do utilizador nunca em `Program Files`.**
- **Erro de plugin nunca derruba a aplicação.**
- **Os módulos empresariais entram como plugins**, não como código do núcleo
  (ver `docs/architecture/ADR-0001-nucleo-fino.md`).

Os plugins podem, no futuro, vir de uma loja online: `core/plugin_sources.py`
já separa "de onde vem o pacote" de "como é validado e instalado", com
`FonteZipsLocais`, `FontePastasLocais` e o esqueleto `FonteRemota`.

---

## 🔨 Gerar o executável

```bash
pip install -r requirements-dev.txt
python tools/build.py
```

Produz `dist/GerenciadorDeTarefas/GerenciadorDeTarefas.exe` (~27 MiB) e **só
dá o build por concluído depois de executar o `.exe`** com `--version` e
`--autoteste`.

Opções: `--limpar` (apaga `build/` e `dist/` antes), `--sem-teste`.

> Um plugin carregado em tempo de execução pode importar módulos que o
> PyInstaller não vê. Os módulos disponíveis aos plugins estão declarados em
> `hiddenimports`, em `GerenciadorDeTarefas.spec`.

## 📦 Gerar o instalador

Requer [Inno Setup 6.3+](https://jrsoftware.org/isdl.php).

```bash
python tools/build.py
python tools/build_installer.py
# -> installer/Output/GerenciadorDeTarefas-Setup.exe
```

Se o `ISCC.exe` estiver noutro local, aponte a variável de ambiente `ISCC`
para ele. `python tools/build_installer.py --verificar` confirma se o
compilador foi encontrado.

### Instalação e desinstalação automatizadas

```bat
GerenciadorDeTarefas-Setup.exe /VERYSILENT /NORESTART /CURRENTUSER /DIR="C:\GDT"
"C:\GDT\unins000.exe" /VERYSILENT                     :: mantém os seus dados
"C:\GDT\unins000.exe" /VERYSILENT /REMOVEDATA=yes     :: apaga também os dados
```

Uma desinstalação silenciosa **nunca** apaga dados sem `/REMOVEDATA=yes`.

## ✅ Testar o instalador

```bash
python tools/testar_instalador.py
```

Instala em silêncio, confirma atalhos e desinstalador, cria dados, instala
uma versão mais recente por cima, verifica que tarefas e plugins
sobreviveram, desinstala (dados preservados) e, por fim, desinstala com
`/REMOVEDATA=yes` (dados removidos). Aborta se já existir
`%APPDATA%\GerenciadorDeTarefas`, para não mexer nos seus dados.

## 🔁 Testar uma atualização sem instalador

```bash
python tools/testar_atualizacao.py
```

Constrói a versão atual, "instala" numa pasta temporária, cria tarefas, liga
um plugin, constrói uma versão mais recente, substitui os arquivos da
aplicação e confirma que tarefas, configurações e plugins sobreviveram.

---

## 🩺 Problemas comuns

| Sintoma | O que fazer |
|---|---|
| "Plugin inválido" ao instalar | O `.zip` tem de conter `plugin.json` na raiz ou numa única pasta de topo, e o `id` tem de ser igual ao nome dessa pasta. |
| "Este plugin exige uma versão diferente" | O `min_app_version` do plugin é superior à versão instalada; atualize a aplicação. |
| "Este plugin já está instalado" | Só se instala por cima com uma versão **mais recente**; para reinstalar a mesma, remova primeiro. |
| Um plugin não arranca | A aplicação avisa e continua. O motivo está em `%APPDATA%\GerenciadorDeTarefas\logs\app.log`. |
| Plugin funciona em desenvolvimento mas não no `.exe` | Falta um módulo em `hiddenimports` no `.spec`. |
| Quero começar do zero | Feche a aplicação e apague `%APPDATA%\GerenciadorDeTarefas` (perde tarefas e plugins). |
| `Inno Setup 6 não encontrado` | Instale o Inno Setup ou defina a variável `ISCC`. |

---

## 🤝 Contribuições

Veja o guia de contribuições em `CONTRIBUTING.md` (disponível em inglês).

## 📝 Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).

## 🙋‍♂️ Autor

Desenvolvido por **Rodrigo Costa**
📧 rodrigocosta8638@gmail.com
🌍 [GitHub/Raoc1987](https://github.com/Raoc1987)
