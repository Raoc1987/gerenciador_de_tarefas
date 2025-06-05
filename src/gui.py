import tkinter as tk
from tkinter import ttk
from datetime import datetime
from database import criar_tabela, buscar_tarefas
from language_manager import carregar_texto, definir_idioma
def iniciar_interface():
    criar_tabela()

    app = tk.Tk()
    app.title("Gerenciador de Tarefas")
    app.geometry("800x600")

    # Frame do topo
    frame_topo = ttk.Frame(app)
    frame_topo.pack(pady=10)

    # Variável de idioma
    idioma_var = tk.StringVar(value="pt")

    # Label do título (atualizável)
    label_titulo = ttk.Label(frame_topo, font=("Arial", 18))
    label_titulo.pack()

    # Dropdown de idiomas
    def mudar_idioma(*args):
        idioma = idioma_var.get()
        definir_idioma(idioma)
        atualizar_textos()

    idiomas = {
        "Português 🇧🇷": "pt",
        "Inglês 🇺🇸": "en",
        "Espanhol 🇪🇸": "es"
    }

    dropdown = ttk.OptionMenu(
        frame_topo, idioma_var,
        "Português 🇧🇷",
        *idiomas.keys(),
        command=lambda _: mudar_idioma()
    )
    dropdown.pack(pady=5)

    # Lista de tarefas
    lista = tk.Listbox(app, width=80, height=15)
    lista.pack(pady=10)

    for tarefa in buscar_tarefas():
        lista.insert(tk.END, tarefa[1])

    # Relógio
    rodape = ttk.Label(app, font=("Arial", 10))
    rodape.pack(side=tk.BOTTOM, pady=5)
    atualizar_relógio(rodape) # type: ignore

    # Atualiza os textos conforme idioma
    def atualizar_textos():
        idioma_selecionado = idiomas[idioma_var.get()]
        definir_idioma(idioma_selecionado)
        label_titulo.config(text=carregar_texto("titulo"))
        app.title(carregar_texto("titulo"))

    atualizar_textos()
    app.mainloop()
