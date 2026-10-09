/*
 * التطبيق: الإقلاع والتوجيه
 * =========================
 * كما في static/app.js: لا شاشة تفاعلية قبل خيارات الخادم (/api/choices)، ثم صاحب الجلسة
 * (/api/me) إلا في التسجيل والتفعيل حيث لا جلسة بعد. التوجيه بالوسم:
 *
 *   #/            الترحيب قبل الدخول، والرئيسية بعده (أو تسلسل البدء لحسابٍ بلا حجمٍ أو
 *                 بإشعارٍ أقدم)
 *   #/login       الدخول بكلمة المرور أو بمفتاح المرور
 *   #/activate    تفعيل حساب دعوة (#activate=…&u=…)
 *   #/signup/…    التسجيل، شاشةً شاشة (#signup=… برابط، أو من «أنشئ حساباً» بلا رابط)
 *   #/account/…   حسابي والمصادر والخروج والحذف
 *   #/marketing/… أداة الحملة: في هذه الحزمة تفتح شاشات العميل القائم عند «/»
 *
 * الحجم: قبل الدخول من العنوان (?size=large)، وبعده من الخادم وحده؛ و`null` من الخادم
 * يعني «اسأل» (تسلسل البدء)، لا «عادي».
 */

import * as React from "react"

import { AccountFlow } from "@/app/account-flow"
import { AppProviders } from "@/app/providers"
import { SignupFlow } from "@/app/signup-flow"
import { StartFlow } from "@/app/start-flow"
import { WorkspaceView } from "@/app/workspace"
import { Button } from "@/components/ui/button"
import { Notice } from "@/components/ui/notice"
import { Redirect } from "@/components/redirect"
import { api, detail } from "@/lib/api"
import { passkeyLogin, passkeysAvailable, preparePasskey, refreshPasskeyOnReturn, upgradeToPasskey } from "@/lib/passkeys"
import { go, reload, route as routeOf, useHash } from "@/lib/router"
import { boot, captureLinks } from "@/lib/session"
import { newSignup } from "@/lib/signup"
import { fromServer, sizeFromUrl, type SizeMode } from "@/lib/size"
import { getState, setState, useStore, type Choices, type Me } from "@/lib/store"
import { ActivateScreen } from "@/screens/activate"
import { SignInScreen, WelcomeScreen } from "@/screens/auth"

/* ── ما قبل الدخول ───────────────────────────────────────────────── */

function Welcome({ choices }: { choices: Choices }) {
  return (
    <WelcomeScreen
      mode={choices.registration.mode}
      onSignup={() => {
        setState({ signup: newSignup(null) })
        go("#/signup")
      }}
      onLogin={() => go("#/login")}
    />
  )
}

function SignIn({ choices }: { choices: Choices }) {
  const flash = useStore((s) => s.flash)
  const [notice, setNotice] = React.useState<string | null>(null)
  const available = passkeysAvailable()
  // رسالةٌ من شاشةٍ سابقة (رابط تسجيلٍ رُفض): تُعرض مرةً واحدة.
  React.useEffect(() => {
    if (flash) {
      setNotice(flash)
      setState({ flash: null })
    }
  }, [flash])
  React.useEffect(() => {
    if (!available) return undefined
    preparePasskey()
    const refresh = () => refreshPasskeyOnReturn(true)
    window.addEventListener("pageshow", refresh)
    document.addEventListener("visibilitychange", refresh)
    return () => {
      window.removeEventListener("pageshow", refresh)
      document.removeEventListener("visibilitychange", refresh)
    }
  }, [available])

  async function submit(username: string, password: string) {
    const result = await api("POST", "/api/auth/login", { json: { username, password } })
    if (result.status === 204) {
      // المتصفّح يحفظ مفتاحاً بعد الدخول بكلمة المرور حيث يدعم ذلك، ثم انتقالٌ كامل.
      await upgradeToPasskey(username)
      reload()
      return { ok: true as const }
    }
    return { ok: false as const, message: detail(result), refused: result.status === 401 }
  }

  const open = choices.registration.mode === "open"
  return (
    <Notice message={notice} onAck={() => setNotice(null)}>
      <SignInScreen
        onSubmit={submit}
        onPasskey={available ? () => void passkeyLogin().then((message) => message && setNotice(message)) : null}
        onSignup={open ? () => {
          setState({ signup: newSignup(null) })
          go("#/signup")
        } : null}
        contact={open ? choices.support_contact : null}
      />
    </Notice>
  )
}

