// ZIP mínimo, sem compressão (método "store"). Um .xlsx é um ZIP, e o Excel,
// o LibreOffice e o Numbers aceitam entradas guardadas sem compressão. Sem
// dependências e sem esperar por streams de compressão.

const TABELA_CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(dados: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < dados.length; i++) c = TABELA_CRC[(c ^ dados[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export function criarZip(entradas: { nome: string; dados: Uint8Array }[]): Uint8Array {
  const enc = new TextEncoder();
  const locais: Uint8Array[] = [];
  const centrais: Uint8Array[] = [];
  let deslocamento = 0;
  // Data fixa (1980-01-01): o mesmo conteúdo dá sempre o mesmo ficheiro.
  const hora = 0;
  const data = (0 << 9) | (1 << 5) | 1;

  for (const e of entradas) {
    const nome = enc.encode(e.nome);
    const crc = crc32(e.dados);
    const local = new Uint8Array(30 + nome.length);
    const v = new DataView(local.buffer);
    v.setUint32(0, 0x04034b50, true);
    v.setUint16(4, 20, true);
    v.setUint16(6, 0x0800, true); // nomes em UTF-8
    v.setUint16(8, 0, true);
    v.setUint16(10, hora, true);
    v.setUint16(12, data, true);
    v.setUint32(14, crc, true);
    v.setUint32(18, e.dados.length, true);
    v.setUint32(22, e.dados.length, true);
    v.setUint16(26, nome.length, true);
    v.setUint16(28, 0, true);
    local.set(nome, 30);

    const central = new Uint8Array(46 + nome.length);
    const c = new DataView(central.buffer);
    c.setUint32(0, 0x02014b50, true);
    c.setUint16(4, 20, true);
    c.setUint16(6, 20, true);
    c.setUint16(8, 0x0800, true);
    c.setUint16(10, 0, true);
    c.setUint16(12, hora, true);
    c.setUint16(14, data, true);
    c.setUint32(16, crc, true);
    c.setUint32(20, e.dados.length, true);
    c.setUint32(24, e.dados.length, true);
    c.setUint16(28, nome.length, true);
    c.setUint32(42, deslocamento, true);
    central.set(nome, 46);

    locais.push(local, e.dados);
    centrais.push(central);
    deslocamento += local.length + e.dados.length;
  }

  const tamCentral = centrais.reduce((s, x) => s + x.length, 0);
  const fim = new Uint8Array(22);
  const f = new DataView(fim.buffer);
  f.setUint32(0, 0x06054b50, true);
  f.setUint16(8, entradas.length, true);
  f.setUint16(10, entradas.length, true);
  f.setUint32(12, tamCentral, true);
  f.setUint32(16, deslocamento, true);

  const partes = [...locais, ...centrais, fim];
  const out = new Uint8Array(partes.reduce((s, x) => s + x.length, 0));
  let p = 0;
  for (const x of partes) {
    out.set(x, p);
    p += x.length;
  }
  return out;
}
