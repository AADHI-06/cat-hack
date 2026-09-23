import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development, /api is forwarded to the FastAPI backend
// (uvicorn app.main:app --reload --app-dir backend).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": process.env.VITE_API_TARGET || "http://127.0.0.1:8000",
    },
  },
});
