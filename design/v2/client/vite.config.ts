import { fileURLToPath, URL } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

/*
 * واجهة eyework: ملفّاتٌ ثابتة يخدمها FastAPI تحت سياسة المحتوى نفسها (كل شيءٍ من الأصل:
 * لا خطّ ولا سكربت ولا صورة من خارجه، ولا شيء مضمَّن data:).
 *
 * قطعتان: `vendor` (React وframer-motion وlucide) و`app` (شيفرة التطبيق). اختبار المؤقّتات
 * في المتصفّح يعدّ ما تستدعيه قطعة `app` وحدها من setTimeout وأخواته (visual_spec §8.1):
 * جدولة React وإطارات framer-motion في `vendor` مسموحةٌ حين تبدأ بضغطةٍ أو بردّ خادم.
 *
 * `--mode demo` يبني صفحة العرض (demo.html) في dist-demo بصورها في demo-public: بياناتٌ
 * ثابتة لمراجعة التصميم وقياسه، لا تدخل بناء الإنتاج أبداً (tests/source.test.ts يفحص dist).
 */
export default defineConfig(({ mode }) => {
  const demo = mode === "demo"
  return {
    base: "/",
    plugins: [react()],
    publicDir: demo ? "demo-public" : "public",
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    build: {
      outDir: demo ? "dist-demo" : "dist",
      assetsInlineLimit: 0,
      rollupOptions: {
        input: (demo ? { demo: "demo.html" } : { index: "index.html" }) as Record<string, string>,
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
  }
})
