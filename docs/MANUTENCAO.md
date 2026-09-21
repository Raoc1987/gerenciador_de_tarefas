# Manutenção — Preditiva, Preventiva e Corretiva

Data: 2026-09-21 · Versão de referência: `1.1.0` (tag `v1.1.0`, 2026-09-20)

**Fronteira entre categorias.** Preditiva antecipa uma falha a partir de um sinal
ou tendência. Preventiva reduz a probabilidade de falha por rotina agendada,
haja ou não sinal. Corretiva responde a uma falha já ocorrida. Cada item
pertence a uma só categoria; um item que parecesse servir duas foi dividido.

**Legenda.** `[hoje]` vale já, com a aplicação empacotada mas sem base instalada
conhecida. `[pós]` só passa a fazer sentido quando houver instalações reais de
terceiros. **Pendência** marca o que ainda não existe no repositório e não pode
ser dado como configurado. Última varredura de pendências: 2026-09-21.

**O que este stack não tem, de propósito.** Não há servidor, API, telemetria nem
serviço de *crash reporting*: a aplicação corre na máquina do utilizador, só com
a biblioteca padrão (ADR-0002), e o único acesso à rede é o plugin de
atualizações, que pede consentimento e nunca descarrega nada. Não há, portanto,
sinais do lado do servidor — tudo o que é preditivo vem do CI, do repositório ou
de ficheiros locais que só chegam se o utilizador os enviar. Introduzir
telemetria seria mudar o produto, não fazer-lhe manutenção.

---

## 1. Preditiva

| Item | Sinal / gatilho | Ferramenta | Cadência | Responsável |
|---|---|---|---|---|
| Suíte de testes a degradar | Duração do job `testes` acima de 2× a mediana das últimas 10 execuções, ou acima de 10 min | Histórico do GitHub Actions (`.github/workflows/tests.yml`) | Leitura a cada PR; revisão semanal | Fundador (manual) — **pendência**: não há recolha automática da duração |
| Testes intermitentes (*flaky*) | O mesmo teste falha e volta a passar sem alteração de código ≥ 2× em 10 execuções | Histórico do Actions, matriz `windows/ubuntu × 3.10/3.13` | Semanal | Fundador (manual) |
| Dependência de execução a entrar | `requirements.txt` deixa de estar vazio, ou um ficheiro em `src/` importa um módulo fora da biblioteca padrão | `tests/test_arquitetura.py::test_a_aplicacao_so_usa_a_biblioteca_padrao` e `::test_nao_ha_dependencias_de_execucao_declaradas` | A cada PR | CI (automático) |
| Executável a inchar | `dist/GerenciadorDeTarefas/` cresce > 15 % face à última release | Artefacto do job `empacotamento`; comparação manual dos tamanhos | Em cada PR que toque `requirements*.txt`, `GerenciadorDeTarefas.spec` ou `tools/build.py` | Fundador (manual) |
| Release em atraso | Secção "Não lançado" do CHANGELOG a crescer sem que saia uma versão — uma release grande é a que é difícil de reverter | `git tag --list "v*"`, `CHANGELOG.md` | Quinzenal | Fundador (manual) |
| Etiqueta sem release | Existe uma etiqueta `v*` sem release publicada: a tentativa falhou e ficou a marca (hoje, `v1.0.1` e `v1.2.0`, recusadas por não baterem certo com `core/version.py`) | `gh release list` contra `git tag`; o guarda é `tools/verificar_versao.py` | A cada release, e na revisão quinzenal | Fundador (manual) — a etiqueta órfã faz `git describe` mentir sobre a versão publicada |
| Fim de vida do Python suportado | Versão mínima da matriz (3.10) a menos de 6 meses do EOL, ou mudança de imagem do runner `windows-latest` | endoflife.date/python; notas de release dos runners GitHub | Trimestral | Fundador (manual) |
| Rutura do contrato de plugins | PR que altere assinaturas em `core/plugin_api.py`, ou plugin embutido com `max_app_version` abaixo do `APP_VERSION` em preparação | `tests/test_arquitetura.py::test_os_plugins_embutidos_abrem_nesta_versao` | A cada PR | CI (automático) |
| Banco do utilizador a crescer `[pós]` | `tarefas.db` > 50 MB, ou tabela `auditoria` > 200 000 linhas, ou abertura do Dashboard percetivelmente mais lenta | `Configurações → Auditoria`; `--verificar-banco`; `EXPLAIN QUERY PLAN` numa cópia | Mensal, numa instalação de referência | Fundador (manual) — **pendência**: não há medição instrumentada da duração das consultas |
| Log a rodar depressa demais `[pós]` | Existência de `app.log.1`…`app.log.5` renovados no mesmo dia: volume anómalo de `WARNING`/`ERROR` | `core/log.py` (rotativo, 2 MB × 5 ≈ 12 MB no total) | Ao receber um pedido de suporte | Utilizador envia o ficheiro; fundador lê |
| Origem das atualizações em baixo `[pós]` | Falhas repetidas da verificação do plugin de atualizações, registadas em silêncio no log | `plugins/available/atualizacoes/plugin.py`, `app.log` | Ao receber um pedido de suporte | Fundador (manual) |

