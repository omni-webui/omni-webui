import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import biomePlugin from "vite-plugin-biome";

export default defineConfig({
  envPrefix: [
    "OMNI_WEBUI_",
    "FASTOAI_",  // FastOAI is also created by me :)
    "OPENAI_",
    "ANTHROPIC_",
    "GEMINI_",
    "GRQQ_",
    "LM_STUDIO_",
    "XAI_",
    "AZURE_",
    "COHERE_",
    "DEEPSEEK_",
    "OLLAMA_",
    "OPENROUTER_",
  ],
  plugins: [biomePlugin(), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
