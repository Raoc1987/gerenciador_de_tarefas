# 🧠 Task Manager (Gerenciador de Tarefas)

Desktop task manager with multi-language support, a calendar, SQLite storage
and a **plugin system** — install, enable, update and remove plugins from the
app itself.

Runtime uses the Python standard library only: no external dependencies.

## 🌐 Languages

- [Português (BR)](README.md)
- [English (US)](README.en.md)

---

## 🚀 Features

- ✅ Add, complete and delete tasks, with due dates
- 🗓️ Calendar tab (shipped as a plugin) showing the tasks of each day
- 🌍 English, Portuguese and Spanish, switchable at runtime
- 🧩 Plugin system with safe `.zip` installation, updates and rollback
- 🧠 Local SQLite storage with versioned migrations
- 🕒 Live clock in the footer
- 🪟 Windows installer that never touches your data

---

## 📦 Install (end user)

1. Download `GerenciadorDeTarefas-Setup.exe` from the
   [releases page](https://github.com/Raoc1987/gerenciador_de_tarefas/releases).
2. Run it. By default it installs for the current user and **does not require
   administrator rights**; the first page lets you install for all users.
3. Launch it from the Start menu.

Where things live:

| What | Where |
|---|---|
| Program | `%LOCALAPPDATA%\Programs\GerenciadorDeTarefas` (or `Program Files`) |
| Database | `%APPDATA%\GerenciadorDeTarefas\tarefas.db` |
| Settings | `%APPDATA%\GerenciadorDeTarefas\config\` |
| Installed plugins | `%APPDATA%\GerenciadorDeTarefas\plugins\installed\` |
| Logs | `%APPDATA%\GerenciadorDeTarefas\logs\app.log` |

Your data lives **outside** the program folder, so upgrading or reinstalling
leaves it alone. Uninstalling only deletes it if you answer "yes" to an
explicit question.

---

## 💻 Development

```bash
git clone https://github.com/Raoc1987/gerenciador_de_tarefas.git
cd gerenciador_de_tarefas
pip install -r requirements-dev.txt
python src/main.py
```

Requires **Python 3.10+** with Tkinter. `requirements.txt` is intentionally
empty — there are no runtime dependencies; `requirements-dev.txt` brings
`pytest` and `pyinstaller`.

```bash
python -m pytest            # 222 tests
python src/main.py --autoteste   # self-check of a running installation
```

GUI tests build real Tkinter windows and are skipped automatically on
machines without a display.

---

## 🧩 Plugins

### Using them

`Settings → Plugins` lists installed plugins with their state and actions:

```
PLUGINS                                   [+ Install Plugin]
┌──────────────────────────────────────────────────────────┐
│ Calendar Integration  v1.0.0                             │
│ Shows tasks on a monthly calendar.                       │
│ Status: Enabled                                          │
│ [Disable] [Update] [Remove]                              │
└──────────────────────────────────────────────────────────┘
```

Disabling does **not** uninstall, and the state survives restarts. Updating
keeps a backup of the previous version and restores it automatically if the
update fails. Removing asks for confirmation, and asks separately whether to
delete that plugin's settings and data.

### Writing one

```
my_plugin/
├── plugin.json
├── plugin.py
└── idiomas/        (optional: pt.json, en.json, es.json)
```

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "You",
  "description": "What it does.",
  "min_app_version": "1.0.0",
  "entry_point": "plugin.py"
}
```

`id` must be 2–64 chars (lowercase letters, digits, `_`, `-`), match the
folder name, and be unique. `version` and `min_app_version` are semantic
versions; `max_app_version` is optional and inclusive.

```python
from core.plugin_api import Plugin


class MyPlugin(Plugin):
    def inicializar(self):
        """Called once, on load."""

    def ativar(self):
        """Start working: register tabs, hook events."""
        self.contexto.ui.registrar_aba(
            self.id,
            lambda: self.contexto.traduzir("aba"),   # follows the UI language
            self._build,
        )

    def _build(self, parent):
        from tkinter import ttk
        return ttk.Label(parent, text=self.contexto.traduzir("hello"))

    def desativar(self):
        """Stop working; the app removes the tabs."""

    def finalizar(self):
        """Release resources before the module is dropped."""
```

Everything a plugin may use comes through `self.contexto` — plugins never
import `database` or `gui` directly:

| Attribute | Purpose |
|---|---|
| `contexto.tarefas` | `listar()`, `listar_por_data(date)`, `adicionar(text, date)` |
| `contexto.ui` | `registrar_aba(id, title, builder)`, `notificar(message)` |
| `contexto.traduzir(key, default, **fmt)` | plugin and application texts |
| `contexto.config()` / `guardar_config(data)` | the plugin's private settings |
| `contexto.diretorio_dados` | writable folder owned by the plugin |
| `contexto.diretorio_plugin` | where the plugin is installed |
| `contexto.logger` | logger named after the plugin |
| `contexto.app_version` | running application version |

`contexto.ui` is `None` when there is no GUI (for example in tests).

Lifecycle: `DISCOVER → VALIDATE → INSTALL → REGISTER → LOAD → ACTIVATE → RUN
→ DEACTIVATE → UNLOAD`. An exception anywhere in it is logged, marks the
plugin as failed, and **never brings the application down**.

### Packaging

```bash
python tools/empacotar_plugin.py plugins/available/calendar
# -> dist/plugins/calendar-1.0.0.zip
```

The `.zip` is treated as untrusted: `..` paths, absolute paths, symlinks,
missing manifests and oversized packages are rejected, and nothing is ever
executed from the archive — files are extracted to a temporary area,
re-validated, and only then promoted to an installed plugin.

`plugins/available/calendar` is a complete working example.

---

## 🏗️ Architecture

```
gerenciador_de_tarefas/
├── src/
│   ├── main.py                 # entry point; --version, --autoteste
│   ├── gui.py                  # main window (tabs + menu)
│   ├── plugin_ui.py            # plugin screen and GUI extension points
│   ├── database.py             # SQLite with versioned migrations
│   ├── language_manager.py     # app and plugin translations
│   ├── calendar_widget.py      # reusable calendar
│   ├── utils.py
│   └── core/
│       ├── version.py          # single source of name and version
│       ├── paths.py            # resources vs. user data vs. temp
│       ├── config.py           # app settings and per-plugin settings
│       ├── log.py
│       ├── plugin_api.py       # manifest, context, Plugin base class
│       ├── plugin_manager.py   # plugin lifecycle
│       ├── plugin_package.py   # safe .zip validation and extraction
│       ├── plugin_registry.py  # plugin state in the database
│       └── plugin_sources.py   # local zips, bundled, future online store
├── plugins/available/calendar/ # plugin shipped with the app
├── assets/idiomas/             # pt.json, en.json, es.json
├── installer/setup.iss         # Inno Setup installer
├── tools/                      # build, installer, plugin packaging, icon
├── tests/                      # 222 tests
└── GerenciadorDeTarefas.spec   # PyInstaller recipe
```

Principles: the core never knows concrete plugins; the version lives in one
place and is read by the app, PyInstaller and Inno Setup; user data never goes
into `Program Files`; a plugin failure never takes the app down.

---

## 🔨 Building

```bash
python tools/build.py              # dist/GerenciadorDeTarefas/GerenciadorDeTarefas.exe
python tools/build_installer.py    # installer/Output/GerenciadorDeTarefas-Setup.exe
python tools/testar_atualizacao.py # upgrade simulation (no installer needed)
python tools/testar_instalador.py  # install, upgrade and uninstall, for real
```

Silent install and uninstall:

```bat
GerenciadorDeTarefas-Setup.exe /VERYSILENT /NORESTART /CURRENTUSER /DIR="C:\GDT"
"C:\GDT\unins000.exe" /VERYSILENT                   :: keeps your data
"C:\GDT\unins000.exe" /VERYSILENT /REMOVEDATA=yes   :: deletes it too
```

A silent uninstall **never** deletes your data without `/REMOVEDATA=yes`.

`tools/build.py` only reports success after running the produced `.exe` with
`--version` and `--autoteste`. The installer needs
[Inno Setup 6.3+](https://jrsoftware.org/isdl.php); point the `ISCC`
environment variable at `ISCC.exe` if it is installed elsewhere.

Plugins are loaded at runtime, so PyInstaller cannot see their imports: the
modules available to plugins are declared in `hiddenimports` inside
`GerenciadorDeTarefas.spec`.

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| "Invalid plugin" on install | The `.zip` needs `plugin.json` at its root or in a single top folder, and `id` must match that folder's name. |
| "Requires a different version" | The plugin's `min_app_version` is newer than your app; update the app. |
| "Already installed" | Installing over an existing plugin requires a **newer** version; remove it first to reinstall the same one. |
| A plugin fails to start | The app warns and keeps running; the reason is in `%APPDATA%\GerenciadorDeTarefas\logs\app.log`. |
| Works in dev, not in the `.exe` | A module is missing from `hiddenimports` in the `.spec`. |
| Start over | Close the app and delete `%APPDATA%\GerenciadorDeTarefas` (loses tasks and plugins). |

---

## 📄 License

MIT — see [LICENSE](LICENSE).

## 🧠 Author

**Rodrigo Costa** — [GitHub/Raoc1987](https://github.com/Raoc1987)
