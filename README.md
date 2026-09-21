# Gerenciador de Tarefas

Aplicação desktop em Python para organizar tarefas com SQLite, dashboard,
métricas, agenda mensal e exportação para CSV e Excel.

## Funcionalidades atuais

- Cadastro de tarefas com titulo, descricao, categoria, prioridade e data limite.
- Listagem com busca por titulo ou categoria.
- Filtros por status, categoria e periodo de data limite.
- Edicao completa de tarefas existentes.
- Marcacao de tarefas como pendentes ou concluidas.
- Exclusao de tarefas.
- Interface profissional com sidebar, barra de pesquisa, dashboard executivo e
  temas claro e escuro.
- Paleta SAV-inspired com azul técnico, ações em azul elétrico e controles com
  feedback visual de foco e hover.
- Idiomas em português, inglês e espanhol para a navegação e textos principais.
- Dashboard com total, pendentes, concluidas, atrasadas e taxa de conclusao.
- Indicadores e distribuição de tarefas por categoria no dashboard.
- Calendario mensal com contagem de tarefas por dia.
- Lembretes internos: informe data e hora da tarefa para receber um alerta com
  opções de abrir, dispensar ou adiar por 10 minutos.
- Importação de tarefas via `.xlsx`, `.xlsm` e `.csv`.
- Exportação para CSV, TSV, JSON, SQL, Excel analítico e arquivos CSV prontos
  para carregar no Power BI.
- Página Dados com tabela de tarefas preparada para exploração analítica.
- Base de testes unitarios para o banco de dados.

## Como executar

```powershell
cd F:\gerenciador_de_tarefas
pip install -r requirements.txt
python src\main.py
```

## Importar e analisar dados

- Na página **Relatórios**, use **Importar dados** para planilhas com colunas
  como `Título`, `Descrição`, `Categoria`, `Prioridade`, `Prazo`, `Hora` e
  `Status`. Cabeçalhos em inglês também são aceitos.
- **Exportar para Power BI** gera `tarefas_powerbi.csv` e
  `tarefas_powerbi_metricas.csv`. No Power BI Desktop, importe ambos por
  **Obter dados > Texto/CSV**.
- Para ativar um lembrete, informe a data no formato `AAAA-MM-DD` e a hora no
  formato `HH:MM` ao criar ou editar uma tarefa.

## Como testar

```powershell
cd F:\gerenciador_de_tarefas
python -m unittest discover -s tests
```

## Estrutura

```text
gerenciador_de_tarefas/
├── assets/idiomas/
├── src/
│   ├── app.py
│   ├── main.py
│   ├── database/        # SQLite e modelos de domínio
│   ├── services/        # exportação e indicadores
│   ├── ui/              # sidebar, páginas e tema
│   └── assets/          # base para ícones e temas
├── tests/
│   └── test_database.py
├── requirements.txt
└── README.md
```

## Proximas evolucoes

1. Sprint 2: projetos, categorias e configurações completas.
2. Sprint 3: subtarefas, tags, recorrência, anexos e progresso.
3. Sprint 4: gráficos executivos com Matplotlib.
4. Sprint 5 e 6: calendário avançado e relatórios em PDF.
5. Sprint 7: assistente integrado por IA.
