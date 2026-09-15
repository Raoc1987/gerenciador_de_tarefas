"""Interface gráfica (Tkinter) do Gerenciador de Tarefas."""

import tkinter as tk
from tkinter import messagebox, ttk

from auditoria_ui import JanelaAuditoria
import alertas
import automacoes
import importacoes_incluidas
import indicadores_incluidos
import pesquisas_incluidas
from core import auditoria, eventos, funcionalidades, permissoes
from importacao_ui import JanelaImportacao
from pesquisa_ui import JanelaPesquisa
from regras import motor as motor_de_regras
from core.log import obter_logger
from core.paths import caminho_recurso, diretorio_plugins_embutidos
from core.plugin_manager import PluginManager
from core.plugin_registry import RegistroEstadoBanco
from core.permissoes import Permissao, PermissaoNegadaError
from core.plugin_sources import FontePastasLocais
from dashboard_ui import PainelDashboard
import tarefas_servico
from backup_ui import JanelaBackup
from funcionalidades_ui import JanelaFuncionalidades
from regras_ui import JanelaAutomacoes
from organizacao_ui import JanelaOrganizacao
from language_manager import (
    IDIOMAS_SUPORTADOS,
    carregar_texto,
    definir_idioma,
    idioma_atual,
    restaurar_idioma_guardado,
)
from plugin_ui import AnfitriaoGUI, JanelaPlugins, ServicoTarefasApp
from utilizadores_ui import JanelaUtilizadores
from utils import atualizar_relógio, formatar_data, validar_data_iso

logger = obter_logger(__name__)


def _rotulo_tarefa(tarefa, mostrar_dono: bool = False) -> str:
    """Formata uma linha da lista: ``[✔] descrição (vencimento) — dono``."""
    identificador, descricao, vencimento, concluida, _ = tarefa
    marca = "[✔]" if concluida else "[  ]"
    sufixo = f"  ({formatar_data(vencimento)})" if vencimento else ""
    if mostrar_dono:
        criador = tarefas_servico.dono(identificador)
        if criador:
            sufixo += f"  — {criador}"
    return f"{marca} {descricao}{sufixo}"


def _aplicar_icone(app: tk.Tk) -> None:
    """Usa o ícone da aplicação na janela, se estiver disponível."""
    icone = caminho_recurso("assets", "icon.ico")
    if not icone.is_file():
        return
    try:
        app.iconbitmap(default=str(icone))
    except tk.TclError:  # pragma: no cover - plataformas sem suporte a .ico
        logger.debug("Não foi possível aplicar o ícone da janela.")


def criar_gerenciador_de_plugins(anfitriao=None) -> PluginManager:
    """Cria o PluginManager já ligado ao banco e aos serviços da aplicação."""
    return PluginManager(
        registro=RegistroEstadoBanco(),
        ui=anfitriao,
        tarefas=ServicoTarefasApp(),
    )


