import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/users": "http://127.0.0.1:8000",
      "/sessions": "http://127.0.0.1:8000",
      "/simulations": "http://127.0.0.1:8000",
      "/scenarios": "http://127.0.0.1:8000",
      "/raw-documents": "http://127.0.0.1:8000",
      "/corpora": "http://127.0.0.1:8000",
      "/corpus-indices": "http://127.0.0.1:8000",
      "/indexing-jobs": "http://127.0.0.1:8000",
      "/prompts": "http://127.0.0.1:8000",
      "/counterpart-personas": "http://127.0.0.1:8000",
      "/embeddings": "http://127.0.0.1:8000",
      "/vector-stores": "http://127.0.0.1:8000",
      "/chunking-profiles": "http://127.0.0.1:8000"
    }
  }
});
