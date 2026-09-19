# Changelog

Todas as mudanças importantes deste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e
o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

Primeiro passo da evolução para plataforma modular de gestão. O gestor de
tarefas continua a ser o núcleo; os módulos empresariais entrarão como
plugins (ver `docs/architecture/`).

### Adicionado

- **Framework de manutenção** (`docs/MANUTENCAO.md`): o que se antecipa
  (preditiva), o que se faz por rotina (preventiva) e como se responde a uma
  falha já ocorrida (corretiva), cada item com sinal, ferramenta, cadência e
  responsável. Nenhum item corretivo assume a causa: começa sempre por
  investigar.
- **`--verificar-banco`**: mostra a versão do schema e o `PRAGMA
  integrity_check`, abrindo o banco **só de leitura**. Um diagnóstico que
  aplicasse migrações deixaria de ser um diagnóstico — e era a única forma de
  ver o estado do banco de alguém sem abrir a aplicação, que é justamente o
  que pode não estar a funcionar.
- **As exceções deixaram de se perder** (`core/log.py`, `main.py`): as do
  interpretador, as das *threads* e as dos *callbacks* do Tk vão todas para o
  `app.log`. O Tk imprimia-as no `stderr`, que numa aplicação empacotada em
  modo gráfico não existe: o botão não fazia nada e não ficava registo de
  porquê.
- **Retenção da auditoria aplicável**: a chave `auditoria_retencao_dias` em
  `app_config.json` é aplicada no arranque. Sem chave definida não se apaga
  nada — o padrão de uma trilha tem de ser guardar.
- **CI**: a suíte passa a correr também por agendamento semanal; os ensaios do
  instalador e da atualização passam a correr no CI (semanalmente e a pedido)
  em vez de dependerem de alguém se lembrar; cobertura medida em cada
  execução; Actions fixadas por SHA e sem permissões de escrita; Dependabot a
  propor as atualizações das ferramentas e das Actions.
- **Testes de arquitetura**: a regra "só biblioteca padrão" (ADR-0002) passa a
  falhar um teste em vez de depender da revisão, e os manifestos dos plugins
  embutidos passam a ser verificados contra a versão atual da aplicação.
- **Dono das tarefas** (`tarefas_servico.py`, migração v6): quem cria uma
  tarefa passa a ser o seu dono. Um Colaborador vê e edita as suas; Gestor,
  Supervisor e Visualizador veem as de todos, com o nome de quem criou e um
  filtro "Só as minhas". As tarefas anteriores às contas ficam sem dono e
  continuam de todos. A regra vale para a janela, o dashboard, os relatórios
  e os plugins.
- **Contas de utilizador e início de sessão** (`core/seguranca.py`,
  `core/utilizadores.py`): palavras-passe derivadas com PBKDF2-HMAC-SHA256 e
  sal próprio, bloqueio após tentativas falhadas, e a garantia de nunca ficar
  sem administrador ativo. No primeiro arranque cria-se a conta de
  administração — não há palavra-passe pré-definida.
- **Gestão de contas** em `Configurações → Utilizadores`.
- **Plugin de verificação de atualizações**: avisa quando há versão nova,
  pergunta antes de contactar a internet e nunca descarrega nem instala — abre
  a página oficial e a decisão é do utilizador.
- Migração de banco v5: tabela `utilizadores`.
- **Relatórios** (`reporting/`) em PDF, XLSX e CSV, com indicadores, análise e
  lista de tarefas, exportáveis a partir do Dashboard. O XLSX e o PDF são
  escritos à mão, sem dependências no executável; os testes leem-nos de volta
  com openpyxl e pypdf para confirmar que são ficheiros válidos.
- **Auditoria persistida** (`core/auditoria.py` e `Configurações →
  Auditoria`): consome o barramento e grava quem fez o quê e quando, sem
  guardar o conteúdo das tarefas. Só de leitura na interface; retenção
  explícita é a única forma de remover registos.
- Migração de banco v4: tabela `auditoria` com índices.
- `textos.py`: tradução partilhada dos insights, para a mesma conclusão não
  ser escrita de duas maneiras no ecrã e no relatório.

### Alterado

- **"Ver todas" passa a querer dizer "as tarefas da minha empresa"**
  (ADR-0011). Antes, quem tinha `tarefas.ver_todas` via as tarefas de **todas
  as empresas** da instalação. Com uma empresa isso era a mesma coisa; com
  duas, era uma fuga entre clientes.
