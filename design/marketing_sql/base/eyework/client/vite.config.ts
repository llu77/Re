import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// واجهة eyework الجديدة: تُبنى ملفّاتٍ ثابتة يخدمها FastAPI تحت سياسة المحتوى نفسها
// (كل شيءٍ من الأصل: لا خطّ ولا سكربت ولا صورة من خارجه). تُخدم تحت /next/ ما دامت
// الشاشات تنتقل إليها: ما لم ينتقل بعد شاشةٌ في التطبيق القائم عند «/»، والانتقال
// إليها تنقّلٌ حقيقي إلى وثيقةٍ أخرى. في التطوير يحوّل Vite طلبات /api إلى الخادم.
export default defineConfig({
  base: "/next/",
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    // لا شيء يُضمَّن data: — الخطوط والصور ملفّاتٌ من الأصل.
    assetsInlineLimit: 0,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
})
