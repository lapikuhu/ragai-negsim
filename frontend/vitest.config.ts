import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  define: {
    "import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://localhost")
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "src")
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"]
  }
});
