"""Verificação de atualizações.

Avisa quando existe uma versão mais recente e deixa a decisão ao utilizador.

Três regras que este plugin respeita, e que valem mais do que a comodidade:

1. **Não contacta a internet sem autorização.** Na primeira vez pergunta; a
   resposta fica guardada e pode ser mudada a qualquer momento na aba.
2. **Não descarrega nem executa nada.** Se o utilizador quiser atualizar, o
   plugin abre a página oficial da versão no navegador — quem instala é ele,
   a partir da fonte original. Um programa que se auto-atualiza em silêncio é
   um programa que executa o que lhe mandarem, se a fonte for comprometida.
3. **Nunca interrompe.** A verificação corre à parte da interface; falhar
   (sem rede, servidor em baixo) é silencioso, fica só no log.

A origem é configurável: por omissão usa a API de *releases* do GitHub do
projeto, mas aceita qualquer URL que devolva ``{"versao": ..., "notas": ...,
"url": ...}`` — o que permite a uma empresa apontar para o seu próprio
servidor.
"""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from tkinter import ttk
from typing import Any, Callable, Dict, Optional

from core.plugin_api import Plugin
from core.version import APP_URL, APP_VERSION, VersaoInvalidaError, comparar_versoes

#: Chaves da configuração do plugin.
CHAVE_CONSENTIMENTO = "verificar_online"
CHAVE_ULTIMA = "ultima_verificacao"
CHAVE_IGNORADA = "versao_ignorada"
CHAVE_ORIGEM = "origem"
CHAVE_AO_ARRANCAR = "verificar_ao_arrancar"

#: Onde procurar, por omissão: os *releases* do repositório do projeto.
ORIGEM_PADRAO = "https://api.github.com/repos/Raoc1987/gerenciador_de_tarefas/releases/latest"

TEMPO_LIMITE_SEGUNDOS = 8
AGENTE = f"GerenciadorDeTarefas/{APP_VERSION} (verificador de atualizações)"


@dataclass(frozen=True)
class Lancamento:
    """Uma versão publicada."""

    versao: str
    notas: str = ""
    url: str = ""
    publicado_em: str = ""

    def mais_recente_que(self, versao: str) -> bool:
        """Se esta versão é posterior à indicada."""
        try:
            return comparar_versoes(self.versao, versao) > 0
        except VersaoInvalidaError:
            return False


def _limpar_versao(texto: str) -> str:
    """``"v1.2.0"`` -> ``"1.2.0"``."""
    return (texto or "").strip().lstrip("vV").strip()


def interpretar(dados: Any) -> Optional[Lancamento]:
    """Lê a resposta da origem, seja o formato do GitHub ou um manifesto simples.

    Devolve ``None`` se a resposta não tiver uma versão reconhecível — uma
    página de erro em HTML ou um JSON de outra coisa não vira uma atualização.
    """
    if not isinstance(dados, dict):
        return None

    # Formato do GitHub: tag_name / body / html_url.
    if "tag_name" in dados:
        versao = _limpar_versao(str(dados.get("tag_name", "")))
        if not versao or dados.get("draft"):
            return None
        return Lancamento(
            versao=versao,
            notas=str(dados.get("body") or "").strip(),
            url=str(dados.get("html_url") or ""),
            publicado_em=str(dados.get("published_at") or "")[:10],
        )

    # Manifesto próprio.
    versao = _limpar_versao(str(dados.get("versao") or dados.get("version") or ""))
    if not versao:
        return None
    return Lancamento(
        versao=versao,
        notas=str(dados.get("notas") or dados.get("notes") or "").strip(),
        url=str(dados.get("url") or ""),
        publicado_em=str(dados.get("data") or dados.get("date") or "")[:10],
    )


def obter_json(url: str, tempo_limite: int = TEMPO_LIMITE_SEGUNDOS) -> Any:
    """Lê JSON de um URL.

    Raises:
        OSError: falha de rede, tempo esgotado ou resposta ilegível.
    """
    if not url.lower().startswith("https://"):
        raise OSError("A origem das atualizações tem de usar HTTPS.")

    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:  # noqa: S310
        bruto = resposta.read(512 * 1024)
    try:
        return json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise OSError(f"Resposta ilegível da origem: {erro}") from erro


