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

### Verificar uma instalação

```bash
python src/main.py --autoteste
```

Verifica banco, idiomas, recursos, plugins e criação da janela, e devolve
código de saída diferente de zero se algo falhar. Funciona também no
executável empacotado:

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


### Plugins incluídos

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
  "entry_point": "plugin.py"
}
```

Regras do manifesto:

- `id`: 2 a 64 caracteres, minúsculas, dígitos, `_` ou `-`; tem de ser igual
  ao nome da pasta e único entre os plugins instalados;
- `version` e `min_app_version`: versão semântica (`1.2.3`);
- `max_app_version`: opcional, inclusivo;
- `entry_point`: arquivo `.py` dentro da pasta do plugin (sem `..`, sem
  caminho absoluto).

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
