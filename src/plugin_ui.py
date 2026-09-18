"""Integração do sistema de plugins com a interface gráfica.

Contém três peças:

* :class:`ServicoTarefasApp` — fachada estreita do banco entregue aos plugins;
* :class:`AnfitriaoGUI` — pontos de extensão da janela principal (abas);
* :class:`JanelaPlugins` — a tela *Configurações → Plugins*.

Toda a comunicação com o :class:`~core.plugin_manager.PluginManager` passa por
:class:`~core.plugin_manager.ResultadoOperacao`, cuja ``chave_mensagem`` é
traduzida aqui: o utilizador vê uma frase compreensível e os detalhes técnicos
ficam disponíveis num campo à parte (e sempre no log).
"""

from __future__ import annotations

from aparencia import fonte
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import tarefas_servico
from core.log import obter_logger
from core.plugin_api import EstadoPlugin
from core.plugin_manager import PluginManager, RegistroPlugin, ResultadoOperacao
from core.plugin_sources import FontePlugins
from language_manager import carregar_texto

logger = obter_logger(__name__)


# ------------------------------------------------------- serviços aos plugins


class ServicoTarefasApp:
    """Acesso às tarefas concedido aos plugins.

    Deliberadamente estreito: os plugins podem ler e criar tarefas, mas não
    apagar nem mexer no schema. Passa por :mod:`tarefas_servico`, para um
    plugin não conseguir ver o que a sessão não pode ver.
    """

    def listar(self, incluir_concluidas: bool = True) -> List[tuple]:
        """Tarefas visíveis para a sessão atual."""
        return tarefas_servico.listar(incluir_concluidas=incluir_concluidas)

    def listar_por_data(self, data_iso: str) -> List[tuple]:
        """Tarefas visíveis com vencimento na data indicada."""
        return tarefas_servico.listar_por_data(data_iso)

    def adicionar(self, descricao: str, data_vencimento: Optional[str] = None) -> int:
        """Cria uma tarefa em nome de quem está em sessão."""
        return tarefas_servico.adicionar(descricao, data_vencimento)


class AnfitriaoGUI:
    """Implementa os pontos de extensão da GUI oferecidos aos plugins.

    Args:
        notebook: o ``ttk.Notebook`` da janela principal.
    """

    def __init__(self, notebook: ttk.Notebook) -> None:
        self._notebook = notebook
        self._abas: Dict[str, List[ttk.Frame]] = {}
        self._titulos: Dict[ttk.Frame, Any] = {}

    @staticmethod
    def _resolver_titulo(titulo: Any) -> str:
        """Aceita um texto fixo ou uma função que devolve o texto traduzido."""
        if callable(titulo):
            try:
                return str(titulo())
            except Exception:  # pragma: no cover - defensivo
                logger.exception("Falha ao obter o título traduzido de uma aba.")
                return ""
        return str(titulo)

    def registrar_aba(
        self, plugin_id: str, titulo: Any, construtor: Callable[[Any], Any]
    ) -> None:
        """Adiciona à janela principal uma aba construída pelo plugin.

        ``construtor`` recebe o widget pai e devolve o widget da aba.
        ``titulo`` pode ser um texto fixo ou uma função sem argumentos — nesse
        caso é reavaliada sempre que o idioma muda. Uma exceção aqui propaga
        para o gerenciador, que marca o plugin como em erro sem afetar a
        aplicação.
        """
        moldura = ttk.Frame(self._notebook)
        conteudo = construtor(moldura)
        if isinstance(conteudo, (tk.Widget, ttk.Widget)) and conteudo.master is moldura:
            conteudo.pack(fill=tk.BOTH, expand=True)
        self._notebook.add(moldura, text=self._resolver_titulo(titulo))
        self._abas.setdefault(plugin_id, []).append(moldura)
        self._titulos[moldura] = titulo
        logger.info("Aba registada pelo plugin %s: %s", plugin_id, self._resolver_titulo(titulo))

    def atualizar_traducoes(self) -> None:
        """Reaplica os títulos das abas dos plugins no idioma atual."""
        for moldura, titulo in list(self._titulos.items()):
            try:
                self._notebook.tab(moldura, text=self._resolver_titulo(titulo))
            except tk.TclError:  # pragma: no cover - aba já removida
                self._titulos.pop(moldura, None)

    def remover_abas(self, plugin_id: str) -> None:
        """Remove todas as abas criadas por um plugin."""
        # A barra lateral e a paleta são limpas aqui, e não no gerenciador:
        # o núcleo não importa interface (ADR-0001), e este anfitrião é
        # precisamente a peça da interface que o núcleo já avisa quando um
        # plugin sai. Um destino de um plugin descarregado é um botão que
        # abre um painel destruído.
        from navegacao import comandos, registo

        registo.esquecer_por_dono(plugin_id)
        comandos.esquecer_por_dono(plugin_id)

        for moldura in self._abas.pop(plugin_id, []):
            self._titulos.pop(moldura, None)
            try:
                self._notebook.forget(moldura)
                moldura.destroy()
            except tk.TclError:  # pragma: no cover - aba já removida
                pass
        logger.info("Abas do plugin %s removidas.", plugin_id)

    def notificar(self, mensagem: str) -> None:
        """Mostra uma mensagem informativa ao utilizador."""
        messagebox.showinfo(carregar_texto("informacao"), mensagem)

    def tem_abas(self, plugin_id: str) -> bool:
        """``True`` se o plugin tem abas registadas."""
        return bool(self._abas.get(plugin_id))


