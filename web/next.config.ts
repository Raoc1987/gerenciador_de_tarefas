import type { NextConfig } from "next";

const config: NextConfig = {
  // Cabeçalhos de segurança em todas as respostas. A CSP fica para quando
  // houver um domínio fixo — com o Supabase em URL variável, uma CSP mal
  // escrita parte o login em vez de o proteger.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