- Nada muda para quem tem **uma empresa só**, **nenhuma estrutura**, ou **não
  está na estrutura**: o isolamento começa a valer no dia em que a segunda
  empresa é criada. As tarefas anteriores à estrutura continuam visíveis para
  toda a gente — não pertencem a empresa nenhuma, e escondê-las faria
  desaparecer o histórico do ecrã.
- A contagem por pessoa passou a respeitar o âmbito: somava as tarefas das
  outras empresas.

### Adicionado

- **Um plugin passa a poder substituir uma tabela**
  (`dados.migrar(..., reconstroi_tabelas=True)`). Não era possível: o SQLite
  não sabe tirar uma restrição, e apagar uma tabela que tem filhos falha com
  as chaves estrangeiras ligadas — sendo que `PRAGMA foreign_keys = OFF` é
  **ignorado em silêncio dentro de uma transação**, que é onde uma migração
  corre. Na prática, um módulo com uma chave estrangeira nunca podia mudar a
  tabela pai. O modo novo faz o procedimento recomendado pelo SQLite e
  **verifica** com `PRAGMA foreign_key_check` antes de gravar: se ficou uma
  referência pendurada, desfaz tudo e a versão do esquema não avança.

### Adicionado

- **Motor do painel** (`src/painel/`, ADR-0010): o painel desenha o que estiver
  **registado**, em vez de uma lista fixa escrita à mão. Um módulo passa a
  poder pôr um **gráfico** no painel principal
  (`contexto.registar_widget_de_painel`), e não só um número.
- A grelha **reparte-se com a largura**: quatro colunas num ecrã largo, duas
  num portátil a 1366×768, uma numa janela estreita.
- Os dados vão ao widget, e não o contrário: o contexto leva o período e o
  panorama já calculado, para dois cartões não darem números diferentes da
  mesma coisa. É também a forma dos filtros globais.
- Um widget sem permissão **não é construído**; um widget que rebente não
  apaga os outros.

### Adicionado

- **Concha de navegação** (`src/navegacao/`, ADR-0009): barra lateral com
  grupos em vez de uma fila de abas, barra de topo com o nome da secção, e
  **paleta de comandos** em `Ctrl+K`. A concha implementa a interface do
  `ttk.Notebook` de propósito — **nenhum plugin instalado precisa de mudar
  uma linha** para passar a aparecer na barra lateral.
- Uma secção declara-se (`navegacao.registar`) com o grupo, a ordem, a
  permissão e a funcionalidade de que depende, em vez de ser acrescentada à
  mão à janela principal. É o mesmo padrão dos indicadores e da pesquisa.
- A barra lateral recolhe para ícones; o conteúdo é uma pilha, por isso mudar
  de secção e voltar não perde o que estava escolhido.
- `docs/PLATAFORMA.md`: auditoria do plano de evolução contra o que existe,
  com o que está **implementado**, **em parte**, **não implementado** e **não
  validado**.

### Adicionado

- **Aparência** (`src/aparencia/`, ADR-0008): cores, espaços e tipos de letra
  num sítio só, aplicados ao ttk uma vez no arranque. O programa deixa de usar
  o tema de origem do sistema — relevo nenhum, uma escala de espaçamento, e
  uma cor de ênfase usada pouco. **Modo escuro**, escolhido em
  `Configurações` e guardado entre arranques.
- Cada par de cores que aparece no ecrã é **medido** contra os limiares da
  WCAG 2.1, nos dois modos, por `tests/test_aparencia.py`. Foi a medição que
  encontrou o que já lá estava: o cinzento do texto secundário dava 3,67 de
  contraste sobre branco, abaixo do mínimo de 4,5.
- Dois testes de arquitetura impedem a decadência: nenhum ecrã escreve uma cor
  em hexadecimal nem escolhe a sua própria família de letra.
- Um plugin acompanha o tema sem fazer nada (as classes de estilo são
  globais); para desenhar num `Canvas`, o contexto dá `cor()`, `fonte()` e
  `espaco()`.

### Adicionado

