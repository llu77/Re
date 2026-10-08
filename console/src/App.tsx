import * as React from "react"

import { forgetSession, loadSession } from "@/lib/api"

import { ConsoleShell } from "@/components/console/console-shell"
import { LoginScreen, type SignedIn } from "@/components/console/login-screen"
import { forgetDrafts } from "@/components/console/proposal-page"

const EMAIL_KEY = "symbol.practitioner.email"

function restore(): SignedIn | null {
  const session = loadSession()
  if (!session) return null
  let email = ""
  try {
    email = window.sessionStorage.getItem(EMAIL_KEY) ?? ""
  } catch {
    email = ""
  }
  return { ...session, email }
}

export function App() {
  const [session, setSession] = React.useState<SignedIn | null>(restore)
  const [expired, setExpired] = React.useState(false)
  const lastEmail = React.useRef(session?.email ?? "")

  const signedIn = React.useCallback((next: SignedIn) => {
    try {
      window.sessionStorage.setItem(EMAIL_KEY, next.email)
    } catch {
      // بلا تخزين: البريد يظهر لهذا التحميل وحده.
    }
    // ممارسٌ آخر يدخل بعد انتهاء جلسة غيره: لا يرى ما كتبه ذاك ولم يُرسله.
    if (lastEmail.current && lastEmail.current !== next.email) forgetDrafts()
    lastEmail.current = next.email
    setExpired(false)
    setSession(next)
  }, [])

  const signedOut = React.useCallback((reason: "signed-out" | "expired") => {
    // انتهاء الجلسة يُقال، وما كُتب يبقى في الذاكرة حتى يعود الممارس نفسه.
    // والخروج المقصود يمحوه: الجهاز قد يكون مشتركاً في العيادة.
    if (reason === "signed-out") forgetDrafts()
    setExpired(reason === "expired")
    forgetSession()
    try {
      window.sessionStorage.removeItem(EMAIL_KEY)
    } catch {
      // لا شيء محفوظ أصلاً.
    }
    setSession(null)
  }, [])

  return session ? (
    <ConsoleShell session={session} onSignedOut={signedOut} />
  ) : (
    <LoginScreen onSignedIn={signedIn} expired={expired} />
  )
}
