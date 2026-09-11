# Auditoria de Baseline — Gerenciador de Tarefas

Data: 2026-09-10
Commit base: `9eee4e5` (branch `main`)

## 1. Estado encontrado

| Arquivo | Tamanho | Estado |
|---|---|---|
| `src/main.py` | 0 bytes | **vazio** |
| `src/database.py` | 0 bytes | **vazio** |
| `src/language_manager.py` | 0 bytes | **vazio** |
| `src/calendar_widget.py` | 0 bytes | **vazio** |
| `src/gui.py` | 1698 bytes | implementado (parcial) |
| `src/utils.py` | 112 bytes | 1 função (`formatar_data`) |
| `assets/idiomas/pt.json` | 0 bytes | **vazio** |
| `assets/idiomas/en.json` | 0 bytes | **vazio** |
| `assets/idiomas/es.json` | 0 bytes | **vazio** |
| `requirements.txt` | 0 bytes | **vazio** |
| `tests/` | — | **não existe** |
| `test_database.py` | — | **não existe** |

Verificação no histórico do Git (`git log --follow`) confirma que estes arquivos
nasceram vazios no commit inicial `db2edab` e nunca tiveram conteúdo.

## 2. Consequências

* **A aplicação nunca executou.** `python src/main.py` não faz nada (arquivo vazio).
* **`src/gui.py` não é importável**: depende de `criar_tabela`, `buscar_tarefas`
  (de `database`) e `carregar_texto`, `definir_idioma` (de `language_manager`),
  nenhuma das quais existe.
* **Bug adicional em `gui.py:52`**: chama `atualizar_relógio(rodape)` sem que a
  função esteja definida ou importada (silenciada por `# type: ignore`).
* **Não há testes existentes para executar** — o critério "testes antigos PASS"
  da especificação é vacuosamente verdadeiro (conjunto vazio).

## 3. Arquitetura inferida (a partir de `gui.py`, única fonte de verdade)

```
main.py  ──►  gui.iniciar_interface()
                   │
                   ├─► database.criar_tabela() / buscar_tarefas()   (SQLite)
                   ├─► language_manager.definir_idioma() / carregar_texto()
                   │        └─► assets/idiomas/{pt,en,es}.json
                   ├─► utils.atualizar_relógio(label)  (relógio no rodapé)
                   └─► calendar_widget  (widget de calendário — não referenciado ainda)
```

Convenções observadas e que serão preservadas:

* GUI em **Tkinter/ttk** puro (sem dependências externas).
* Nomes de API **em português** (`criar_tabela`, `buscar_tarefas`, `carregar_texto`).
* Idiomas em **JSON plano** por idioma, sob `assets/idiomas/`.
* `buscar_tarefas()` retorna tuplas indexáveis, com a descrição em `tarefa[1]`
  (deduzido de `lista.insert(tk.END, tarefa[1])`) — logo a coluna 0 é o `id`.
* Imports **flat** dentro de `src/` (`from database import ...`), ou seja
  `src/` é a raiz de execução.
* `.gitignore` já ignora `tarefas.db` → o banco era pensado como SQLite local.

## 4. Ambiente

* Python **3.14.4** (`C:\Program Files\Python314\python.exe`)
* `tkinter` **8.6** disponível, `sqlite3` disponível
* `pytest` **9.1.1** e `pyinstaller` **6.22.2** instalados nesta sessão
* **Inno Setup não está instalado** nesta máquina (nem em `Program Files`
  nem em `Program Files (x86)`) → o `.iss` será criado e validado por
  inspeção, mas a geração do `Setup.exe` **NÃO PODE SER VALIDADA** aqui.

## 5. Decisão arquitetural

A especificação assume um projeto funcional a preservar. Como esse projeto não
existe, a decisão de **menor risco** é:

1. **Não reescrever `gui.py`** — ele define o contrato da aplicação. Implementar
   os módulos ausentes exatamente com a API que ele já espera.
2. Corrigir apenas o bloqueador real (`atualizar_relógio` ausente).
3. Só depois construir o sistema de plugins por cima dessa base.

O `core/` da especificação fica em `src/core/`, coerente com o layout `src/` já
existente, em vez de forçar uma raiz artificial.

---

## Atualização — 2026-09-11

O ponto 4 acima ("Inno Setup não está instalado") deixou de se aplicar: o
Inno Setup 6.7.3 foi instalado durante o trabalho (com autorização explícita),
o `GerenciadorDeTarefas-Setup.exe` foi compilado e o ciclo completo de
instalação, atualização e desinstalação foi executado e verificado por
`tools/testar_instalador.py`.

Nenhuma etapa do trabalho ficou por validar.
