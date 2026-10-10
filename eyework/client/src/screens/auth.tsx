/*
 * ما قبل الدخول: الترحيب، والدخول، وخطوة حجم الواجهة في التسجيل
 * ==============================================================
 * قبل الدخول لا يُعرف حجم المستخدم: الشاشات بالحجم العادي، وفي رأسها زرّ «حجمٌ أكبر»
 * (aria-pressed) يبدّل إلى الكبير ويحمله في العنوان (?size=gaze) لا في المتصفّح. مكانه
 * الطرف الأعلى البادئ في الشاشات الثلاث، وزاويته ثابتةٌ في الحجمين، فنظرةٌ باقيةٌ عليه
 * بعد الضغط تبقى عليه.
 *
 * الترحيب (registration_spec §8.3): «أنشئ حساباً» و«ادخل» آمنان، تحت العنوان لا في
 * الطرف الأسفل حيث يظهر «أوافق وأتابع» في الإشعار. «أنشئ حساباً» في الوضع المفتوح وحده.
 * الدخول (AuthForm من 21st.dev، ملفّ premium-auth.tsx الذي ألصقه المالك؛ صفحته ورخصتها كما في
 * 21st.dev): «أنشئ حساباً» زرٌّ في الطرف الأعلى، لا
 * رابطٌ صغير في سطر؛ وإظهار كلمة المرور زرٌّ بنصّه؛ والخطأ من الخادم كما هو. ومفتاح المرور
 * زرّ دخولٍ وحده «ادخل بمفتاح المرور» (قرار المالك 2026-10-09)، ولا شيء عنه في «حسابي».
 * «كيف تستخدم الجهاز؟» (registration_spec §8.5، الخطوة use): بعد الإشعار وقبل الاسم، فما
 * بعدها بالحجم المختار. الاختيار لا يبدّل الحجم في مكانه: «التالي» يطبّقه وينتقل.
 */

import * as React from "react"
import { Eye, EyeOff, Fingerprint, Hand, LogIn, Maximize2, Minimize2, ScanEye, UserPlus } from "lucide-react"

import { PageTitle } from "@/components/brand/page-title"
import { Wordmark } from "@/components/brand/marks"
import { Slots } from "@/components/shell/slots"
import { Button, NextIcon, BackIcon } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { useSize, writeSizeToUrl, type SizeMode } from "@/lib/size"
import { cn } from "@/lib/utils"

/* ── الإطار ─────────────────────────────────────────────────────────── */

export function SizeToggle() {
  const { size, setSize } = useSize()
  const gaze = size === "gaze"
  return (
    <Button
      variant="ghost"
      aria-pressed={gaze}
      icon={gaze ? Minimize2 : Maximize2}
      onClick={() => {
        const next: SizeMode = gaze ? "compact" : "gaze"
        setSize(next)
        writeSizeToUrl(next)
      }}
    >
      حجمٌ أكبر
    </Button>
  )
}

/**
 * إطار ما قبل الدخول: عمودٌ واحد بعرض `max-w-md`، في أعلاه صفٌّ بخانتين ثابتتين كصفّ شاشات
 * البوابة («حجمٌ أكبر» في البداية، وفي النهاية ما يغادر أو يعود)، ثم المحتوى. في الحجم الكبير
 * بارتفاع الشاشة بلا تمرير.
 */
export function AuthFrame({ end, toggle = true, children, className }: {
  end?: React.ReactNode
  toggle?: boolean
  children: React.ReactNode
  className?: string
}) {
  const { size } = useSize()
  return (
    <div className={cn("mx-auto flex w-full max-w-md flex-col px-edge pb-safe pt-safe", size === "gaze" ? "h-dvh overflow-hidden" : "min-h-dvh", className)}>
      <header>
        <Slots top start={toggle ? <SizeToggle /> : undefined} end={end} />
      </header>
      {children}
    </div>
  )
}

/* ── الترحيب ───────────────────────────────────────────────────────── */

export type RegistrationMode = "open" | "code" | "closed"

