import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// يُخدم التطبيق من FastAPI نفسه على الجذر، ويستهلك /api من الأصل نفسه: لا CORS
// ولا نطاق ثانٍ. في التطوير يحوّل Vite الطلبات إلى الخادم.
export default defineConfig({
  base: "/",
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    // لا شيء يُضمَّن data: — السياسة تسمح بالخطوط والأنماط والسكربتات من الأصل
    // وحده (font-src 'self'، img-src 'self' blob:).
    assetsInlineLimit: 0,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
})
