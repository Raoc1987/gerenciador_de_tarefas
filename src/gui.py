"""Interface gráfica (Tkinter) do Gerenciador de Tarefas."""

import tkinter as tk
from tkinter import messagebox, ttk

from core.log import obter_logger
from core.plugin_manager import PluginManager
from core.plugin_registry import RegistroEstadoBanco
from database import (
    adicionar_tarefa,
    buscar_tarefas,
    concluir_tarefa,
    criar_tabela,
    remover_tarefa,
)
from language_manager import (
    IDIOMAS_SUPORTADOS,
    carregar_texto,
    definir_idioma,
    idioma_atual,
    restaurar_idioma_guardado,
)
from plugin_ui import AnfitriaoGUI, JanelaPlugins, ServicoTarefasApp
from utils import atualizar_relógio, formatar_data, validar_data_iso

logger = obter_logger(__name__)


def _rotulo_tarefa(tarefa) -> str:
    """Formata uma linha da lista: ``[✔] descrição (vencimento)``."""
    _, descricao, vencimento, concluida, _ = tarefa
    marca = "[✔]" if concluida else "[  ]"
    sufixo = f"  ({formatar_data(vencimento)})" if vencimento else ""
    return f"{marca} {descricao}{sufixo}"


def criar_gerenciador_de_plugins(anfitriao=None) -> PluginManager:
    """Cria o PluginManager já ligado ao banco e aos serviços da aplicação."""
    return PluginManager(
        registro=RegistroEstadoBanco(),
        ui=anfitriao,
        tarefas=ServicoTarefasApp(),
    )


def criar_janela() -> tk.Tk:
    """Constrói a janela principal sem entrar no laço de eventos.

    Separado de :func:`iniciar_interface` para que os testes possam exercitar
    a interface real sem bloquear no ``mainloop``.
    """
    criar_tabela()
    restaurar_idioma_guardado()

    app = tk.Tk()
    app.title(carregar_texto("titulo"))
    app.geometry("800x600")

    # ------------------------------------------------------------ topo
    frame_topo = ttk.Frame(app)
    frame_topo.pack(pady=10)

    # Variável de idioma (mostra o rótulo, guarda o código)
    rotulos_idioma = {rotulo: codigo for codigo, rotulo in IDIOMAS_SUPORTADOS.items()}
    idioma_var = tk.StringVar(value=IDIOMAS_SUPORTADOS[idioma_atual()])

    label_titulo = ttk.Label(frame_topo, font=("Arial", 18))
    label_titulo.pack()

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
        """Relê o banco e repovoa a Listbox."""
        lista.delete(0, tk.END)
        ids_visiveis.clear()
        tarefas = buscar_tarefas()
        if not tarefas:
            lista.insert(tk.END, carregar_texto("sem_tarefas"))
            return
        for tarefa in tarefas:
            ids_visiveis.append(tarefa[0])
            lista.insert(tk.END, _rotulo_tarefa(tarefa))

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
        adicionar_tarefa(descricao, vencimento)
        entrada_descricao.delete(0, tk.END)
        entrada_data.delete(0, tk.END)
        recarregar_lista()

    def acao_concluir():
        tarefa_id = tarefa_selecionada()
        if tarefa_id is None:
            return
        atual = next((t for t in buscar_tarefas() if t[0] == tarefa_id), None)
        if atual is not None:
            concluir_tarefa(tarefa_id, not atual[3])
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
            remover_tarefa(tarefa_id)
            recarregar_lista()

    # ------------------------------------------------------------- plugins
    anfitriao = AnfitriaoGUI(notebook)
    gerenciador = criar_gerenciador_de_plugins(anfitriao)
    app.gerenciador_de_plugins = gerenciador  # facilita testes e depuração

    def abrir_plugins():
        JanelaPlugins(app, gerenciador)

    def arrancar_plugins():
        """Ativa os plugins deixados ligados, avisando sobre os que falharam."""
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
        barra.add_cascade(label=carregar_texto("configuracoes"), menu=configuracoes)
        app.config(menu=barra)

    def mudar_idioma():
        definir_idioma(rotulos_idioma[idioma_var.get()])
        atualizar_textos()

    def atualizar_textos():
        """Reaplica todos os textos visíveis conforme o idioma atual."""
        app.title(carregar_texto("titulo"))
        label_titulo.config(text=carregar_texto("titulo"))
        label_descricao.config(text=carregar_texto("descricao_tarefa"))
        label_data.config(text=carregar_texto("data_vencimento"))
        botao_adicionar.config(text=carregar_texto("adicionar"))
        botao_concluir.config(text=carregar_texto("concluir"))
        botao_remover.config(text=carregar_texto("remover"))
        botao_atualizar.config(text=carregar_texto("atualizar_lista"))
        notebook.tab(aba_tarefas, text=carregar_texto("tarefas"))
        anfitriao.atualizar_traducoes()
        construir_menu()
        recarregar_lista()

    def ao_fechar():
        """Encerra os plugins antes de fechar a janela."""
        try:
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
