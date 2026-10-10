/*
 * المسارات بالوسم، كما في app.js وportal.js. شاشةٌ واحدة معروضة في كل لحظة؛ وقبل
 * أن تصل الخيارات من الخادم لا شاشة (لا أزرار في موضعٍ مؤقّت تحت النظر).
 */
import * as React from "react"

import { api, detail } from "@/lib/api"
import { go, useHash } from "@/lib/router"
import { setState, showAlert, useStore } from "@/lib/store"
import type { Choices } from "@/lib/types"
import { About } from "@/screens/about"
import { Account, AccountLogout } from "@/screens/account"
import { Assistant, AssistantWrite } from "@/screens/assistant"
import { Home } from "@/screens/home"
import { Login } from "@/screens/login"
import { PortalItem } from "@/screens/portal-item"
import { SignupName, SignupNotice, SignupYear } from "@/screens/signup"
import { Welcome } from "@/screens/welcome"

async function boot() {
  const choices = await api<Choices>("GET", "/api/choices")
  if (choices.status !== 200 || !choices.data) {
    go("#/login", { replace: true })
    showAlert("login", `${detail(choices)} «حسناً» تعيد المحاولة.`)
    return
  }
  setState({ choices: choices.data })
  const hash = location.hash || "#/"
  // التسجيل والترحيب والدخول قبل الجلسة: لا يُسأل عن صاحبٍ لم يُنشأ حسابه بعد.
  if (/^#\/(signup|welcome|login)/.test(hash)) return
  const response = await fetch("/api/me", { headers: { "X-Eyework": "1" }, credentials: "same-origin", cache: "no-store" })
  if (response.status === 200) {
    const me = (await response.json()) as { display_name: string | null }
    setState({ displayName: me.display_name || null })
  } else if (response.status === 401) {
    // لا جلسة: من فتح التطبيق يرى الترحيب؛ ومن انتهت جلسته أثناء العمل يرى الدخول (api).
    go("#/welcome", { replace: true })
  } else {
    go("#/login", { replace: true })
    showAlert("login", "حدث خطأ. «حسناً» تعيد المحاولة.")
  }
}

export function App() {
  const hash = useHash()
  const ready = useStore((s) => s.choices !== null)
  React.useEffect(() => {
    void boot()
  }, [])
  if (!ready && !hash.startsWith("#/login")) return null

  if (hash.startsWith("#/welcome")) return <Welcome />
  if (hash.startsWith("#/login")) return <Login />
  if (hash === "#/signup") return <SignupNotice />
  if (hash === "#/signup/name") return <SignupName />
  if (hash === "#/signup/year") return <SignupYear />
  if (hash === "#/about") return <About />
  if (hash === "#/account") return <Account />
  if (hash === "#/account/logout") return <AccountLogout />
  if (hash === "#/assistant") return <Assistant />
  if (hash === "#/assistant/write") return <AssistantWrite />
  const context = hash.match(/^#\/assistant\/(tasks|skills)\/([0-9]{1,3})$/)
  if (context) return <Assistant context={{ kind: context[1] as "tasks" | "skills", n: Number(context[2]) }} />
  const item = hash.match(/^#\/(tasks|skills)\/([0-9]{1,3})$/)
  if (item) return <PortalItem kind={item[1] as "tasks" | "skills"} position={Number(item[2])} />
  return <Home />
}
