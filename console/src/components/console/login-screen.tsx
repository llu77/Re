import * as React from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError, login } from "@/lib/api"
import type { Session } from "@/lib/types"

import { ErrorNotice } from "./feedback"
import { SymbolMark } from "./symbol-mark"

export interface SignedIn extends Session {
  email: string
}

export function LoginScreen({ onSignedIn }: { onSignedIn: (session: SignedIn) => void }) {
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const session = await login(email.trim(), password)
      onSignedIn({ ...session, email: email.trim() })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تسجيل الدخول. أعد المحاولة.")
      setPassword("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-secondary px-4 py-10">
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <SymbolMark className="size-10" />
          <div className="leading-tight">
            <p className="font-bold text-primary" lang="en" dir="ltr">
              Symbol AI
            </p>
            <h1 className="text-xl font-bold">لوحة الممارس</h1>
          </div>
        </div>
        <p className="mb-6 text-muted-foreground">
          النظام يقترح، والممارس يقرّر. لا يصل المريضَ محتوى دون اعتمادك.
        </p>

        <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email" className="text-base">
              البريد الإلكتروني
            </Label>
            <Input
              id="email"
              type="email"
              dir="ltr"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-12 text-base"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password" className="text-base">
              كلمة المرور
            </Label>
            <Input
              id="password"
              type="password"
              dir="ltr"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-12 text-base"
            />
          </div>

          {error ? <ErrorNotice message={error} /> : null}

          <Button
            type="submit"
            className="h-12 text-base"
            disabled={busy || !email.trim() || !password}
          >
            {busy ? "جارٍ الدخول…" : "تسجيل الدخول"}
          </Button>
        </form>
      </div>
    </main>
  )
}
