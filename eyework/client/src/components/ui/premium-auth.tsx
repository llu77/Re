/*
 * AuthForm — الدخول وبداية التسجيل
 * ==================================
 * الأصل: premium-auth.tsx من 21st.dev (AuthForm وPasswordStrengthIndicator)، كما
 * لصقه المالك. مكيَّفٌ لـeyework، ولكل تكييفٍ سببه:
 *
 *  • الدخول طلبٌ حقيقي إلى /api/auth/login، لا setTimeout يحاكيه، ورسالة الخطأ
 *    من الخادم كما هي.
 *  • لا استعادة كلمة مرورٍ بالبريد ولا رمز تحقّقٍ بالبريد: التطبيق لا يرسل بريداً.
 *  • لا هاتف، ولا «تذكّرني» في localStorage: سلسلة مفاتيح iCloud تحفظ الدخول،
 *    والتطبيق لا يخزّن في المتصفّح شيئاً.
 *  • «حساب جديد» يبدأ خطوات التسجيل، خطوةً في كل شاشة (`onStartSignup`): نموذجٌ
 *    بستّة حقولٍ في شاشةٍ واحدة لا يُملأ بالنظر. ومضيفٌ لا يملك بعد طريقاً إلى
 *    التسجيل لا يمرّر `onStartSignup`، فيقول الوضع ذلك بدل زرٍّ لا يفضي إلى شيء.
 *  • بعد دخولٍ رُفض يبقى «ادخل» معطّلاً حتى يتغيّر حقل: نظرٌ باقٍ عليه لا يعيد إرسال
 *    الاسم وكلمة المرور نفسيهما.
 *  • كل هدفٍ 72px على الأقل وبين كل هدفين 24px؛ فإظهار كلمة المرور زرٌّ مستقلٌّ
 *    بنصّه، لا أيقونةٌ صغيرة داخل الحقل.
 *  • قياس القوّة يقيس ما يفرضه الخادم وحده: الطول بين 12 و256. القواعد الأخرى
 *    في الأصل (حرفٌ كبير، رمز) لا يفرضها الخادم، فلا تُعرض كأنها شرط.
 *  • العربية من اليمين؛ والظهور تلاشٍ بـCSS يسقط مع «تقليل الحركة»؛ ولا شيء
 *    يتغيّر على الشاشة إلا بضغطةٍ أو بردّ الخادم عليها.
 *  • رسالة الخطأ تحت آخر زرّ: ظهورها لا يحرّك هدفاً تحت نظرٍ باقٍ.
 */

import * as React from "react"
import { useId, useState } from "react"
import { AlertTriangle, Eye, EyeOff, Loader2, Lock, LogIn, Mail, UserPlus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { api, detail } from "@/lib/api"
import { cn } from "@/lib/utils"

export type AuthMode = "login" | "signup"

/** حدّا كلمة المرور في الخادم (`auth.PASSWORD_MIN` و`PASSWORD_MAX`). */
export const PASSWORD_MIN = 12
export const PASSWORD_MAX = 256

export interface AuthFormProps {
  /** بعد دخولٍ نجح: الجلسة في ملفّ التعريف، والمضيف يفتح البوابة. */
  onSignedIn: () => void
  /** «ابدأ التسجيل»: المضيف يفتح الخطوة الأولى من خطوات التسجيل. بلا قيمةٍ لا زرّ. */
  onStartSignup?: () => void
  /** @default "login" */
  initialMode?: AuthMode
  className?: string
}

/* ── قوّة كلمة المرور ─────────────────────────────────────────────────── */

export interface PasswordStrength {
  length: number
  enough: boolean
  tooLong: boolean
}

export function passwordStrength(password: string, min = PASSWORD_MIN, max = PASSWORD_MAX): PasswordStrength {
  // الطول بالمحارف كما يعدّها الخادم (Python len)، لا بوحدات UTF-16.
  const length = [...password].length
  return { length, enough: length >= min && length <= max, tooLong: length > max }
}

export function PasswordStrengthIndicator({ password, min = PASSWORD_MIN }: { password: string; min?: number }) {
  const strength = passwordStrength(password, min)
  const progress = Math.min(strength.length / min, 1)
  const text = strength.tooLong
    ? `أطول من ${PASSWORD_MAX} حرفاً.`
    : strength.enough
      ? "الطول كافٍ. والأطول أقوى."
      : `${strength.length} من ${min} حرفاً على الأقل.`
  return (
    <div className="space-y-2" aria-live="polite">
      <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div
          className={cn("h-full rounded-full", strength.enough ? "bg-success" : "bg-primary")}
          style={{ width: `${progress * 100}%` }}
        />
      </div>
      <p className={cn("text-base", strength.enough ? "text-success" : "text-muted-foreground")}>{text}</p>
    </div>
  )
}

/* ── الحقل ───────────────────────────────────────────────────────────── */

interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  icon: React.ElementType
}

const Field = React.forwardRef<HTMLInputElement, FieldProps>(({ label, icon: Icon, className, ...props }, ref) => {
  const id = useId()
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-base font-medium">
        {label}
      </label>
      <div className="relative">
        <Icon className="pointer-events-none absolute right-5 top-1/2 size-6 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        {/* البريد وكلمة المرور لاتينيّان: يُكتبان من اليسار، والأيقونة يميناً كبقية الصفحة. */}
        <input
          ref={ref}
          id={id}
          dir="ltr"
          className={cn(
            "h-target w-full rounded-xl border border-input bg-card pl-5 pr-16 text-lg text-foreground shadow-sm transition-shadow",
            "focus-visible:border-primary",
            className,
          )}
          {...props}
        />
      </div>
    </div>
  )
})
Field.displayName = "Field"