**Escalonamento (sinal preditivo → acção preventiva urgente).** Um sinal sobe a
acção imediata, fora da cadência normal, quando: (a) aponta para perda de dados
do utilizador — banco a crescer com lentidão associada, log que engole a prova,
migração por aplicar; (b) bloqueia a capacidade de libertar uma correcção — CI
lento ou intermitente ao ponto de a suíte deixar de ser fiável; ou (c) o prazo é
externo e não negociável — EOL do Python, mudança de imagem do runner. Nos
restantes casos o sinal entra na lista da rotina seguinte.

---

## 2. Preventiva

| Item | Rotina agendada | Ferramenta | Cadência | Responsável |
|---|---|---|---|---|
| Atualizar dependências de desenvolvimento | `pip list --outdated` sobre `requirements-dev.txt` (pytest, pyinstaller, openpyxl, pypdf, pillow) e correr a suíte completa | Dependabot (`.github/dependabot.yml`) abre o PR; pytest valida-o | Semanal (PR automático); revisão do fundador ao aceitar | Dependabot + fundador |
| Suíte completa fora do fluxo de PR | Correr a matriz inteira sem depender de haver commits | GitHub Actions, gatilho `schedule` (segunda-feira, 06:00 UTC) | Semanal | CI (automático) |
| Ensaio de restauro de cópia de segurança | Criar cópia, restaurá-la numa pasta descartável via `GDT_DATA_DIR` e conferir contagens de tarefas, contas e registo de plugins | `core/backup.py`, variável `GDT_DATA_DIR` | Trimestral `[hoje]`; mensal `[pós]` | Fundador (manual) |
| Ensaio de atualização preservando dados | Substituir os ficheiros da aplicação como o instalador faz e confirmar que tarefas, configuração e plugins sobrevivem | `tools/testar_atualizacao.py`, no job `ensaios` (`tests.yml`) e no `release.yml` | Semanal, a pedido (`workflow_dispatch`) e **sempre** que se marca uma versão | CI (automático) |
| Ensaio do instalador de ponta a ponta | Instalação limpa, atualização, desinstalação com e sem `/REMOVEDATA` | `tools/testar_instalador.py`, no job `ensaios` (`tests.yml`) e no `release.yml` | Semanal, a pedido e **sempre** que se marca uma versão | CI (automático) |
| Política de retenção da auditoria | Fixar o prazo (ex.: 365 dias) e aplicá-lo | Chave `auditoria_retencao_dias` em `app_config.json`, aplicada no arranque por `auditoria.aplicar_retencao_configurada()` | A cada arranque; revisão do prazo trimestral | Aplicação (automático) — sem chave definida guarda para sempre, que é o padrão |
| Integridade do banco `[pós]` | `PRAGMA integrity_check` e `PRAGMA user_version` numa instalação de referência | `python src/main.py --verificar-banco` (abre só de leitura) | Mensal | Fundador (manual) |
| Higiene da cadeia de build | Confirmar que as Actions continuam fixadas por SHA, que os SHA correspondem à versão pretendida, e que a escrita continua confinada ao `release.yml` | `tests.yml` (`contents: read`) e `release.yml` (`contents: write`, necessário para publicar a release e anexar o instalador) | Semestral, e sempre que o Dependabot propuser uma Action nova | Fundador (manual) |
| Assinatura do instalador | Decidir e documentar se o `.exe` passa a ser assinado; enquanto não for, manter documentado o aviso do SmartScreen | `installer/setup.iss` | Semestral, ou antes de qualquer distribuição alargada | Fundador (manual) — **pendência que não se resolve em código**: exige um certificado de assinatura em nome do editor; até o haver, `setup.iss` continua sem directiva de assinatura e o SmartScreen avisa |
| Revisão da matriz de versões do CI | Acrescentar a versão estável nova do Python e retirar a que entrou em EOL | `.github/workflows/tests.yml` | Semestral | Fundador (manual) |
| Revisão de permissões e perfis | Conferir que a matriz de `core/permissoes.py` corresponde ao que a interface mostra e ao que os testes exigem | Leitura de código + `tests/test_permissoes.py` | Semestral | Fundador (manual) |
| Cobertura de testes | Medir cobertura, para saber onde a suíte de 896 testes não chega | `pytest --cov=src --cov-report=term-missing`, já corrido no CI | A cada PR (relatório); revisão trimestral | CI (automático) + fundador |

**Escalonamento (preventivo).** Uma rotina falhada que toque em dados — restauro
que não repõe, instalador que não preserva `%APPDATA%\GerenciadorDeTarefas` —
bloqueia a release seguinte até estar resolvida. Uma rotina falhada que não toque
em dados (dependência de desenvolvimento desatualizada, cobertura por medir)
entra na lista de trabalho normal. Qualquer pendência desta secção que seja
pré-requisito de um item da secção 3 sobe de prioridade no momento em que esse
item for accionado pela primeira vez.

