import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

/*
 * واجهة eyework الجديدة: ملفّاتٌ ثابتة يخدمها FastAPI تحت سياسة المحتوى نفسها (كل شيءٍ من
 * الأصل: لا خطّ ولا سكربت ولا صورة من خارجه، ولا شيء مضمَّن data:). تُخدم تحت /next/ حتى
 * حزمة التبديل: العميل الثابت عند «/» كما هو، وهذا يُجرَّب بجانبه على الخادم نفسه.
 *
 * قطعتان: `vendor` (React وframer-motion وlucide) و`app` (شيفرة التطبيق). اختبار المؤقّتات
 * في المتصفّح يعدّ ما تستدعيه قطعة `app` وحدها من setTimeout وأخواته: جدولة React وإطارات
 * framer-motion في `vendor` مسموحةٌ حين تبدأ بضغطةٍ أو بردّ خادم.
 */
export default defineConfig({
  base: "/next/",
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        entryFileNames: "assets/app-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        manualChunks(id: string) {
          if (id.includes("node_modules")) return "vendor"
          return undefined
        },
      },
    },
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