def criar_janela(raiz: tk.Tk | None = None) -> tk.Tk:
    """Constrói a janela principal sem entrar no laço de eventos.

    Args:
        raiz: janela Tk já existente — é assim que o início de sessão e a
            aplicação partilham o mesmo interpretador, em vez de criarem dois.

    Separado de :func:`iniciar_interface` para que os testes possam exercitar
    a interface real sem bloquear no ``mainloop``.
    """
    tarefas_servico.garantir_esquema()
    restaurar_idioma_guardado()
    # A auditoria liga-se ao barramento antes de qualquer coisa acontecer.
    auditoria.ativar()
    # A automação depois dela: assim o que uma regra faz também fica na trilha.
    automacoes.registar_incluidas()
    pesquisas_incluidas.registar_incluidas()
    indicadores_incluidos.registar_incluidos()
    importacoes_incluidas.registar_incluidos()
    motor_de_regras.ativar()
    # A vigilancia depois do motor: assim o que ela anuncia ja encontra as
    # regras a ouvir.
    alertas.ativar()
    eventos.publicar(eventos.APP_INICIADA, origem="gui")

    app = raiz if raiz is not None else tk.Tk()
    app.deiconify()
    app.title(carregar_texto("titulo"))
    app.geometry("800x600")
    _aplicar_icone(app)

    # ------------------------------------------------------------ topo
    frame_topo = ttk.Frame(app)
    frame_topo.pack(pady=10)

    # Variável de idioma (mostra o rótulo, guarda o código)
    rotulos_idioma = {rotulo: codigo for codigo, rotulo in IDIOMAS_SUPORTADOS.items()}
    idioma_var = tk.StringVar(value=IDIOMAS_SUPORTADOS[idioma_atual()])

    label_titulo = ttk.Label(frame_topo, font=("Arial", 18))
    label_titulo.pack()

    label_sessao = ttk.Label(frame_topo, foreground="#7a8794", font=("Arial", 9))
    label_sessao.pack()

    dropdown = ttk.OptionMenu(
        frame_topo,
        idioma_var,
        idioma_var.get(),
        *rotulos_idioma.keys(),
        command=lambda _=None: mudar_idioma(),
    )
    dropdown.pack(pady=5)

    # ------------------------------------------- abas (tarefas + plugins)
    notebook = ttk.Notebook(app)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10)

    # A aba só é construída se a instalação tiver o painel: criá-la e escondê-la
    # seria pagar o custo de a desenhar para não a mostrar.
    painel_dashboard = None
    if funcionalidades.ativa("painel"):
        painel_dashboard = PainelDashboard(notebook)
        notebook.add(painel_dashboard, text=carregar_texto("dashboard"))

    aba_tarefas = ttk.Frame(notebook)
    notebook.add(aba_tarefas, text=carregar_texto("tarefas"))

    # ------------------------------------------------- formulário de tarefa
    frame_form = ttk.Frame(aba_tarefas)
    frame_form.pack(pady=5)

    label_descricao = ttk.Label(frame_form)
    label_descricao.grid(row=0, column=0, padx=4, sticky=tk.W)
    entrada_descricao = ttk.Entry(frame_form, width=45)
    entrada_descricao.grid(row=1, column=0, padx=4)

    label_data = ttk.Label(frame_form)
    label_data.grid(row=0, column=1, padx=4, sticky=tk.W)
    entrada_data = ttk.Entry(frame_form, width=16)
    entrada_data.grid(row=1, column=1, padx=4)

    botao_adicionar = ttk.Button(frame_form, command=lambda: acao_adicionar())
    botao_adicionar.grid(row=1, column=2, padx=4)

    # Só faz sentido escolher entre "as minhas" e "todas" a quem vê todas.
    apenas_minhas = tk.BooleanVar(value=False)
    caixa_minhas = ttk.Checkbutton(
        frame_form, variable=apenas_minhas, command=lambda: recarregar_lista()
    )
    if tarefas_servico.ve_tudo():
        caixa_minhas.grid(row=1, column=3, padx=(12, 0))

    # -------------------------------------------------------- lista + ações
    lista = tk.Listbox(aba_tarefas, width=80, height=15)
    lista.pack(pady=10)

    frame_acoes = ttk.Frame(aba_tarefas)
    frame_acoes.pack()
    botao_concluir = ttk.Button(frame_acoes, command=lambda: acao_concluir())
    botao_concluir.grid(row=0, column=0, padx=4)
    botao_remover = ttk.Button(frame_acoes, command=lambda: acao_remover())
    botao_remover.grid(row=0, column=1, padx=4)
    botao_atualizar = ttk.Button(frame_acoes, command=lambda: recarregar_lista())
    botao_atualizar.grid(row=0, column=2, padx=4)

    # Ids das tarefas na mesma ordem da Listbox.
    ids_visiveis = []

    def recarregar_lista():
        """Relê as tarefas visíveis e repovoa a Listbox."""
        lista.delete(0, tk.END)
        ids_visiveis.clear()
        so_minhas = bool(apenas_minhas.get())
        tarefas = tarefas_servico.listar(apenas_minhas=so_minhas)
        mostrar_dono = tarefas_servico.ve_tudo() and not so_minhas
        if not tarefas:
            lista.insert(tk.END, carregar_texto("sem_tarefas"))
            return
        for tarefa in tarefas:
            ids_visiveis.append(tarefa[0])
            lista.insert(tk.END, _rotulo_tarefa(tarefa, mostrar_dono))

    def tarefa_selecionada():
        """Id da tarefa selecionada, ou ``None`` (avisando o utilizador)."""
        selecao = lista.curselection()
        if not selecao or selecao[0] >= len(ids_visiveis):
            messagebox.showinfo(carregar_texto("informacao"), carregar_texto("selecione_tarefa"))
            return None
        return ids_visiveis[selecao[0]]

    def acao_adicionar():
        descricao = entrada_descricao.get().strip()
        vencimento = entrada_data.get().strip() or None
        if not descricao:
            messagebox.showwarning(carregar_texto("aviso"), carregar_texto("descricao_vazia"))
            return
        if not validar_data_iso(vencimento):
            messagebox.showwarning(carregar_texto("aviso"), carregar_texto("data_invalida"))
            return
        try:
            tarefas_servico.adicionar(descricao, vencimento)
        except PermissaoNegadaError:
            messagebox.showwarning(
                carregar_texto("aviso"), carregar_texto("permissao_negada")
            )
            return
        entrada_descricao.delete(0, tk.END)
        entrada_data.delete(0, tk.END)
        recarregar_lista()

    def acao_concluir():
        tarefa_id = tarefa_selecionada()
        if tarefa_id is None:
            return
        atual = tarefas_servico.obter(tarefa_id)
        if atual is not None:
            try:
                tarefas_servico.concluir(tarefa_id, not atual[3])
            except PermissaoNegadaError:
                messagebox.showwarning(
                    carregar_texto("aviso"), carregar_texto("tarefa_de_outro")
                )
        recarregar_lista()

    def acao_remover():
        tarefa_id = tarefa_selecionada()
        if tarefa_id is None:
            return
        rotulo = lista.get(lista.curselection()[0])
        if messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("confirmar_remocao", item=rotulo),
        ):
            try:
                tarefas_servico.remover(tarefa_id)
            except PermissaoNegadaError:
                messagebox.showwarning(
                    carregar_texto("aviso"), carregar_texto("tarefa_de_outro")
                )
            recarregar_lista()

    # ------------------------------------------------------------- plugins
    anfitriao = AnfitriaoGUI(notebook)
    gerenciador = criar_gerenciador_de_plugins(anfitriao)
    app.gerenciador_de_plugins = gerenciador  # facilita testes e depuração

    def abrir_plugins():
        JanelaPlugins(app, gerenciador, FontePastasLocais(diretorio_plugins_embutidos()))

    def abrir_auditoria():
        JanelaAuditoria(app)

    def abrir_utilizadores():
        JanelaUtilizadores(app)

    def abrir_estrutura():
        JanelaOrganizacao(app)

    def abrir_backup():
        JanelaBackup(app)

    def abrir_funcionalidades():
        JanelaFuncionalidades(app)

    def abrir_automacoes():
        JanelaAutomacoes(app)

    def abrir_pesquisa(_evento=None):
        JanelaPesquisa(app)

    def abrir_importacao():
        JanelaImportacao(app)

    def arrancar_plugins():
        """Semeia os plugins embutidos e ativa os que o utilizador deixou ligados."""
        try:
            gerenciador.semear_de_fonte(FontePastasLocais(diretorio_plugins_embutidos()))
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao instalar os plugins embutidos.")
        gerenciador.descobrir()
        falhas = [r for r in gerenciador.ativar_habilitados() if not r.sucesso]
        if falhas:
            nomes = ", ".join(
                (gerenciador.obter(r.plugin_id).nome if gerenciador.obter(r.plugin_id) else r.plugin_id)
                for r in falhas
            )
            messagebox.showwarning(
                carregar_texto("aviso"),
                carregar_texto("plugin_falha_arranque", nomes=nomes),
            )

    # ------------------------------------------------------------- rodapé
    rodape = ttk.Label(app, font=("Arial", 10))
    rodape.pack(side=tk.BOTTOM, pady=5)
    atualizar_relógio(rodape)

    # ------------------------------------------------------------- idiomas
    def construir_menu():
        """(Re)constrói a barra de menus no idioma atual."""
        barra = tk.Menu(app, tearoff=0)
        configuracoes = tk.Menu(barra, tearoff=0)
        configuracoes.add_command(
            label=carregar_texto("plugins") + "...", command=abrir_plugins
        )
        configuracoes.add_command(
            label=carregar_texto("importar") + "...", command=abrir_importacao
        )
        if permissoes.pode(Permissao.UTILIZADORES_GERIR):
            configuracoes.add_command(
                label=carregar_texto("utilizadores") + "...", command=abrir_utilizadores
            )
        # A estrutura e a trilha de auditoria são de quem administra a
        # instalação: mexer na primeira muda o que as outras pessoas veem.
        if permissoes.pode(Permissao.SISTEMA_ADMIN):
            configuracoes.add_separator()
            if funcionalidades.ativa("estrutura"):
                configuracoes.add_command(
                    label=carregar_texto("estrutura") + "...", command=abrir_estrutura
                )
            configuracoes.add_command(
                label=carregar_texto("auditoria") + "...", command=abrir_auditoria
            )
            configuracoes.add_command(
                label=carregar_texto("backup") + "...", command=abrir_backup
            )
            configuracoes.add_command(
                label=carregar_texto("automacoes") + "...", command=abrir_automacoes
            )
            configuracoes.add_command(
                label=carregar_texto("funcionalidades") + "...",
                command=abrir_funcionalidades,
            )
        barra.add_cascade(label=carregar_texto("configuracoes"), menu=configuracoes)
        # Fora de Configurações: pesquisar é uma ação de todos os dias, não
        # uma definição. E tem atalho, que é como se usa uma pesquisa.
        barra.add_command(
            label=carregar_texto("pesquisa") + "  (Ctrl+F)", command=abrir_pesquisa
        )
        app.config(menu=barra)

    def mudar_idioma():
        definir_idioma(rotulos_idioma[idioma_var.get()])
        atualizar_textos()
    # Ctrl+F é como se usa uma pesquisa; um menu sem atalho é uma pesquisa
    # que ninguém usa.
    app.bind_all("<Control-f>", abrir_pesquisa)
    app.bind_all("<Control-F>", abrir_pesquisa)

    def atualizar_textos():
        """Reaplica todos os textos visíveis conforme o idioma atual."""
        app.title(carregar_texto("titulo"))
        label_titulo.config(text=carregar_texto("titulo"))
        label_sessao.config(
            text=carregar_texto("sessao_de", nome=permissoes.sessao().utilizador)
        )
        label_descricao.config(text=carregar_texto("descricao_tarefa"))
        label_data.config(text=carregar_texto("data_vencimento"))
        botao_adicionar.config(text=carregar_texto("adicionar"))
        botao_concluir.config(text=carregar_texto("concluir"))
        botao_remover.config(text=carregar_texto("remover"))
        botao_atualizar.config(text=carregar_texto("atualizar_lista"))
        caixa_minhas.config(text=carregar_texto("so_as_minhas"))
        if painel_dashboard is not None:
            notebook.tab(painel_dashboard, text=carregar_texto("dashboard"))
        notebook.tab(aba_tarefas, text=carregar_texto("tarefas"))
        if painel_dashboard is not None:
            painel_dashboard.aplicar_idioma()
        anfitriao.atualizar_traducoes()
        construir_menu()
        recarregar_lista()

    def ao_fechar():
        """Encerra os plugins antes de fechar a janela."""
        try:
            eventos.publicar(eventos.APP_ENCERRADA, origem="gui")
            gerenciador.desativar_todos()
        except Exception:  # pragma: no cover - defensivo
            logger.exception("Falha ao encerrar os plugins.")
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", ao_fechar)

    atualizar_textos()
    arrancar_plugins()
    logger.info("Janela principal criada.")
    return app


def iniciar_interface():
    """Cria e executa a janela principal da aplicação."""
    criar_janela().mainloop()
