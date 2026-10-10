/*
 * تفعيل حسابٍ بدعوة
 * =================
 * رابط التفعيل (#activate=…&u=…) من المشغّل: اسم الدخول فيه، وكلمة مرورٍ جديدة هنا، ثم
 * انتقالٌ كامل كالدخول (يعرض Safari حفظها). منقولٌ من static/app.js.
 */

import * as React from "react"
import { KeyRound } from "lucide-react"

import { PageTitle } from "@/components/brand/page-title"
import { Button } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { AuthFrame } from "@/screens/auth"

export function ActivateScreen({ username, passwordMin, onSubmit }: {
  username: string
  passwordMin: number
  onSubmit: (password: string) => Promise<string | null>
}) {
  const [password, setPassword] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return
    setAttempt((n) => n + 1)
    if (password.length < passwordMin) {
      setError(`كلمة المرور من ${passwordMin} حرفاً على الأقل.`)
      return
    }
    setBusy(true)
    setError(null)
    const message = await onSubmit(password)
    setBusy(false)
    if (message) setError(message)
  }

  return (
    <AuthFrame>
      <main className="flex flex-1 flex-col">
        <form noValidate onSubmit={submit} className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
          <div className="flex flex-col gap-2">
            <PageTitle>فعّل حسابك</PageTitle>
          </div>
          <div className="flex flex-col gap-tg">
            <Field label="اسم الدخول">
              <Input dir="ltr" type="email" name="username" autoComplete="username" value={username} readOnly />
            </Field>
            <Field label="كلمة مرورٍ جديدة">
              <Input
                dir="ltr"
                type="password"
                name="password"
                autoComplete="new-password"
                minLength={passwordMin}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
          </div>
          <div className="mt-auto flex flex-col gap-tg">
            <p role="alert" className="min-h-[1.45em] text-small font-medium text-destructive">
              {error ? <span key={attempt}>{error}</span> : null}
            </p>
            <Button id="activate-submit" type="submit" variant="primary" size="lg" width="full" commit icon={KeyRound} busy={busy}>
              فعّل حسابي
            </Button>
          </div>
        </form>
      </main>
    </AuthFrame>
  )
}
