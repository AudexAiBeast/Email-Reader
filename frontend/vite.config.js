import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-time proxy so the frontend can call /graphql and /api/* as same-origin
// paths without needing CORS at all; the backend already allows any origin
// too, so this also works if you open the built app from somewhere else.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/graphql": "http://localhost:8000",
      "/api": "http://localhost:8000",
    },
  },
});
