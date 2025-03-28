import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import biomePlugin from "vite-plugin-biome";

export default defineConfig({
  define: {
    "import.meta.env.OPENAI_API_KEY": JSON.stringify(
      process.env.OPENAI_API_KEY,
    ),
    "import.meta.env.OPENAI_BASE_URL": JSON.stringify(
      process.env.OPENAI_BASE_URL,
    ),
  },
  plugins: [biomePlugin(), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