# ------------------------------------------------------------- tela de plugins


def texto_estado(registro: RegistroPlugin) -> str:
    """Rótulo traduzido do estado de um plugin."""
    mapa = {
        EstadoPlugin.ATIVO: "plugin_estado_ativo",
        EstadoPlugin.CARREGADO: "plugin_estado_inativo",
        EstadoPlugin.INSTALADO: "plugin_estado_inativo",
        EstadoPlugin.INVALIDO: "plugin_estado_invalido",
        EstadoPlugin.INCOMPATIVEL: "plugin_estado_incompativel",
        EstadoPlugin.ERRO: "plugin_estado_erro",
        EstadoPlugin.DESCOBERTO: "plugin_estado_inativo",
    }
    return carregar_texto(mapa.get(registro.estado, "plugin_estado_inativo"))


def mensagem_resultado(resultado: ResultadoOperacao) -> str:
    """Traduz a chave de um resultado para uma frase amigável."""
    return carregar_texto(resultado.chave_mensagem)


def texto_permissoes(registro: RegistroPlugin) -> str:
    """O que o plugin pede, escrito para quem não programa.

    Um plugin que não pede nada diz isso mesmo — é informação, não ausência
    de informação.
    """
    manifesto = registro.manifesto
    pedidas = sorted(manifesto.permissoes, key=lambda p: p.value) if manifesto else []
    if not pedidas:
        return carregar_texto("plugin_sem_permissoes")
    return ", ".join(carregar_texto(f"permissao_{p.value}") for p in pedidas)


