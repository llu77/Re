import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { App } from "@/app/app"
import { getState } from "@/lib/store"
import "@/styles/globals.css"

// للاختبارات: قراءة الحالة كما تقرأ اختبارات العميل القائم متغيّره `state`؛ لا كتابة من هنا.
Object.defineProperty(window, "__eyework_state", { value: getState })

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