---

## 3. Corretiva

Nenhum item assume a causa: a primeira acção é sempre investigação.

| Item | Gatilho (falha ocorrida) | Diagnóstico obrigatório antes de corrigir | Ferramenta | Responsável |
|---|---|---|---|---|
| Aplicação não arranca depois de instalar ou atualizar | Relato de utilizador, ou arranque falhado em máquina de teste | Correr `GerenciadorDeTarefas.exe --autoteste --relatorio <ficheiro>`; repetir com `GDT_DATA_DIR` a apontar para uma pasta vazia — separa "binário partido" de "dados do utilizador" antes de qualquer hipótese | `--autoteste`, `app.log`, `GDT_DATA_DIR` | Fundador |
| Exceção não tratada na interface | Janela fecha, trava, ou uma acção não produz efeito | Reproduzir com o log em `INFO`; se não houver *traceback*, assumir que o Tk o engoliu e instrumentar **antes** de teorizar sobre a causa | `core/log.py` (`instalar_captura_de_excecoes`) e `main.instalar_captura_do_tk` — interpretador, *threads* e *callbacks* do Tk vão todos para `app.log` | Fundador |
| Migração de banco falha a meio | Erro no arranque após atualização, ou funcionalidade que depende de coluna nova a falhar | Correr `--verificar-banco` (não escreve nada) para saber em que versão ficou o schema e se o ficheiro está íntegro; só depois identificar qual a migração que não aplicou | `main.verificar_banco`, `banco_de_dados._aplicar_migracoes` | Fundador |
| Restauro perde ou corrompe dados | Utilizador restaura e o estado não corresponde | Recuperar primeiro a cópia de emergência que `restaurar` grava antes de tocar em seja o que for; só depois reproduzir com o ficheiro do utilizador numa pasta descartável | `core/backup.py` | Fundador |
| Plugin derruba a aplicação | Falha que desaparece com o plugin desativado | Desativar e reproduzir; determinar se o núcleo isolou o erro ou se o deixou propagar — a resposta muda quem tem o defeito | `tests/test_plugin_isolamento.py`, `app.log` | Fundador |
| Plugins desativados em massa após atualização | Utilizador perde abas depois de atualizar | Comparar `min_app_version`/`max_app_version` dos manifestos instalados com o `APP_VERSION` novo, via `versao_compativel()`; não presumir incompatibilidade real sem isso | `core/plugin_api.py`, registo de plugins | Fundador |
| Instalador ou desinstalador mexe em dados do utilizador | Dados desaparecem depois de atualizar ou desinstalar | Reproduzir com `python tools/testar_instalador.py` em máquina ou VM limpa (o script aborta se a pasta de dados real já existir) | Script do repositório + Inno Setup | Fundador |
| Relatório PDF/XLSX ilegível | Ficheiro exportado não abre no Excel ou no leitor de PDF | Reproduzir a exportação e reabrir o resultado com `openpyxl`/`pypdf`, como fazem os testes, antes de alterar o escritor | `relatorios/`, `tests/test_relatorios.py` | Fundador |
| Release falha depois de a etiqueta estar marcada | O workflow `release.yml` acaba em erro e fica uma etiqueta sem release | Ler o job que falhou antes de voltar a marcar; se foi o guarda da versão, o defeito está em `core/version.py` ou na etiqueta, não no build | `gh run view`, `tools/verificar_versao.py` | Fundador — apagar a etiqueta órfã antes de remarcar; reutilizar uma etiqueta publicada é pior do que criar outra |
| `main` com testes vermelhos | Job `testes` falha em `main` | `git bisect` para localizar o commit; repetir a execução para distinguir falha real de intermitente | GitHub Actions, `git bisect` | Fundador |

**Escalonamento (corretivo).** Exige **retirada imediata da release** —
despublicar o `.exe` da página de releases, repor o anterior e dizê-lo nas notas
— o defeito que corrompe ou apaga dados do utilizador (migração, restauro,
instalador/desinstalador) ou que impede o arranque em máquina limpa. A versão
corrigida sai numa etiqueta nova, com `core/version.py` a subir primeiro:
reaproveitar uma etiqueta já publicada faria o mesmo número corresponder a dois
instaladores diferentes, e quem já descarregou não teria como saber qual tem. Tudo o resto
— defeito de interface com contorno possível, plugin isolado, relatório mal
formatado — é corrigido na versão seguinte. `main` vermelho por mais de 24 h
bloqueia qualquer release, seja qual for a gravidade do defeito original.

**Limite honesto deste canal.** Não há atualização automática: o plugin de
atualizações apenas avisa e abre a página oficial. Uma release retirada continua
instalada em quem já a instalou, e não existe forma de a recuperar à distância.
Na prática, "rollback" significa *parar a propagação* e publicar depressa uma
versão corrigida — o que faz dos ensaios preventivos de instalador e de
atualização (secção 2) a última defesa real, e não uma formalidade.
