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

### Corrigido

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