/* ── العلامة ─────────────────────────────────────────────────────────── */

/* علامةٌ هندسية محايدة: الاسم والعنوان والأيقونة لا تذكر النظر ولا العين ولا الإعاقة
   (tests/architecture/test_separation.py)، فقائمة مستخدمي التطبيق معلومةٌ صحّية. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={cn("size-12 shrink-0", className)} role="img" aria-label="صياغة">
      <rect width="48" height="48" rx="14" className="fill-primary" />
      <rect x="13" y="13" width="14" height="14" rx="3" className="fill-primary-foreground" />
      <rect x="21" y="21" width="14" height="14" rx="3" className="fill-primary-foreground opacity-60" />
    </svg>
  )
}

/* ── النموذج ─────────────────────────────────────────────────────────── */

export function AuthForm({ onSignedIn, onStartSignup, initialMode = "login", className }: AuthFormProps) {
  const [mode, setMode] = useState<AuthMode>(initialMode)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [reveal, setReveal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // كل محاولةٍ تعيد رسم التنبيه، فيُقرأ من جديد ولو تكرّر نصّه.
  const [attempt, setAttempt] = useState(0)
  // ما رفضه الخادم: «ادخل» معطّلٌ ما دام الحقلان كما رُفضا.
  const [refused, setRefused] = useState<{ username: string; password: string } | null>(null)
  const unchanged = refused !== null && refused.username === username && refused.password === password

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || unchanged) return
    setAttempt((n) => n + 1)
    const name = username.trim()
    if (!name || !password) {
      setError("اكتب اسم الدخول وكلمة المرور.")
      return
    }
    setBusy(true)
    setError(null)
    const result = await api("POST", "/api/auth/login", { username: name, password })
    setBusy(false)
    if (result.status === 204) {
      onSignedIn()
      return
    }
    // رفضٌ لما أُرسل (لا انقطاع ولا حدّ): لا يُعاد إرساله كما هو.
    if (result.status === 401 || result.status === 422) {
      setRefused({ username, password })
    }
    setError(result.status === 422 ? "تحقّق من اسم الدخول وكلمة المرور." : detail(result))
  }

  function choose(next: AuthMode) {
    setMode(next)
    setError(null)
  }

  return (
    <section
      dir="rtl"
      aria-labelledby="auth-title"
      className={cn("mx-auto flex w-full max-w-md flex-col gap-target-gap", className)}
    >
      <header className="flex items-center gap-4">
        <BrandMark />
        <div>
          <h2 id="auth-title" className="text-2xl font-bold leading-tight">
            {mode === "login" ? "أهلاً بعودتك" : "حسابٌ جديد"}
          </h2>
          <p className="text-base text-muted-foreground">
            {mode === "login" ? "ادخل إلى بوابة عملك" : "بوابة عملٍ لمهنتك"}
          </p>
        </div>
      </header>

      {/* الوضعان زرّان متباعدان لا شريطٌ ملتصق: بينهما 24px كبين كل هدفين. */}
      <div className="grid grid-cols-2 gap-target-gap" role="group" aria-label="الدخول أو حسابٌ جديد">
        {(["login", "signup"] as const).map((value) => (
          <Button
            key={value}
            variant={mode === value ? "default" : "secondary"}
            aria-pressed={mode === value}
            onClick={() => choose(value)}
          >
            {value === "login" ? "تسجيل الدخول" : "حساب جديد"}
          </Button>
        ))}
      </div>

      {mode === "login" ? (
        <form
          key="login"
          noValidate
          onSubmit={onSubmit}
          className="flex flex-col gap-target-gap animate-in fade-in-0 duration-200 motion-reduce:animate-none"
        >
          <Field
            label="اسم الدخول"
            icon={Mail}
            name="username"
            type="email"
            inputMode="email"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <Field
            label="كلمة المرور"
            icon={Lock}
            name="password"
            type={reveal ? "text" : "password"}
            autoComplete="current-password"
            enterKeyHint="go"
            maxLength={PASSWORD_MAX}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-target-gap">
            <Button type="submit" disabled={busy || unchanged} aria-busy={busy}>
              {busy ? (
                <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : (
                <LogIn className="rtl:-scale-x-100" aria-hidden="true" />
              )}
              ادخل
            </Button>
            {/* زرّ تبديلٍ بتسميةٍ ثابتة: الحالة في aria-pressed وحدها (ARIA APG). */}
            <Button variant="secondary" aria-pressed={reveal} onClick={() => setReveal((shown) => !shown)}>
              {reveal ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
              أظهر كلمة المرور
            </Button>
          </div>
          <p role="alert" className="min-h-[1.6em] text-base text-destructive">
            {error && (
              <span key={attempt} className="inline-flex items-start gap-2">
                <AlertTriangle className="mt-1 size-5 shrink-0" aria-hidden="true" />
                {error}
              </span>
            )}
          </p>
        </form>
      ) : (
        <div key="signup" className="flex flex-col gap-target-gap animate-in fade-in-0 duration-200 motion-reduce:animate-none">
          <p className="text-lg leading-relaxed">
            خطوةٌ في كل شاشة، ولا يُرسَل شيءٌ قبل الأخيرة: الموافقة، ثم الاسم، وتاريخ الميلاد، والمهنة،
            والبريد، ثم كلمة المرور.
          </p>
          {onStartSignup ? (
            <Button width="full" onClick={onStartSignup}>
              <UserPlus aria-hidden="true" />
              ابدأ التسجيل
            </Button>
          ) : (
            <p className="text-base leading-relaxed text-muted-foreground">
              التسجيل الآن برابطٍ يصلك ممّن يدير التطبيق: افتح الرابط ليبدأ.
            </p>
          )}
        </div>
      )}
    </section>
  )
}
