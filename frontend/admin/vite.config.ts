import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { goldenReviewServer } from "./server/index.ts";

export default defineConfig({
  plugins: [react(), goldenReviewServer()],
  server: {
    port: 5183,
  },
});
