import { readdirSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// 01-xxx/index.html のようなフォルダをすべてページとして扱う
const pages = Object.fromEntries(
  readdirSync(__dirname)
    .filter((name) => /^\d\d-/.test(name) && existsSync(resolve(__dirname, name, "index.html")))
    .map((name) => [name, resolve(__dirname, name, "index.html")]),
);

// API は uvicorn (127.0.0.1:8000) に転送する
const api = { target: "http://127.0.0.1:8000", changeOrigin: true };

export default defineConfig({
  plugins: [tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/search": api, "/library": api, "/catalog": api, "/taste": api },
  },
  build: { rollupOptions: { input: { index: resolve(__dirname, "index.html"), ...pages } } },
});
