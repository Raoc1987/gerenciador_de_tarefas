// Leitor mínimo de ficheiros SQLite: só lê tabelas, do princípio ao fim.
//
// Existe para a importação do desktop correr no browser. O ficheiro
// tarefas.db pode ter dezenas de MB (a auditoria cresce), e mandá-lo inteiro
// ao servidor esbarrava no limite de tamanho dos pedidos; lido aqui, só
// seguem as tarefas. Sem dependências: o formato está documentado em
// https://www.sqlite.org/fileformat2.html e esta é a parte de que precisamos —
// árvores B de tabela, páginas de overflow e o formato de registo.
//
// Não lê índices, tabelas WITHOUT ROWID nem ficheiros com WAL por aplicar
// (o desktop não usa WAL).

export type Valor = null | number | string | Uint8Array;

export class ErroSqlite extends Error {}

export class LeitorSqlite {
  private readonly bytes: Uint8Array;
  private readonly dv: DataView;
  private readonly paginaTam: number;
  private readonly util: number;
  private readonly texto = new TextDecoder("utf-8");

  constructor(bytes: Uint8Array) {
    this.bytes = bytes;
    const assinatura = new TextDecoder("latin1").decode(bytes.subarray(0, 16));
    if (bytes.length < 512 || assinatura !== "SQLite format 3\u0000") {
      throw new ErroSqlite("Isto não é uma base de dados SQLite.");
    }
    this.dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const tam = this.dv.getUint16(16);
    this.paginaTam = tam === 1 ? 65536 : tam;
    this.util = this.paginaTam - bytes[20];
    if (this.dv.getUint32(56) !== 1 && this.dv.getUint32(56) !== 0) {
      throw new ErroSqlite("Só se leem bases em UTF-8.");
    }
    if (bytes[18] === 2 || bytes[19] === 2) {
      // Modo WAL: o que está no ficheiro -wal não estaria aqui.
      throw new ErroSqlite("A base está em modo WAL; feche a aplicação de secretária e tente de novo.");
    }
  }

  private inicioPagina(n: number): number {
    if (n < 1 || n * this.paginaTam > this.bytes.length) throw new ErroSqlite(`Página ${n} fora do ficheiro.`);
    return (n - 1) * this.paginaTam;
  }

  private varint(pos: number): [number, number] {
    let v = 0;
    for (let i = 0; i < 8; i++) {
      const b = this.bytes[pos + i];
      v = v * 128 + (b & 0x7f);
      if (b < 0x80) return [v, i + 1];
    }
    return [v * 256 + this.bytes[pos + 8], 9];
  }

  /** Percorre a árvore B de uma tabela e devolve [rowid, registo] por ordem. */
  *linhas(raiz: number): Generator<[number, Valor[]]> {
    const pilha = [raiz];
    const vistas = new Set<number>();
    // Em-ordem com pilha explícita: filhos da direita entram primeiro.
    while (pilha.length) {
      const pagina = pilha.pop()!;
      if (vistas.has(pagina)) throw new ErroSqlite("Árvore com ciclos: ficheiro corrompido.");
      vistas.add(pagina);
      const base = this.inicioPagina(pagina);
      const cab = base + (pagina === 1 ? 100 : 0);
      const tipo = this.bytes[cab];
      const n = this.dv.getUint16(cab + 3);
      if (tipo === 0x05) {
        const filhos: number[] = [];
        for (let i = 0; i < n; i++) {
          const celula = base + this.dv.getUint16(cab + 12 + i * 2);
          filhos.push(this.dv.getUint32(celula));
        }
        filhos.push(this.dv.getUint32(cab + 8));
        for (let i = filhos.length - 1; i >= 0; i--) pilha.push(filhos[i]);
      } else if (tipo === 0x0d) {
        for (let i = 0; i < n; i++) {
          let p = base + this.dv.getUint16(cab + 8 + i * 2);
          const [tamanho, a] = this.varint(p);
          p += a;
          const [rowid, b] = this.varint(p);
          p += b;
          yield [rowid, this.registo(this.carga(p, tamanho))];
        }
      } else {
        throw new ErroSqlite(`Página ${pagina} não é de tabela (tipo ${tipo}).`);
      }
    }
  }

  /** A carga de uma célula de folha, juntando as páginas de overflow. */
  private carga(pos: number, total: number): Uint8Array {
    const U = this.util;
    const X = U - 35;
    if (total <= X) return this.bytes.subarray(pos, pos + total);
    const M = Math.floor(((U - 12) * 32) / 255) - 23;
    const K = M + ((total - M) % (U - 4));
    const local = K <= X ? K : M;
    const out = new Uint8Array(total);
    out.set(this.bytes.subarray(pos, pos + local), 0);
    let feito = local;
    let seguinte = this.dv.getUint32(pos + local);
    let saltos = 0;
    while (feito < total) {
      if (!seguinte || ++saltos > 1_000_000) throw new ErroSqlite("Overflow incompleto: ficheiro corrompido.");
      const base = this.inicioPagina(seguinte);
      const n = Math.min(U - 4, total - feito);
      out.set(this.bytes.subarray(base + 4, base + 4 + n), feito);
      feito += n;
      seguinte = this.dv.getUint32(base);
    }
    return out;
  }

