// As rotas do Supabase (/auth/v1 → GoTrue, /rest/v1 → PostgREST) numa só
// porta, como o Kong do Supabase faz. Só em 127.0.0.1, só para os testes.
import http from "node:http";

const alvos = { "/auth/v1": 9999, "/rest/v1": 3001 };
const porta = Number(process.env.PORTA_API ?? 54321);

http
  .createServer((req, res) => {
    const cors = {
      "access-control-allow-origin": req.headers.origin ?? "*",
      "access-control-allow-credentials": "true",
      "access-control-allow-headers": "*",
      "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
    };
    if (req.method === "OPTIONS") {
      res.writeHead(204, cors);
      return res.end();
    }
    const prefixo = Object.keys(alvos).find((p) => req.url.startsWith(p));
    if (!prefixo) {
      res.writeHead(404, cors);
      return res.end();
    }
    const pedido = http.request(
      { host: "127.0.0.1", port: alvos[prefixo], path: req.url.slice(prefixo.length) || "/", method: req.method, headers: { ...req.headers, host: "127.0.0.1" } },
      (r) => {
        res.writeHead(r.statusCode, { ...r.headers, ...cors });
        r.pipe(res);
      },
    );
    pedido.on("error", (e) => {
      res.writeHead(502, cors);
      res.end(String(e));
    });
    req.pipe(pedido);
  })
  .listen(porta, "127.0.0.1");