export function WelcomeScreen({ mode, onSignup, onLogin }: { mode: RegistrationMode; onSignup: () => void; onLogin: () => void }) {
  return (
    <AuthFrame>
      {/* الزرّان بعد الاسم مباشرةً: «ادخل» في أعلى الشاشة يقع بعد الانتقال على حقول الدخول، و«ادخل» الذي
          يعتمد في أسفل شاشة الدخول. */}
      <main className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        {/* الاسم عنوان الترحيب، بارتفاع العلامة التي كان بجانبها (44) فلا يتحرّك ما تحته. */}
        <h1 className="flex min-h-11 items-center">
          <Wordmark decorative={false} className="text-[1.75rem]" />
        </h1>
        <div className="flex flex-col gap-tg">
          {mode === "open" ? (
            <Button id="welcome-signup" variant="primary" size="lg" width="full" icon={UserPlus} onClick={onSignup}>
              أنشئ حساباً
            </Button>
          ) : (
            <p className="text-flow text-muted-foreground">
              {mode === "code" ? "التسجيل هنا برابطٍ ممّن يدير التطبيق." : "الحسابات هنا بدعوةٍ ممّن يدير التطبيق."}
            </p>
          )}
          <Button id="welcome-login" variant={mode === "open" ? "outline" : "primary"} size="lg" width="full" icon={LogIn} onClick={onLogin}>
            ادخل
          </Button>
        </div>
      </main>
    </AuthFrame>
  )
}

/* ── الدخول ────────────────────────────────────────────────────────── */

export interface SignInProps {
  onSubmit: (username: string, password: string) => Promise<{ ok: true } | { ok: false; message: string; refused: boolean }>
  /** «ادخل بمفتاح المرور»، أو null حين لا WebAuthn في المتصفّح. */
  onPasskey: (() => void) | null
  /** «أنشئ حساباً» في الوضع المفتوح وحده؛ null في غيره. */
  onSignup: (() => void) | null
  /** بريد من يدير التطبيق في الوضع المفتوح، أو null. */
  contact: string | null
  initial?: { username?: string; error?: string }
}

export function SignInScreen({ onSubmit, onPasskey, onSignup, contact, initial }: SignInProps) {
  const [username, setUsername] = React.useState(initial?.username ?? "")
  const [password, setPassword] = React.useState("")
  const [reveal, setReveal] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(initial?.error ?? null)
  const [attempt, setAttempt] = React.useState(0)
  const [refused, setRefused] = React.useState<{ username: string; password: string } | null>(null)
  const unchanged = refused !== null && refused.username === username && refused.password === password

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || unchanged) return
    setAttempt((n) => n + 1)
    if (!username.trim() || !password) {
      setError("اكتب البريد وكلمة المرور.")
      return
    }
    setBusy(true)
    setError(null)
    const result = await onSubmit(username.trim(), password)
    setBusy(false)
    if (!result.ok) {
      if (result.refused) setRefused({ username, password })
      setError(result.message)
    }
  }

  return (
    <AuthFrame
      end={
        onSignup ? (
          <Button id="login-signup" variant="ghost" icon={UserPlus} onClick={onSignup}>
            أنشئ حساباً
          </Button>
        ) : undefined
      }
    >
      {/* «ادخل» في أسفل الشاشة والحقلان في أعلاها: «ادخل» في الترحيب (وسط الشاشة) يقع بعد
          الانتقال على حقلٍ لا على زرٍّ يعتمد؛ وسطر الخطأ محجوزٌ فوقه فلا يتحرّك حين يظهر. */}
      <main className="flex flex-1 flex-col">
      <form noValidate onSubmit={submit} className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-edge">
        <PageTitle>ادخل إلى بوابتك</PageTitle>
        <div className="flex flex-col gap-tg">
          <Field label="البريد">
            <Input
              dir="ltr"
              type="email"
              name="username"
              inputMode="email"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </Field>
          <Field label="كلمة المرور">
            <div className="flex gap-tg-min gaze:gap-tg">
              <Input
                dir="ltr"
                type={reveal ? "text" : "password"}
                name="password"
                autoComplete="current-password"
                enterKeyHint="go"
                maxLength={256}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <Button aria-pressed={reveal} icon={reveal ? EyeOff : Eye} onClick={() => setReveal((shown) => !shown)} className="shrink-0">
                أظهر
              </Button>
            </div>
          </Field>
          <p className="text-small text-muted-foreground gaze:short:hidden">
            {contact ? (
              <>
                نسيت كلمة المرور؟{" "}
                <bdi dir="ltr" className="num font-semibold text-foreground">
                  {contact}
                </bdi>
              </>
            ) : (
              "تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك."
            )}
          </p>
        </div>
        <div className="mt-auto flex flex-col gap-tg">
          <p role="alert" className="min-h-[1.45em] text-small font-medium text-destructive">
            {error ? <span key={attempt}>{error}</span> : null}
          </p>
          {/* في الحجم الكبير الزرّان في صفٍّ واحد: فوق بعضهما بفجوة 40 لا يتّسعان في 320×635. */}
          <div className="flex flex-col gap-tg gaze:flex-row-reverse">
            {onPasskey ? (
              <Button width="full" icon={Fingerprint} onClick={onPasskey} className="gaze:flex-1">
                {/* نصف الصفّ في 320px لا يتّسع لثلاث كلمات بلا سطرٍ ثالث. */}
                <span className="gaze:hidden">ادخل بمفتاح المرور</span>
                <span className="hidden gaze:inline">بمفتاح المرور</span>
              </Button>
            ) : null}
            <Button type="submit" variant="primary" size="lg" width="full" commit icon={LogIn} busy={busy} disabled={unchanged} className="gaze:flex-1">
              ادخل
            </Button>
          </div>
        </div>
      </form>
      </main>
    </AuthFrame>
  )
}

