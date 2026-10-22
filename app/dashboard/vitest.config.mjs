// Component tests (ROADMAP 6.3.7): Vitest + Testing Library in jsdom.
// End-to-end browser tests live in e2e/ and run with Playwright instead.
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: {
    environment: "jsdom",
    setupFiles: ["./__tests__/setup.js"],
    include: ["__tests__/**/*.test.{js,jsx}"],
    restoreMocks: true,
  },
});
