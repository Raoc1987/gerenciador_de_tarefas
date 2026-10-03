"use client";

import { useActionState, useEffect } from "react";
import {
  ESTADOS, PRIORIDADES, ROTULO_ESTADO, ROTULO_PRIORIDADE, type Tarefa,
} from "@/lib/dominio/tarefas";
import { criarTarefa, editarTarefa, type EstadoFormulario } from "./acoes";
import { Aviso, Botao, Campo, classeEntrada } from "@/components/ui";

export interface Pessoa {
  id: string;
  nome: string;
}

/**
 * O mesmo formulário cria e edita. Sem `tarefa`, cria.
 *
 * Quem não pode atribuir (colaborador) só vê "Eu" e "Ninguém" no
 * responsável — e, se a tarefa já estiver com outra pessoa, essa opção
 * aparece também, para gravar sem a mudar.
 */
export function FormularioTarefa({
  empresaId,
  tarefa,
  pessoas,
  eu,
  podeAtribuir,
  aoConcluir,
  aoCancelar,
}: {
  empresaId: string;
  tarefa?: Tarefa;
  pessoas: Pessoa[];
  eu: string;
  podeAtribuir: boolean;
  aoConcluir?: () => void;
  aoCancelar?: () => void;
}) {
  const acao = tarefa ? editarTarefa.bind(null, empresaId, tarefa.id) : criarTarefa.bind(null, empresaId);
  const [estado, submeter, aEnviar] = useActionState<EstadoFormulario, FormData>(acao, {});

  useEffect(() => {
    if (estado.ok) aoConcluir?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estado]);

  const opcoesResponsavel = podeAtribuir
    ? pessoas
    : pessoas.filter((p) => p.id === eu || p.id === tarefa?.responsavel_id);

  return (
    <form action={submeter} className="space-y-4" key={tarefa?.atualizada_em ?? "nova"}>
      <Campo rotulo="Título" erro={estado.erros?.titulo}>
        <input name="titulo" required maxLength={200} defaultValue={tarefa?.titulo} autoFocus className={classeEntrada} />
      </Campo>
      <Campo rotulo="Descrição" erro={estado.erros?.descricao}>
        <textarea name="descricao" rows={4} maxLength={10000} defaultValue={tarefa?.descricao} className={classeEntrada} />
      </Campo>
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo rotulo="Estado" erro={estado.erros?.estado}>
          <select name="estado" defaultValue={tarefa?.estado ?? "a_fazer"} className={classeEntrada}>
            {ESTADOS.map((e) => <option key={e} value={e}>{ROTULO_ESTADO[e]}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Prioridade" erro={estado.erros?.prioridade}>
          <select name="prioridade" defaultValue={tarefa?.prioridade ?? "media"} className={classeEntrada}>
            {PRIORIDADES.map((p) => <option key={p} value={p}>{ROTULO_PRIORIDADE[p]}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Prazo" erro={estado.erros?.prazo}>
          <input name="prazo" type="date" defaultValue={tarefa?.prazo ?? ""} className={classeEntrada} />
        </Campo>
        <Campo rotulo="Responsável" erro={estado.erros?.responsavel_id}>
          <select name="responsavel_id" defaultValue={tarefa ? tarefa.responsavel_id ?? "" : podeAtribuir ? "" : eu} className={classeEntrada}>
            <option value="">Ninguém</option>
            {opcoesResponsavel.map((p) => (
              <option key={p.id} value={p.id}>{p.id === eu ? `${p.nome} (eu)` : p.nome}</option>
            ))}
          </select>
        </Campo>
      </div>
      <Campo rotulo="Etiquetas" ajuda="Separadas por vírgulas. Ex.: cliente, financeiro" erro={estado.erros?.etiquetas}>
        <input name="etiquetas" defaultValue={tarefa?.etiquetas.join(", ")} className={classeEntrada} />
      </Campo>

      <Aviso>{estado.erro}</Aviso>
      {tarefa && estado.ok && <Aviso tom="sucesso">Alterações gravadas.</Aviso>}

      <div className="flex justify-end gap-2">
        {aoCancelar && (
          <Botao type="button" variante="secundario" onClick={aoCancelar}>
            Cancelar
          </Botao>
        )}
        <Botao type="submit" disabled={aEnviar}>
          {aEnviar ? "A gravar…" : tarefa ? "Gravar" : "Criar tarefa"}
        </Botao>
      </div>
    </form>
  );
}