- **Políticas por atributo** (`core/permissoes.py`, ADR-0007): o papel responde
  a "podes concluir tarefas?"; uma política responde a "podes concluir
  **esta**?". Uma política recebe o par `(ação, objeto)` e **só pode recusar**
  — nunca concede, corre depois do papel e, se rebentar, recusa. É o que torna
  seguro um plugin registar uma: no pior caso tranca alguém de fora do seu
  próprio módulo, e isso vê-se; se pudesse conceder, o pior caso era abrir uma
  porta em silêncio.
- **Segregação de funções** (funcionalidade, **nasce desligada**): com ela
  ligada, quem cria uma tarefa não a dá por concluída — nem quem administra,
  porque um controlo que o dono da instalação contorna não é um controlo.
  Reabrir continua a ser possível, e as tarefas anteriores às contas não são
  abrangidas. Ligue-a só onde exista outra pessoa para fechar o trabalho.
- Uma tentativa recusada por uma política publica `politica.recusou` e fica na
  trilha de auditoria. É o que separa um controlo de um obstáculo: um
  obstáculo impede e cala-se. Perguntar (`pode`) não conta como tentativa —
  senão a trilha enchia-se do que a interface pergunta para desenhar botões.
- Um plugin pode registar políticas sobre os seus objetos
  (`contexto.registar_politica`), no seu espaço de nomes, e elas saem quando
  ele é descarregado.

### Alterado

- **Nomes de topo em português** (ADR-0005): `database.py` → `banco_de_dados.py`,
  `analytics/` → `analitica/`, `reporting/` → `relatorios/`, `widgets/` →
  `componentes/`. `src/` está no `sys.path`, por isso cada nome ali é um nome
  no espaço global de módulos — foi assim que `src/workflow/` bateu com o hook
  do pacote `workflow` do PyPI e o build parou, com os testes todos verdes.
  Nada muda para quem usa o programa: a permissão continua a chamar-se
  `analytics.ler` e os eventos do banco continuam a assinar `origem="database"`,
  porque uma trilha de auditoria não se reescreve.
- `docs/architecture/nomes-de-topo.json` declara todos os nomes de topo, e um
  teste falha perante um nome não declarado — a decisão passa a ser tomada no
  dia em que o módulo é criado. Os nomes que os plugins importam
  (`utils`, `calendar_widget`, `language_manager`, `core`) ficam congelados,
  com a razão escrita, e um teste verifica que coincidem com o que o
  executável leva lá dentro.

### Corrigido

- **Um plugin que acompanha o aplicativo era instalado uma vez e nunca mais
  atualizado** (`core/plugin_manager.py`, migração v12, ADR-0006). A semeadura
  saltava qualquer plugin que já estivesse em disco, sem sequer olhar para a
  versão: nenhuma correção de segurança, permissão nova ou tradução nova
  chegava a quem já tinha o aplicativo instalado. Cada plugin instalado passa
  a ter dono — do aplicativo ou do utilizador — e a impressão digital do que
  foi instalado. Um plugin do aplicativo, intacto e desatualizado, é
  atualizado no arranque; um que o utilizador instalou ou modificou fica como
  está, e só a ação **Repor originais**, na tela de plugins, lhe toca. Se uma
  alteração escapar sem subir a versão, a mesma versão com um manifesto
  diferente também é refrescada — comparando manifestos interpretados, não
  bytes, para que fins de linha não provoquem reinstalações.
- **O plugin Calendar não ativava numa instalação existente**: o manifesto em
  disco não declarava as permissões `tarefas.ler` e `tarefas.escrever`, que a
  versão do repositório já declarava desde que o SDK passou a exigi-las. Fica
  corrigido pela atualização automática acima (Calendar v1.0.1). O plugin de
  atualizações passa a declarar `"permissions": []` — não acede a dados de
  ninguém, e agora di-lo (v1.0.1).
- O relatório mostrava o estado de uma tarefa no plural ("Atrasadas"), usava
  o cabeçalho do formulário como cabeçalho de coluna e truncava datas por
  repartir a largura por número de caracteres em vez de largura real.
- `auditoria.ativar()` podia reportar-se ativa depois de o barramento ter
  sido reposto, ficando calada sem ninguém dar por isso.

### Adicionado (fundação, anterior)

- **Barramento de eventos** (`core/eventos.py`): os módulos passam a
  comunicar sem se conhecerem. Um ouvinte com defeito não afeta os outros nem
  quem publicou. Plugins podem subscrever e publicar eventos, e as suas
  subscrições morrem com eles.