  private registo(c: Uint8Array): Valor[] {
    const dv = new DataView(c.buffer, c.byteOffset, c.byteLength);
    const vi = (pos: number): [number, number] => {
      let v = 0;
      for (let i = 0; i < 8; i++) {
        const b = c[pos + i];
        v = v * 128 + (b & 0x7f);
        if (b < 0x80) return [v, i + 1];
      }
      return [v * 256 + c[pos + 8], 9];
    };
    const [cabTam, n0] = vi(0);
    const tipos: number[] = [];
    for (let p = n0; p < cabTam; ) {
      const [t, n] = vi(p);
      tipos.push(t);
      p += n;
    }
    const valores: Valor[] = [];
    let p = cabTam;
    // Inteiro big-endian com sinal (complemento para dois), até 6 bytes.
    const int = (n: number) => {
      let u = 0;
      for (let i = 0; i < n; i++) u = u * 256 + c[p + i];
      const max = 2 ** (8 * n);
      p += n;
      return u >= max / 2 ? u - max : u;
    };
    for (const t of tipos) {
      if (t === 0) valores.push(null);
      else if (t >= 1 && t <= 4) valores.push(int([0, 1, 2, 3, 4][t]));
      else if (t === 5) valores.push(int(6));
      else if (t === 6) {
        valores.push(Number(dv.getBigInt64(p)));
        p += 8;
      } else if (t === 7) {
        valores.push(dv.getFloat64(p));
        p += 8;
      } else if (t === 8) valores.push(0);
      else if (t === 9) valores.push(1);
      else if (t >= 12 && t % 2 === 0) {
        const n = (t - 12) / 2;
        valores.push(c.slice(p, p + n));
        p += n;
      } else if (t >= 13) {
        const n = (t - 13) / 2;
        valores.push(this.texto.decode(c.subarray(p, p + n)));
        p += n;
      } else throw new ErroSqlite(`Tipo de valor desconhecido: ${t}.`);
    }
    return valores;
  }

  /** As tabelas do ficheiro: nome, página raiz e colunas (de sqlite_schema). */
  tabelas(): Map<string, { raiz: number; colunas: string[]; aliasRowid: number }> {
    const out = new Map<string, { raiz: number; colunas: string[]; aliasRowid: number }>();
    for (const [, [tipo, nome, , raiz, sql]] of this.linhas(1)) {
      if (tipo !== "table" || typeof nome !== "string" || typeof raiz !== "number" || typeof sql !== "string") continue;
      const { colunas, aliasRowid } = colunasDe(sql);
      out.set(nome.toLowerCase(), { raiz, colunas, aliasRowid });
    }
    return out;
  }

  /** As linhas de uma tabela como objetos coluna → valor. */
  *objetos(tabela: string): Generator<Record<string, Valor>> {
    const t = this.tabelas().get(tabela.toLowerCase());
    if (!t) throw new ErroSqlite(`A tabela "${tabela}" não existe neste ficheiro.`);
    for (const [rowid, valores] of this.linhas(t.raiz)) {
      const o: Record<string, Valor> = {};
      t.colunas.forEach((c, i) => {
        // Uma coluna INTEGER PRIMARY KEY é o próprio rowid e vem NULL no registo.
        o[c] = i === t.aliasRowid ? rowid : (valores[i] ?? null);
      });
      yield o;
    }
  }
}

const RESTRICOES = /^(constraint|primary|unique|check|foreign)\b/i;

/** Nomes das colunas a partir do CREATE TABLE (o SQLite reescreve-o nos ALTER TABLE ADD COLUMN). */
export function colunasDe(sql: string): { colunas: string[]; aliasRowid: number } {
  const ini = sql.indexOf("(");
  const fim = sql.lastIndexOf(")");
  if (ini < 0 || fim < ini) return { colunas: [], aliasRowid: -1 };
  const corpo = sql.slice(ini + 1, fim);
  const partes: string[] = [];
  let nivel = 0;
  let atual = "";
  let aspas: string | null = null;
  for (const ch of corpo) {
    if (aspas) {
      if (ch === aspas) aspas = null;
    } else if (ch === "'" || ch === '"' || ch === "`" || ch === "[") {
      aspas = ch === "[" ? "]" : ch;
    } else if (ch === "(") nivel++;
    else if (ch === ")") nivel--;
    else if (ch === "," && nivel === 0) {
      partes.push(atual);
      atual = "";
      continue;
    }
    atual += ch;
  }
  partes.push(atual);
  const colunas: string[] = [];
  let aliasRowid = -1;
  for (const parte of partes.map((p) => p.trim()).filter(Boolean)) {
    if (RESTRICOES.test(parte)) continue;
    const m = parte.match(/^("([^"]+)"|`([^`]+)`|\[([^\]]+)\]|(\S+))\s*(.*)$/s);
    if (!m) continue;
    const nome = (m[2] ?? m[3] ?? m[4] ?? m[5]).toLowerCase();
    if (/^integer\s+primary\s+key\b/i.test(m[6].trim())) aliasRowid = colunas.length;
    colunas.push(nome);
  }
  return { colunas, aliasRowid };
}
