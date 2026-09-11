# Changelog

Todas as mudanças importantes deste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e
o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

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
