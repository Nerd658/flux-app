import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En-têtes de sécurité appliqués au build servi (vite preview) ; en prod, les reprendre sur le reverse proxy
const securityHeaders = {
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; " +
    "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
};

const backend = { target: "http://127.0.0.1:8000", changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  // Proxy /api -> FastAPI : même origine pour le navigateur, cookies SameSite=Strict fonctionnels
  server: { port: 5173, strictPort: true, proxy: { "/api": backend } },
  preview: { port: 5173, strictPort: true, proxy: { "/api": backend }, headers: securityHeaders },
  build: { sourcemap: false }, // pas de sources exposées en production
});