class JanelaPlugins(tk.Toplevel):
    """Tela *Configurações → Plugins*.

    Lista os plugins instalados com estado e ações (ativar, desativar,
    atualizar, remover) e permite instalar um novo a partir de um ``.zip``.

    Args:
        embutidos: fonte dos plugins que acompanham a aplicação. Quando é
            dada, a tela oferece a reposição — a saída para os casos que o
            arranque não pode resolver sozinho (ADR-0006).
    """

    def __init__(
        self,
        master: tk.Misc,
        gerenciador: PluginManager,
        embutidos: Optional[FontePlugins] = None,
    ) -> None:
        super().__init__(master)
        self._gerenciador = gerenciador
        self._embutidos = embutidos
        self.title(carregar_texto("plugins"))
        self.geometry("620x520")
        self.transient(master)

        cabecalho = ttk.Frame(self)
        cabecalho.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(
            cabecalho, text=carregar_texto("plugins"), font=fonte("subtitulo", negrito=True)
        ).pack(side=tk.LEFT)
        ttk.Button(
            cabecalho,
            text="+ " + carregar_texto("instalar_plugin"),
            command=self._instalar,
        ).pack(side=tk.RIGHT)
        if self._embutidos is not None:
            ttk.Button(
                cabecalho,
                text=carregar_texto("plugin_repor_embutidos"),
                command=self._repor_embutidos,
            ).pack(side=tk.RIGHT, padx=(0, 6))

        # Área rolável com um cartão por plugin.
        moldura = ttk.Frame(self)
        moldura.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        self._tela = tk.Canvas(moldura, borderwidth=0, highlightthickness=0)
        barra = ttk.Scrollbar(moldura, orient=tk.VERTICAL, command=self._tela.yview)
        self._lista = ttk.Frame(self._tela)
        self._lista.bind(
            "<Configure>",
            lambda _: self._tela.configure(scrollregion=self._tela.bbox("all")),
        )
        self._janela_interna = self._tela.create_window(
            (0, 0), window=self._lista, anchor="nw"
        )
        self._tela.bind(
            "<Configure>",
            lambda evento: self._tela.itemconfigure(self._janela_interna, width=evento.width),
        )
        self._tela.configure(yscrollcommand=barra.set)
        self._tela.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(self, text=carregar_texto("fechar"), command=self.destroy).pack(pady=(0, 10))

        self.recarregar()

    # ------------------------------------------------------------- desenho

    def recarregar(self) -> None:
        """Redescobre os plugins e redesenha a lista."""
        self._gerenciador.descobrir()
        for filho in self._lista.winfo_children():
            filho.destroy()

        registros = self._gerenciador.listar()
        if not registros:
            ttk.Label(self._lista, text=carregar_texto("plugin_nenhum")).pack(
                anchor=tk.W, pady=20
            )
            return

        for registro in registros:
            self._desenhar_cartao(registro)

    def _desenhar_cartao(self, registro: RegistroPlugin) -> None:
        cartao = ttk.LabelFrame(self._lista, text=f"{registro.nome}  v{registro.versao}")
        cartao.pack(fill=tk.X, expand=True, pady=6, padx=2)

        if registro.descricao:
            ttk.Label(cartao, text=registro.descricao, wraplength=520).pack(
                anchor=tk.W, padx=8, pady=(6, 0)
            )

        ttk.Label(
            cartao,
            text=f"{carregar_texto('plugin_status')}: {texto_estado(registro)}",
        ).pack(anchor=tk.W, padx=8, pady=(4, 0))

        ttk.Label(
            cartao,
            text=f"{carregar_texto('plugin_permissoes')}: {texto_permissoes(registro)}",
            wraplength=520,
        ).pack(anchor=tk.W, padx=8, pady=(2, 0))

        if registro.erro:
            ttk.Label(
                cartao,
                text=registro.erro,
                wraplength=520,
                foreground="#a33",
            ).pack(anchor=tk.W, padx=8, pady=(2, 0))

        acoes = ttk.Frame(cartao)
        acoes.pack(anchor=tk.W, padx=8, pady=8)

        utilizavel = registro.estado.utilizavel or registro.estado == EstadoPlugin.ERRO
        if registro.ativo:
            ttk.Button(
                acoes,
                text=carregar_texto("desativar"),
                command=lambda: self._desativar(registro.id),
            ).grid(row=0, column=0, padx=(0, 6))
        else:
            botao = ttk.Button(
                acoes,
                text=carregar_texto("ativar"),
                command=lambda: self._ativar(registro.id),
            )
            botao.grid(row=0, column=0, padx=(0, 6))
            if not utilizavel:
                botao.state(["disabled"])

        ttk.Button(
            acoes,
            text=carregar_texto("atualizar"),
            command=lambda: self._instalar(atualizar=registro.id),
        ).grid(row=0, column=1, padx=6)
        ttk.Button(
            acoes,
            text=carregar_texto("remover"),
            command=lambda: self._remover(registro),
        ).grid(row=0, column=2, padx=6)

    # -------------------------------------------------------------- ações

    def _ativar(self, plugin_id: str) -> None:
        resultado = self._gerenciador.ativar(plugin_id)
        if not resultado.sucesso:
            self._mostrar_erro(resultado)
        self.recarregar()

    def _desativar(self, plugin_id: str) -> None:
        resultado = self._gerenciador.desativar(plugin_id)
        if not resultado.sucesso:
            self._mostrar_erro(resultado)
        self.recarregar()

    def _instalar(self, atualizar: Optional[str] = None) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title=carregar_texto("atualizar_plugin" if atualizar else "instalar_plugin"),
            filetypes=[(carregar_texto("plugin_arquivo_zip"), "*.zip")],
        )
        if not caminho:
            return

        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            resultado = self._gerenciador.instalar_zip(Path(caminho))
        finally:
            self.configure(cursor="")

        if resultado.sucesso:
            if atualizar and resultado.plugin_id != atualizar:
                messagebox.showinfo(
                    carregar_texto("informacao"),
                    carregar_texto("plugin_outro_instalado", id=resultado.plugin_id or "?"),
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    carregar_texto("informacao"), mensagem_resultado(resultado), parent=self
                )
            self.recarregar()
            if resultado.plugin_id and self._perguntar_ativar(resultado.plugin_id):
                self._ativar(resultado.plugin_id)
        else:
            self._mostrar_erro(resultado)
            self.recarregar()

    def _perguntar_ativar(self, plugin_id: str) -> bool:
        registro = self._gerenciador.obter(plugin_id)
        if registro is None or registro.ativo or not registro.estado.utilizavel:
            return False
        # O acesso pedido aparece antes do "Sim", não depois: é o momento em
        # que a decisão ainda é do utilizador.
        pergunta = carregar_texto("plugin_ativar_agora", nome=registro.nome)
        pergunta += "\n\n" + carregar_texto(
            "plugin_ativar_acesso", acesso=texto_permissoes(registro)
        )
        return bool(
            messagebox.askyesno(
                carregar_texto("plugins"),
                pergunta,
                parent=self,
            )
        )

    def _repor_embutidos(self) -> None:
        """Volta a pôr os plugins que vieram com a aplicação.

        Existe porque a decisão do ADR-0006 deixa de propósito dois casos
        parados: um plugin embutido que alguém modificou à mão, e um que o
        utilizador substituiu pela sua própria versão. Nenhum dos dois pode
        ser resolvido pelo arranque sem desfazer uma escolha de alguém — mas
        ficar sem saída nenhuma seria pior, porque é assim que um plugin fica
        partido para sempre.

        Diz o que vai sobrepor antes de o fazer: quem carrega no botão deve
        saber o que está a perder.
        """
        if self._embutidos is None:  # pragma: no cover - o botão nem existe
            return

        retidos = self._gerenciador.retidos_da_fonte(self._embutidos)
        if not retidos:
            messagebox.showinfo(
                carregar_texto("informacao"),
                carregar_texto("plugin_repor_nada"),
                parent=self,
            )
            return

        nomes = ", ".join(
            (self._gerenciador.obter(pid).nome if self._gerenciador.obter(pid) else pid)
            for pid in retidos
        )
        if not messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("plugin_repor_confirmar", nomes=nomes),
            parent=self,
        ):
            return

        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            resultados = self._gerenciador.semear_de_fonte(self._embutidos, repor=True)
        finally:
            self.configure(cursor="")

        falhas = [r for r in resultados if not r.sucesso]
        if falhas:
            self._mostrar_erro(falhas[0])
        else:
            messagebox.showinfo(
                carregar_texto("informacao"),
                carregar_texto("plugin_repostos", quantos=len(resultados)),
                parent=self,
            )
        self.recarregar()

    def _remover(self, registro: RegistroPlugin) -> None:
        if not messagebox.askyesno(
            carregar_texto("confirmar"),
            carregar_texto("confirmar_remocao", item=registro.nome),
            parent=self,
        ):
            return

        remover_dados = bool(
            messagebox.askyesno(
                carregar_texto("plugins"),
                carregar_texto("plugin_remover_dados"),
                parent=self,
                default=messagebox.NO,
            )
        )
        resultado = self._gerenciador.remover(registro.id, remover_dados=remover_dados)
        if resultado.sucesso:
            messagebox.showinfo(
                carregar_texto("informacao"), mensagem_resultado(resultado), parent=self
            )
        else:
            self._mostrar_erro(resultado)
        self.recarregar()

    # -------------------------------------------------------------- erros

    def _mostrar_erro(self, resultado: ResultadoOperacao) -> None:
        """Apresenta uma mensagem amigável, com os detalhes técnicos abaixo."""
        texto = mensagem_resultado(resultado)
        if resultado.detalhes:
            texto = f"{texto}\n\n{carregar_texto('detalhes')}:\n{resultado.detalhes}"
        messagebox.showerror(carregar_texto("erro"), texto, parent=self)