- **Permissões (RBAC)** (`core/permissoes.py`): permissões nomeadas, cinco
  papéis e um ponto único de verificação. **Sem autenticação** — a estrutura
  existe, o ecrã de início de sessão não.
- **Camada de análise** (`analytics/`): KPIs, séries temporais, média móvel,
  tendência, previsão, deteção de anomalias e insights em texto. Funções
  puras, independentes da interface e da persistência.
- **Dashboard** com indicadores, gráficos e análise, que se atualiza sozinho
  quando as tarefas mudam.
- **Gráficos desenhados em Canvas** (`widgets/graficos.py`), sem matplotlib:
  o executável cresceu 0,1 MiB em vez de ~170 MiB.
- `docs/architecture/` com a visão, o roadmap e três ADRs.
- Migração de banco v3: `concluida_em`, sem a qual "concluídas por dia" não
  existia.

### Corrigido

- A previsão era desenhada sobre o início da série em vez de a prolongar.
- Os cartões comparavam o total de sempre com uma janela de 30 dias.
- Eixos com escalas ilegíveis (30.2, 60.4, 90.6).
- Um gráfico sem dados desenhava uma linha achatada no zero, que parece uma
  medição.

## [1.0.0] - 2026-09-11

Primeira versão funcional e distribuível.

### Adicionado

**Aplicação**
- Implementação dos módulos que estavam vazios desde o commit inicial
  (`main.py`, `database.py`, `language_manager.py`, `calendar_widget.py` e os
  arquivos de idioma), respeitando o contrato já definido por `gui.py`.
- Tarefas com descrição, data de vencimento e estado; criar, concluir,
  reabrir e remover pela interface.
- Banco SQLite com migrações versionadas (`PRAGMA user_version`), guardado em
  `%APPDATA%\GerenciadorDeTarefas` — nunca em `Program Files`.
- Idiomas português, inglês e espanhol, com a escolha persistida.
- Logging rotativo em arquivo e configuração da aplicação separada da dos
  plugins.
- `--version` e `--autoteste` na linha de comandos.

**Sistema de plugins**
- Plugin API com manifesto validado (`plugin.json`), contexto de plugin e
  ciclo de vida `inicializar/ativar/desativar/finalizar`.
- Plugin Manager: descoberta, validação, carregamento isolado, ativação,
  desativação, atualização, remoção e tolerância total a falhas — um plugin
  defeituoso não derruba a aplicação.
- Instalação a partir de `.zip` com proteção contra *path traversal*,
  caminhos absolutos, ligações simbólicas e *zip bombs*; nada é executado a
  partir do pacote.
- Atualização com backup e reposição automática em caso de falha; o plugin
  que estava a correr volta a correr na versão nova.
- Estado instalado/ativo persistido no banco (tabela `plugins`).
- Abstração de fontes de plugins (zips locais, plugins embutidos e o
  esqueleto de uma futura loja online).
- Tela `Configurações → Plugins` com instalar, ativar, desativar, atualizar e
  remover, mensagens amigáveis traduzidas e detalhes técnicos à parte.
- Plugin `Calendar Integration`, que reutiliza o calendário da aplicação.

**Distribuição**
- Empacotamento com PyInstaller (`GerenciadorDeTarefas.spec`) e `tools/build.py`,
  que valida o `.exe` gerado antes de dar o build por concluído.
- Instalador Inno Setup (`installer/setup.iss`): atalhos, Menu Iniciar,
  desinstalador, atualização que preserva os dados e desinstalação que só
  apaga dados pessoais mediante confirmação explícita.
- Ícone da aplicação e ferramentas para empacotar plugins e simular
  atualizações.

**Qualidade**
- 224 testes automatizados, incluindo testes que constroem a janela Tkinter
  real e o percurso completo de um plugin, do `.zip` até à aba.
- Executável, instalador, atualização e desinstalação verificados a correr,
  não apenas gerados (`tools/build.py`, `tools/testar_atualizacao.py`,
  `tools/testar_instalador.py`).
- Integração contínua a correr os testes em Windows e Linux e a construir o
  executável.
- `docs/AUDIT.md` com a auditoria do estado inicial do projeto.

## [0.1.0] - 2025-06-06
### Adicionado
- Estrutura inicial do projeto.
- Suporte a múltiplos idiomas.
- Interface gráfica com Tkinter.
- Base de dados SQLite integrada.
