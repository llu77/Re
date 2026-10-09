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
 * الدخول (21st.dev AuthForm، premium-auth.tsx): «أنشئ حساباً» زرٌّ في الطرف الأعلى، لا
 * رابطٌ صغير في سطر؛ وإظهار كلمة المرور زرٌّ بنصّه؛ والخطأ من الخادم كما هو. ومفتاح المرور
 * زرّ دخولٍ وحده «ادخل بمفتاح المرور» (قرار المالك 2026-10-09)، ولا شيء عنه في «حسابي».
 * «كيف تستخدم الجهاز؟» (registration_spec §8.5، الخطوة use): بعد الإشعار وقبل الاسم، فما
 * بعدها بالحجم المختار. الاختيار لا يبدّل الحجم في مكانه: «التالي» يطبّقه وينتقل.
 */

import * as React from "react"
import {
  Boxes, Eye, EyeOff, Fingerprint, Hand, Headset, LogIn, Maximize2, Megaphone, Minimize2, ScanEye, UserPlus,
} from "lucide-react"

import { BrandMark, SymbolMark } from "@/components/brand/marks"
import { Slots } from "@/components/shell/slots"
import { Badge } from "@/components/ui/badge"
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
        <Slots start={toggle ? <SizeToggle /> : undefined} end={end} />
      </header>
      {children}
    </div>
  )
}

/* ── الترحيب ───────────────────────────────────────────────────────── */

const PROFESSIONS = [
  { icon: Boxes, name: "أمين المخزون", line: "فواتير الشراء والأصناف والمرتجعات" },
  { icon: Megaphone, name: "التسويق", line: "حملاتٌ من صورة المنتج إلى الإطلاق" },
  { icon: Headset, name: "الدعم الفني", line: "ردودٌ يكتبها سيمبول وتعتمدها أنت" },
]

export type RegistrationMode = "open" | "code" | "closed"

export function WelcomeScreen({ mode, onSignup, onLogin }: { mode: RegistrationMode; onSignup: () => void; onLogin: () => void }) {
  return (
    <AuthFrame>
      <main className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex items-center gap-2.5">
          <BrandMark className="size-10 gaze:size-12" />
          <span className="text-title font-semibold text-heading">صياغة</span>
        </div>
        {/* في الحجم الكبير الزرّان بعد العنوان مباشرةً والشرح بعدهما: «ادخل» في أعلى الشاشة يقع
            بعد الانتقال على حقول الدخول، و«ادخل» الذي يعتمد في أسفل شاشة الدخول. */}
        <div className="flex flex-col gap-3">
          <Badge tone="info" className="self-start gaze:hidden">
            بوابة عملٍ لمهنتك
          </Badge>
          <h1 className="text-display font-semibold leading-tight tracking-tight">عملك اليومي في بوابةٍ واحدة</h1>
          <p className="text-flow text-muted-foreground gaze:hidden">
            مخزونٌ وتسويقٌ ودعمٌ فني، لكل مهنةٍ أدواتها. وسيمبول يراجع معك ويقترح، والقرار لك.
          </p>
        </div>
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
        <ul aria-label="المهن" className="flex flex-col gap-2 gaze:hidden">
          {PROFESSIONS.map((p) => (
            <li key={p.name} className="flex items-center gap-3 rounded-card border border-border bg-card px-pad py-2.5 shadow-card">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-ctl bg-secondary text-secondary-foreground">
                <p.icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="font-semibold">{p.name}</span>
                <span className="text-small text-muted-foreground">{p.line}</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="hidden text-flow text-muted-foreground gaze:block">
          مخزونٌ وتسويقٌ ودعمٌ فني، لكل مهنةٍ أدواتها. وسيمبول يراجع معك ويقترح، والقرار لك.
        </p>
        <p className="flex items-start gap-2 text-small text-muted-foreground gaze:short:hidden">
          <SymbolMark className="mt-0.5 size-4" />
          يعمل باللمس وبتتبّع العين. للأزرار الكبيرة اضغط «حجمٌ أكبر» في الأعلى.
        </p>
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
          <Button id="login-signup" icon={UserPlus} onClick={onSignup}>
            أنشئ حساباً
          </Button>
        ) : undefined
      }
    >
      {/* «ادخل» في أسفل الشاشة والحقلان في أعلاها: «ادخل» في الترحيب (وسط الشاشة) يقع بعد
          الانتقال على حقلٍ لا على زرٍّ يعتمد؛ وسطر الخطأ محجوزٌ فوقه فلا يتحرّك حين يظهر. */}
      <main className="flex flex-1 flex-col">
      <form noValidate onSubmit={submit} className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex flex-col gap-2">
          <BrandMark className="size-10 gaze:hidden" />
          <h1 className="text-display font-semibold leading-tight tracking-tight">ادخل إلى بوابتك</h1>
          <p className="text-flow text-muted-foreground gaze:short:hidden">بالبريد وكلمة المرور، أو بمفتاح المرور.</p>
        </div>
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
            <div className="flex gap-tg-min">
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
                نسيت كلمة المرور؟ اكتب إلى{" "}
                <bdi dir="ltr" className="num font-semibold text-foreground">
                  {contact}
                </bdi>{" "}
                من بريد حسابك.
              </>
            ) : (
              "تعذّر الدخول؟ اطلب رابطاً جديداً ممّن دعاك أو أعطاك رابط التسجيل."
            )}
          </p>
        </div>
        <div className="mt-auto flex flex-col gap-tg">
          <p role="alert" className="min-h-[1.45em] text-small font-medium text-destructive">
            {error ? <span key={attempt}>{error}</span> : null}
          </p>
          {onPasskey ? (
            <Button width="full" icon={Fingerprint} onClick={onPasskey}>
              ادخل بمفتاح المرور
            </Button>
          ) : null}
          <Button type="submit" variant="primary" size="lg" width="full" commit icon={LogIn} busy={busy} disabled={unchanged}>
            ادخل
          </Button>
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
      <main className="flex flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex flex-col gap-tg-min">
          <Stepper steps={steps} current={step} variant="brief" />
          <h1 className="text-display font-semibold leading-tight tracking-tight">كيف تستخدم الجهاز؟</h1>
          <p className="text-flow text-muted-foreground">
            تُحفظ مع حسابك لتُفتح بوابتك بحجمها، ولا تُرسَل إلى مزوّد النموذج. وتغيّرها متى شئت من «حسابي».
          </p>
        </div>
        {/* الخياران و«التالي» في أسفل الخطوة، والشرح فوقهما: ما يقع تحت موضع «أوافق وأتابع»
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
                preview: <SizePreview mode="compact" />,
                description: size === "compact" ? option("COMPACT")?.line : undefined,
              },
              {
                value: "gaze",
                title: option("GAZE")?.name ?? "",
                icon: ScanEye,
                preview: <SizePreview mode="gaze" />,
                description: size === "compact" ? option("GAZE")?.line : undefined,
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