class PainelAtualizacoes(ttk.Frame):
    """Aba com o estado, o botão de verificar e o consentimento."""

    def __init__(self, master: tk.Misc, plugin: "AtualizacoesPlugin") -> None:
        super().__init__(master, padding=16)
        self._plugin = plugin
        traduzir = plugin.contexto.traduzir

        ttk.Label(self, text=traduzir("titulo_aba"), font=("Arial", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self,
            text=traduzir("versao_atual", versao=APP_VERSION),
            foreground="#7a8794",
        ).pack(anchor=tk.W, pady=(4, 12))

        self._estado = ttk.Label(self, wraplength=560, justify=tk.LEFT)
        self._estado.pack(anchor=tk.W)

        self._notas = tk.Text(self, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self._notas.pack(fill=tk.BOTH, expand=True, pady=10)

        acoes = ttk.Frame(self)
        acoes.pack(fill=tk.X)
        self._botao_verificar = ttk.Button(
            acoes, text=traduzir("verificar_agora"), command=plugin.verificar_agora
        )
        self._botao_verificar.pack(side=tk.LEFT)

        self._botao_pagina = ttk.Button(
            acoes, text=traduzir("abrir_pagina"), command=plugin.abrir_pagina
        )
        self._botao_pagina.pack(side=tk.LEFT, padx=8)
        self._botao_pagina.state(["disabled"])

        self._consentimento = tk.BooleanVar(value=plugin.consentiu())
        ttk.Checkbutton(
            self,
            text=traduzir("permitir_verificacao"),
            variable=self._consentimento,
            command=lambda: plugin.definir_consentimento(self._consentimento.get()),
        ).pack(anchor=tk.W, pady=(12, 0))

        self._ao_arrancar = tk.BooleanVar(value=plugin.verifica_ao_arrancar())
        ttk.Checkbutton(
            self,
            text=traduzir("verificar_ao_arrancar"),
            variable=self._ao_arrancar,
            command=lambda: plugin.definir_verificar_ao_arrancar(self._ao_arrancar.get()),
        ).pack(anchor=tk.W)

        self.mostrar_estado()

    def mostrar_estado(self, mensagem: str = "") -> None:
        """Atualiza a linha de estado e a caixa de notas."""
        traduzir = self._plugin.contexto.traduzir
        if mensagem:
            texto = mensagem
        else:
            ultima = self._plugin.ultima_verificacao()
            texto = (
                traduzir("ultima_verificacao", quando=ultima)
                if ultima
                else traduzir("nunca_verificado")
            )
        self._estado.config(text=texto)

        lancamento = self._plugin.ultimo_lancamento
        self._notas.config(state=tk.NORMAL)
        self._notas.delete("1.0", tk.END)
        if lancamento and lancamento.notas:
            self._notas.insert("1.0", lancamento.notas)
        self._notas.config(state=tk.DISABLED)

        if lancamento and lancamento.url:
            self._botao_pagina.state(["!disabled"])
        else:
            self._botao_pagina.state(["disabled"])

    def ocupado(self, ocupado: bool) -> None:
        """Desativa o botão enquanto a verificação corre."""
        estado = ["disabled"] if ocupado else ["!disabled"]
        try:
            self._botao_verificar.state(estado)
        except tk.TclError:  # pragma: no cover - aba já fechada
            pass


class AtualizacoesPlugin(Plugin):
    """Verifica se existe uma versão mais recente e pergunta ao utilizador."""

    #: De quanto em quanto tempo o laço do Tk vai ver se a resposta chegou.
    INTERVALO_DE_SONDAGEM_MS = 150

    def __init__(self, contexto) -> None:
        super().__init__(contexto)
        self._painel: Optional[PainelAtualizacoes] = None
        self._resultados: "queue.Queue" = queue.Queue()
        self.ultimo_lancamento: Optional[Lancamento] = None
        #: Injetável nos testes, para não haver rede durante a suíte.
        self.buscar: Callable[[str], Any] = obter_json

    # ------------------------------------------------------- configuração

    def _config(self) -> Dict[str, Any]:
        return self.contexto.config()

    def _guardar(self, **valores) -> None:
        config = self._config()
        config.update(valores)
        self.contexto.guardar_config(config)

    def consentiu(self) -> bool:
        """Se o utilizador autorizou contactar a origem das atualizações."""
        return bool(self._config().get(CHAVE_CONSENTIMENTO, False))

    def definir_consentimento(self, autorizado: bool) -> None:
        """Guarda a autorização (ou a retirada dela)."""
        self._guardar(**{CHAVE_CONSENTIMENTO: bool(autorizado)})
        self.contexto.logger.info(
            "Verificação de atualizações %s pelo utilizador.",
            "autorizada" if autorizado else "desautorizada",
        )

    def verifica_ao_arrancar(self) -> bool:
        """Se deve verificar sozinho quando a aplicação abre."""
        return bool(self._config().get(CHAVE_AO_ARRANCAR, True))

    def definir_verificar_ao_arrancar(self, ativo: bool) -> None:
        """Liga ou desliga a verificação automática."""
        self._guardar(**{CHAVE_AO_ARRANCAR: bool(ativo)})

    def origem(self) -> str:
        """URL consultado (configurável para apontar a outro servidor)."""
        return str(self._config().get(CHAVE_ORIGEM) or ORIGEM_PADRAO)

    def ultima_verificacao(self) -> str:
        """Quando foi a última verificação, em texto legível."""
        bruto = self._config().get(CHAVE_ULTIMA)
        return str(bruto).replace("T", " ") if bruto else ""

    def versao_ignorada(self) -> str:
        """Versão que o utilizador pediu para não voltar a ser avisada."""
        return str(self._config().get(CHAVE_IGNORADA) or "")

    # -------------------------------------------------------- ciclo de vida

    def ativar(self) -> None:
        if self.contexto.ui is None:
            return
        self.contexto.ui.registrar_aba(
            self.id, lambda: self.contexto.traduzir("aba"), self._construir_painel
        )
        if self.consentiu() and self.verifica_ao_arrancar():
            # Adiada: o arranque da aplicação não espera pela rede.
            self._agendar(3000, lambda: self.verificar(silencioso=True))
        elif not self.consentiu():
            self._agendar(1500, self._pedir_consentimento)

    def desativar(self) -> None:
        self._painel = None

    def _construir_painel(self, pai):
        self._painel = PainelAtualizacoes(pai, self)
        return self._painel

    def _agendar(self, atraso_ms: int, funcao) -> None:
        if self._painel is None:
            return
        try:
            self._painel.after(atraso_ms, funcao)
        except tk.TclError:  # pragma: no cover - aba fechada entretanto
            pass

    # ------------------------------------------------------------ verificação

    def _pedir_consentimento(self) -> None:
        """Pergunta uma vez se pode consultar a origem das atualizações."""
        from tkinter import messagebox

        if self._painel is None:
            return
        traduzir = self.contexto.traduzir
        autorizado = messagebox.askyesno(
            traduzir("aba"),
            traduzir("pedir_consentimento", origem=self.origem()),
            parent=self._painel,
        )
        self.definir_consentimento(bool(autorizado))
        if autorizado:
            self.verificar(silencioso=True)
        else:
            self._painel.mostrar_estado(traduzir("verificacao_desligada"))

    def verificar_agora(self) -> None:
        """Verificação pedida pelo utilizador (mostra sempre o resultado)."""
        if not self.consentiu():
            self._pedir_consentimento()
            return
        self.verificar(silencioso=False)

    def _consultar(self, origem: str):
        """Vai buscar e interpretar. Devolve ``(lançamento, erro)``."""
        try:
            return interpretar(self.buscar(origem)), None
        except Exception as falha:  # rede, tempo esgotado, resposta má
            return None, falha

    def verificar(self, silencioso: bool = True) -> None:
        """Consulta a origem sem bloquear a interface.

        O trabalho de rede corre noutra linha de execução, mas **só o laço
        principal toca no Tk**: a resposta é deixada numa fila e recolhida por
        uma sondagem agendada com ``after``. Chamar widgets a partir de outra
        linha de execução parece funcionar e falha quando menos convém.
        """
        if not self.consentiu():
            self.contexto.logger.info("Verificação pedida sem autorização; ignorada.")
            return

        origem = self.origem()

        if self._painel is None:
            # Sem interface (testes, arranque sem aba): não há nada a bloquear.
            lancamento, erro = self._consultar(origem)
            self._concluir(lancamento, erro, silencioso)
            return

        self._painel.ocupado(True)
        self._painel.mostrar_estado(self.contexto.traduzir("a_verificar"))

        threading.Thread(
            target=lambda: self._resultados.put(self._consultar(origem)),
            daemon=True,
            name="verificar-atualizacoes",
        ).start()
        self._sondar(silencioso)

    def _sondar(self, silencioso: bool) -> None:
        """Vê se a resposta já chegou; se não, volta a tentar mais tarde."""
        if self._painel is None:
            return
        try:
            lancamento, erro = self._resultados.get_nowait()
        except queue.Empty:
            try:
                self._painel.after(
                    self.INTERVALO_DE_SONDAGEM_MS, lambda: self._sondar(silencioso)
                )
            except tk.TclError:  # pragma: no cover - aba fechada entretanto
                pass
            return
        self._concluir(lancamento, erro, silencioso)

    def _concluir(self, lancamento: Optional[Lancamento], erro, silencioso: bool) -> None:
        traduzir = self.contexto.traduzir
        self._guardar(**{CHAVE_ULTIMA: datetime.now().isoformat(timespec="minutes")})

        if self._painel is not None:
            self._painel.ocupado(False)

        if erro is not None:
            self.contexto.logger.info("Verificação de atualizações falhou: %s", erro)
            if self._painel is not None:
                self._painel.mostrar_estado(traduzir("falha_ao_verificar"))
            return

        if lancamento is None:
            if self._painel is not None:
                self._painel.mostrar_estado(traduzir("resposta_inesperada"))
            return

        self.ultimo_lancamento = lancamento
        self.contexto.publicar(
            "atualizacoes.verificada", versao=lancamento.versao, atual=APP_VERSION
        )

        if not lancamento.mais_recente_que(APP_VERSION):
            if self._painel is not None:
                self._painel.mostrar_estado(traduzir("esta_atualizado", versao=APP_VERSION))
            return

        if self._painel is not None:
            self._painel.mostrar_estado(
                traduzir("ha_novidade", versao=lancamento.versao, atual=APP_VERSION)
            )
        self.contexto.publicar("atualizacoes.disponivel", versao=lancamento.versao)

        if silencioso and lancamento.versao == self.versao_ignorada():
            self.contexto.logger.info("Versão %s ignorada pelo utilizador.", lancamento.versao)
            return

        self._propor(lancamento)

    def _propor(self, lancamento: Lancamento) -> None:
        """Mostra a novidade e deixa o utilizador decidir."""
        from tkinter import messagebox

        if self._painel is None:
            return
        traduzir = self.contexto.traduzir
        notas = lancamento.notas.strip()
        if len(notas) > 600:
            notas = notas[:600].rsplit("\n", 1)[0] + "\n…"

        mensagem = traduzir(
            "proposta",
            versao=lancamento.versao,
            atual=APP_VERSION,
            notas=notas or traduzir("sem_notas"),
        )
        if messagebox.askyesno(traduzir("aba"), mensagem, parent=self._painel):
            self.abrir_pagina()
        else:
            self._guardar(**{CHAVE_IGNORADA: lancamento.versao})
            self._painel.mostrar_estado(traduzir("adiado", versao=lancamento.versao))

    def abrir_pagina(self) -> bool:
        """Abre no navegador a página oficial da versão.

        O plugin nunca descarrega nem executa o instalador: quem o faz é o
        utilizador, a partir da página oficial.
        """
        destino = (self.ultimo_lancamento.url if self.ultimo_lancamento else "") or APP_URL
        if not destino.lower().startswith("https://"):
            self.contexto.logger.warning("Destino recusado (não é HTTPS): %s", destino)
            return False
        self.contexto.logger.info("A abrir a página da versão: %s", destino)
        webbrowser.open(destino)
        self.contexto.publicar("atualizacoes.pagina_aberta", url=destino)
        return True
