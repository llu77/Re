/*
 * الدخول. «ادخل» (يرسل) في المحتوى بعرض الشاشة؛ وأسفل البداية — حيث كان «ادخل» في
 * الترحيب — زرّ مفتاح المرور، أو «أظهر كلمة المرور» حيث لا مفاتيح مرور: نظرةٌ باقية
 * هناك تفتح نافذة النظام أو تُظهر الحقل، ولا ترسل شيئاً.
 */
import * as React from "react"
import { ChevronRight, Eye, EyeOff, KeyRound, Lock, LogIn, Mail } from "lucide-react"

import { BottomBar, Content, Screen, TopBar } from "@/components/frame/screen"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, detail } from "@/lib/api"
import { passkeyLogin, passkeysAvailable, preparePasskey } from "@/lib/passkeys"
import { go } from "@/lib/router"
import { getState, setState, showAlert } from "@/lib/store"

export function Login() {
  const [revealed, setRevealed] = React.useState(false)
  const username = React.useRef<HTMLInputElement>(null)
  const password = React.useRef<HTMLInputElement>(null)
  const passkeys = passkeysAvailable()
  // خيارات مفتاح المرور تُجلب حين تُعرض الشاشة، لا داخل الضغطة.
  React.useEffect(() => preparePasskey("login"), [])

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (getState().busy) return
    setState({ busy: true })
    const result = await api("POST", "/api/auth/login", {
      json: { username: username.current?.value ?? "", password: password.current?.value ?? "" },
    })
    setState({ busy: false })
    if (result.status === 204) {
      if (password.current) password.current.value = ""
      // انتقالٌ كامل: لا يبقى في الذاكرة شيءٌ لحسابٍ سابق، ويعرض Safari حفظ كلمة المرور.
      location.replace("/")
    } else {
      showAlert("login", detail(result))
    }
  }

  return (
    <Screen name="login">
      <TopBar
        start={
          <Button icon={ChevronRight} onClick={() => go("#/welcome")} data-back="">
            رجوع
          </Button>
        }
        step="الدخول"
      />
      <Content as="form" id="login-form" onSubmit={onSubmit}>
        <h2 tabIndex={-1} className="text-title">
          أهلاً بعودتك
        </h2>
        <p className="text-muted-foreground">ادخل ببريدك وكلمة المرور.</p>
        <div className="flex flex-col gap-1">
          <Label htmlFor="login-username">البريد الإلكتروني</Label>
          <Input
            ref={username}
            id="login-username"
            name="username"
            type="email"
            icon={Mail}
            dir="ltr"
            autoComplete="username"
            inputMode="email"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            required
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="login-password">كلمة المرور</Label>
          <Input
            ref={password}
            id="login-password"
            name="password"
            type={revealed ? "text" : "password"}
            icon={Lock}
            dir="ltr"
            autoComplete="current-password"
            enterKeyHint="go"
            required
          />
        </div>
        <Button id="login-submit" type="submit" commit variant="primary" icon={LogIn} className="spaced w-full">
          ادخل
        </Button>
      </Content>
      <BottomBar
        start={
          passkeys ? (
            <Button id="login-passkey" icon={KeyRound} onClick={passkeyLogin}>
              ادخل بمفتاح المرور
            </Button>
          ) : (
            <Button
              id="login-reveal"
              icon={revealed ? EyeOff : Eye}
              aria-pressed={revealed}
              onClick={() => setRevealed((shown) => !shown)}
            >
              {revealed ? "أخفِ كلمة المرور" : "أظهر كلمة المرور"}
            </Button>
          )
        }
      />
    </Screen>
  )
}
