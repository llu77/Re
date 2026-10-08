import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// اللوحة تُخدم من التطبيق نفسه تحت /console، وتستهلك /practitioner من الأصل
// نفسه: لا CORS ولا نطاق ثانٍ. في التطوير يحوّل Vite الطلبات إلى الخادم.
export default defineConfig({
  base: "/console/",
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    // لا شيء يُضمَّن data: — سياسة المحتوى تسمح بالخطوط والأنماط والسكربتات من
    // الأصل وحده؛ data: للصور وحدها (رسوم المقترحات).
    assetsInlineLimit: 0,
  },
  server: {
    proxy: { "/practitioner": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
})