function Activate({ choices }: { choices: Choices }) {
  const activation = useStore((s) => s.activation)
  const [notice, setNotice] = React.useState<string | null>(null)
  if (!activation) {
    return (
      <Notice message="افتح رابط التفعيل من جديد." onAck={() => go("#/login", { replace: true })}>
        <span />
      </Notice>
    )
  }
  return (
    <Notice message={notice} onAck={() => setNotice(null)}>
      <ActivateScreen
        username={activation.username}
        passwordMin={choices.registration.password_min}
        onSubmit={async (password) => {
          const result = await api("POST", "/api/auth/activate", {
            json: { token: activation.token, username: activation.username, password },
          })
          if (result.status === 204) {
            setState({ activation: null })
            reload()
            return null
          }
          return detail(result)
        }}
      />
    </Notice>
  )
}

function StartupFailed({ message }: { message: string }) {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col items-center justify-center gap-tg px-edge">
      <p role="alert" className="text-flow text-center font-bold text-destructive">
        {message}
      </p>
      <Button id="boot-retry" variant="primary" size="lg" onClick={() => void boot()}>
        حاول مرة أخرى
      </Button>
    </div>
  )
}

/* ── التوجيه ─────────────────────────────────────────────────────── */

function Router() {
  const hash = useHash()
  const path = routeOf(hash)
  // قيمةٌ واحدة لكل اختيار: كائنٌ جديد في كل قراءة يعيد الرسم بلا نهاية.
  const choices = useStore((s) => s.choices)
  const me = useStore((s) => s.me)
  const booted = useStore((s) => s.booted)
  const startupError = useStore((s) => s.startupError)
  if (startupError) return <StartupFailed message={startupError} />
  if (!booted || !choices) return null
  if (path.startsWith("#/activate")) return <Activate choices={choices} />
  if (path.startsWith("#/signup")) return <SignupFlow path={path} choices={choices} />
  if (path.startsWith("#/login")) return me ? <Redirect to="#/" /> : <SignIn choices={choices} />
  if (!me) return path === "#/" || path === "#" ? <Welcome choices={choices} /> : <Redirect to="#/" />
  // حسابٌ بلا حجمٍ (دعوة، أو أقدم من الحزمة 1) أو بإشعارٍ أقدم: يُسأل قبل أيّ شاشة.
  if (me.ui_size === null || !me.terms_current) return <StartFlow path={path} choices={choices} me={me} />
  if (path.startsWith("#/account")) return <AccountFlow path={path} choices={choices} me={me} />
  return <WorkspaceView path={path} choices={choices} me={me} />
}

function initialSize(me: Me | null): SizeMode {
  if (me) return fromServer(me.ui_size) ?? "compact"
  return sizeFromUrl() ?? "compact"
}

export function App() {
  const me = useStore((s) => s.me)
  const booted = useStore((s) => s.booted)
  React.useEffect(() => {
    captureLinks()
    void boot()
  }, [])
  if (!booted && !getState().startupError) return null
  // مزوّدٌ جديد حين يدخل صاحب الحساب أو يخرج: الحجم من الخادم بعد الدخول، ومن العنوان قبله.
  return (
    <AppProviders key={me ? "in" : "out"} size={initialSize(me)}>
      <Router />
    </AppProviders>
  )
}