/* ── التسجيل: «كيف تستخدم الجهاز؟» ──────────────────────────────── */

/** معاينةٌ مرسومة: أهدافٌ صغيرةٌ كثيرة، أو كبيرةٌ قليلة. زخرفية. */
function SizePreview({ mode }: { mode: SizeMode }) {
  const rows = mode === "compact" ? 4 : 2
  return (
    <span aria-hidden="true" className="flex flex-col gap-1.5 rounded-ctl border border-border bg-background p-2">
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className="flex gap-1.5">
          <span className={cn("rounded-[4px] bg-primary/80", mode === "compact" ? "h-3 w-1/2" : "h-7 w-1/2")} />
          <span className={cn("rounded-[4px] border border-control bg-card", mode === "compact" ? "h-3 w-1/2" : "h-7 w-1/2")} />
        </span>
      ))}
    </span>
  )
}

/** الاسم والسطر كما يرسلهما الخادم في /api/choices (`ui_sizes`، eyework/ui_size.py). */
export interface UiSizeChoice {
  code: "COMPACT" | "GAZE"
  name: string
  line: string
}

export interface SignupSizeStepProps {
  /** ترقيم الخطوات بعد شاشتي الإشعار: هذه الأولى. */
  step: number
  steps: { id: string; label: string }[]
  /** الحجم الذي تُعرض به الشاشة: الخيار المبدئي (لا تخمين). */
  value: SizeMode
  choices: UiSizeChoice[]
  onNext: (mode: SizeMode) => void
  onBack: () => void
}

export function SignupSizeStep({ step, steps, value, choices, onNext, onBack }: SignupSizeStepProps) {
  const { size } = useSize()
  const [choice, setChoice] = React.useState<SizeMode>(value)
  const option = (code: UiSizeChoice["code"]) => choices.find((c) => c.code === code)
  return (
    <AuthFrame
      toggle={false}
      end={
        <Button icon={BackIcon} onClick={onBack}>
          رجوع
        </Button>
      }
    >
      <main className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-edge">
        <div className="flex flex-col gap-tg-min">
          <Stepper steps={steps} current={step} variant="brief" />
          <PageTitle>كيف تستخدم الجهاز؟</PageTitle>
        </div>
        {/* الخياران و«التالي» في أسفل الخطوة: ما يقع تحت موضع «أوافق وأتابع»
            بعد الانتقال نصٌّ أو «التالي»، لا خيار (registration_spec §8.10، القاعدة 4). */}
        <div className="mt-auto flex flex-col gap-tg">
          <RadioCards<SizeMode>
            label="كيف تستخدم الجهاز؟"
            value={choice}
            onValueChange={setChoice}
            columns={2}
            ids={{ compact: "signup-use-COMPACT", gaze: "signup-use-GAZE" }}
            options={[
              {
                value: "compact",
                title: option("COMPACT")?.name ?? "",
                icon: Hand,
                // المعاينتان باللمس وحده: في الحجم الكبير لا تتّسعان مع «التالي» بفجوة 40 في 320×635.
                preview: size === "compact" ? <SizePreview mode="compact" /> : undefined,
              },
              {
                value: "gaze",
                title: option("GAZE")?.name ?? "",
                icon: ScanEye,
                preview: size === "compact" ? <SizePreview mode="gaze" /> : undefined,
              },
            ]}
          />
          <Button id="signup-use-next" variant="secondary" size="lg" width="full" iconEnd={NextIcon} onClick={() => onNext(choice)}>
            التالي
          </Button>
        </div>
      </main>
    </AuthFrame>
  )
}
