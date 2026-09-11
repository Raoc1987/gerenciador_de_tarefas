# Arquitetura da plataforma

O produto evolui de **gestor de tarefas** para **plataforma modular de gestão**,
mantendo a gestão de tarefas como núcleo inicial.

A regra que organiza tudo o resto: **os módulos empresariais (RH, Estoque,
Financeiro, CRM, Manutenção…) não entram no núcleo.** O núcleo prepara-lhes o
terreno — plugins, eventos, permissões, analytics — para que possam ser
acrescentados sem transformar o programa num monólito.

## Camadas

```
        ┌──────────────────────────────────────────────┐
   UI   │  gui.py · dashboard_ui.py · plugin_ui.py     │
        ├──────────────────────────────────────────────┤
 APP    │  analytics/ (métricas, séries, insights)     │
        ├──────────────────────────────────────────────┤
 CORE   │  eventos · permissoes · plugins · config     │
        │  version · paths · log                       │
        ├──────────────────────────────────────────────┤
 INFRA  │  database.py (SQLite + migrações)            │
        └──────────────────────────────────────────────┘
```

Regras de dependência, verificadas por testes:

- a **UI** pode usar tudo abaixo dela;
- **analytics** não importa UI nem plugins;
- o **core** não importa UI nem analytics;
- **plugins** não importam `database`, `gui` nem o `PluginManager`: tudo o que
  usam chega pelo `ContextoPlugin`.

## A espinha de dados

Analytics não é uma tela isolada — atravessa o produto:

```
ação do utilizador
      ↓
database  ──publica──►  Event Bus  ──►  plugins / notificações / auditoria
      ↓
analytics (métricas, séries, tendências)
      ↓
dashboard (KPIs, gráficos)
      ↓
insights (descritivo → diagnóstico → preditivo)
```

Cada peça é utilizável sozinha e testável sem interface.

## Estado atual

| Bloco | Estado |
|---|---|
| Core: versão, caminhos, config, log | ✅ implementado |
| Persistência com migrações versionadas | ✅ implementado |
| Plugin Engine (ciclo de vida, ZIP seguro, rollback, fontes) | ✅ implementado |
| Idiomas (app + plugins) | ✅ implementado |
| Empacotamento e instalador Windows | ✅ implementado e testado |
| **Event Bus** | ✅ implementado |
| **Permissões (RBAC)** | ✅ implementado — sem autenticação (ver abaixo) |
| **Analytics Engine** | ✅ implementado |
| **Dashboard + gráficos** | ✅ implementado |
| Autenticação de utilizadores | ❌ **NÃO IMPLEMENTADO** |
| Multiempresa | ❌ **NÃO IMPLEMENTADO** |
| Licenciamento | ❌ **NÃO IMPLEMENTADO** |
| Auditoria persistida | ❌ **NÃO IMPLEMENTADO** (o Event Bus já dá a origem dos dados) |
| Relatórios / exportação | ❌ **NÃO IMPLEMENTADO** |
| Módulos empresariais (RH, Estoque, Financeiro…) | ❌ **NÃO IMPLEMENTADO** — por desenho: entram como plugins |
| Data Science (modelos) | ⚠️ parcial — tendência, previsão linear e anomalias por estatística simples; sem ML |

## Roadmap

Concluído: **FASE 0** (auditoria) · **FASE 1** (fundação arquitetural) ·
FASE 3 (Plugin Engine) · FASE 6–8 (Analytics, visualização, dashboard) ·
FASE 17–18 (empacotamento e instalador).

A seguir, por ordem de valor:

1. **Relatórios e exportação** (PDF/XLSX/CSV) — camada `reporting`, sem lógica
   na GUI. É o que falta para o dashboard virar entregável.
2. **Auditoria persistida** — consumir o Event Bus e gravar; o barramento já
   existe, falta o destino.
3. **Autenticação + sessão real** — hoje há papéis e permissões, mas um único
   utilizador local; sem isto, multiempresa e licenciamento não fazem sentido.
4. **Módulo Projetos** — primeiro módulo de gestão, já como plugin, para
   provar que o Plugin Engine aguenta um módulo de negócio a sério.
5. **Licenciamento** — só depois de existir algo que valha a pena licenciar.

Ver os ADRs nesta pasta para as decisões e os seus porquês.
