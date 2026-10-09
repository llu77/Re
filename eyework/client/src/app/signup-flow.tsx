/*
 * التسجيل، شاشةً شاشة
 * ===================
 * منقولٌ من static/portal.js بمكوّنات التصميم الجديد: الإشعار بشاشتيه، ثم «كيف تستخدم
 * الجهاز؟»، ثم الاسم، ثم تاريخ الميلاد بأزرارٍ لا بكتابة (سنواتٌ وأشهرٌ وأيامٌ جاهزة وخطوة
 * «أقدم/أحدث»)، ثم المهنة، ثم البريد، ثم المراجعة، ثم كلمة المرور. البيانات في الذاكرة
 * (lib/store) ولا تُرسل إلا في الأخيرة؛ وقبل الخطوة الأولى يُسأل الخادم عن الرمز (برابط) أو
 * عن فتح التسجيل (بلا رابط)، فلا يكتب أحدٌ ثماني شاشاتٍ بالنظر ليسمع في آخرها أن اليوم اكتمل.
 * وما يرفضه الخادم في الأخيرة يعود برمز حقله فتُفتح خطوته وعليها رسالته.
 */

import * as React from "react"
import { Eye, EyeOff, UserPlus } from "lucide-react"

import { Redirect } from "@/components/redirect"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { Notice } from "@/components/ui/notice"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { api, detail, errorCode, errorField } from "@/lib/api"
import { go, reload } from "@/lib/router"
import {
  DAY_PRESETS, FIELD_SCREENS, MONTHS, MONTH_PRESETS, SCREEN_ORDER, SIGNUP_STEPS, STEP_LABELS, YEAR_PRESETS,
  birthDate, birthInFuture, birthWords, daysIn, dropImpossibleDay, emailIsValid, firstMissing, nameIsValid, newSignup,
  normalizeEmail, normalizeName, parentRoute, screenFromRoute, screenRoute, stepNumber, type SignupScreen, type SignupState,
} from "@/lib/signup"
import { toServer, useSize, writeSizeToUrl } from "@/lib/size"
import { getState, setState, useStore, type Choices } from "@/lib/store"
import { cn } from "@/lib/utils"
import { SignupSizeStep } from "@/screens/auth"
import { NoticeKeptScreen, NoticeSentScreen } from "@/screens/notice"

const STEPS = SIGNUP_STEPS.map((id) => ({ id, label: STEP_LABELS[id] }))
const LINK_INVALID = "رابط التسجيل غير صالح أو انتهى. اطلب رابطاً جديداً ممّن أعطاك إياه."

function update(patch: Partial<SignupState> | ((s: SignupState) => Partial<SignupState>)) {
  setState((current) => {
    if (!current.signup) return {}
    const next = typeof patch === "function" ? patch(current.signup) : patch
    return { signup: { ...current.signup, ...next } }
  })
}

/* ── إطار الخطوة ─────────────────────────────────────────────────── */

function StepFrame({ screen, title, hint, onBack, next, children }: {
  screen: SignupScreen
  title: string
  hint?: React.ReactNode
  onBack: () => void
  next: React.ReactNode
  children: React.ReactNode
}) {
  const { size } = useSize()
  return (
    <div className={cn("mx-auto flex w-full max-w-lg flex-col px-edge pb-safe pt-safe", size === "gaze" ? "h-dvh overflow-hidden" : "min-h-dvh")}>
      <header className="flex items-start justify-end gap-tg">
        <Button id="signup-back" icon={BackIcon} onClick={onBack}>
          رجوع
        </Button>
      </header>
      <main className="flex min-h-0 flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex flex-col gap-tg-min">
          <Stepper steps={STEPS} current={stepNumber(screen) - 1} variant="brief" />
          <h1 className="text-display font-bold leading-tight">{title}</h1>
          {hint ? <p className="text-flow text-muted-foreground gaze:short:hidden">{hint}</p> : null}
        </div>
        {children}
        <div className="mt-auto flex flex-col gap-tg">{next}</div>
      </main>
    </div>
  )
}

function NextButton({ id, label = "التالي", disabled = false, onClick, form }: {
  id: string
  label?: string
  disabled?: boolean
  onClick?: () => void
  form?: string
}) {
  return (
    <Button id={id} type={form ? "submit" : "button"} form={form} variant="secondary" size="lg" width="full" iconEnd={NextIcon} disabled={disabled} onClick={onClick}>
      {label}
    </Button>
  )
}

/* ── الاسم ───────────────────────────────────────────────────────── */

function NameStep({ s, nameMax, onBack }: { s: SignupState; nameMax: number; onBack: () => void }) {
  const [value, setValue] = React.useState(s.name)
  const [error, setError] = React.useState<string | null>(null)
  function submit(event: React.FormEvent) {
    event.preventDefault()
    const name = normalizeName(value)
    if (!nameIsValid(name, nameMax)) {
      setError(`الاسم: حروفٌ عربية أو لاتينية فقط، حتى ${nameMax} حرفاً.`)
      return
    }
    update({ name })
    go(screenRoute("year"))
  }
  return (
    <StepFrame screen="name" title="الاسم الذي يناديك به سيمبول" onBack={onBack} next={<NextButton id="signup-name-next" form="signup-name-form" />}>
      <form id="signup-name-form" noValidate onSubmit={submit} className="flex flex-col gap-tg">
        <Field label={`الاسم الأول يكفي، حتى ${nameMax} حرفاً`} error={error ?? undefined}>
          <Input id="signup-name-input" type="text" autoComplete="given-name" autoCapitalize="words" enterKeyHint="next" maxLength={60} value={value} onChange={(event) => setValue(event.target.value)} />
        </Field>
      </form>
    </StepFrame>
  )
}

/* ── تاريخ الميلاد: سنة، شهر، يوم ───────────────────────────────── */

function DateStep({ s, kind, earliest, onBack }: { s: SignupState; kind: "year" | "month" | "day"; earliest: number; onBack: () => void }) {
  const value = s[kind]
  const year = new Date().getFullYear()
  const [min, max] = kind === "year" ? [earliest, year] : kind === "month" ? [1, 12] : [1, s.year !== null && s.month !== null ? daysIn(s.year, s.month) : 31]
  const presets = (kind === "year" ? YEAR_PRESETS : kind === "month" ? MONTH_PRESETS : DAY_PRESETS).filter((n) => n >= min && n <= max)
  const base = value ?? (kind === "year" ? 1990 : kind === "month" ? 6 : 15)
  const words = (n: number) => (kind === "month" ? MONTHS[n - 1] : String(n))
  const title = kind === "year" ? "سنة الميلاد" : kind === "month" ? "شهر الميلاد" : "يوم الميلاد"
  const future = kind === "day" && birthInFuture(s)
  const nextScreen: SignupScreen = kind === "year" ? "month" : kind === "month" ? "day" : "profession"

  function pick(n: number) {
    const clamped = Math.min(max, Math.max(min, n))
    update((current) => dropImpossibleDay({ ...current, [kind]: clamped }))
  }

  return (
    <StepFrame
      screen={kind}
      title={title}
      hint={kind === "day" && future ? "تاريخ الميلاد لا يكون في المستقبل." : undefined}
      onBack={onBack}
      next={<NextButton id={`signup-${kind}-next`} disabled={value === null || future} onClick={() => go(screenRoute(nextScreen))} />}
    >
      <p id={`signup-${kind}-value`} aria-live="polite" className="num text-display font-bold text-heading">
        {value === null ? "—" : words(value)}
      </p>
      <div role="group" aria-label={kind === "year" ? "سنواتٌ جاهزة" : kind === "month" ? "أشهرٌ جاهزة" : "أيامٌ جاهزة"} id={`signup-${kind}-presets`} className="grid grid-cols-3 gap-tg">
        {presets.map((n) => (
          <Button key={n} className="chip" data-key={String(n)} aria-pressed={value === n} isValue onClick={() => pick(n)}>
            {words(n)}
          </Button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-tg">
        <Button id={`signup-${kind}-down`} isValue disabled={base <= min} onClick={() => pick(base - 1)}>
          {kind === "year" ? `أقدم: ${base - 1}` : kind === "month" ? `السابق: ${base > min ? MONTHS[base - 2] : ""}` : `السابق: ${base - 1}`}
        </Button>
        <Button id={`signup-${kind}-up`} isValue disabled={base >= max} onClick={() => pick(base + 1)}>
          {kind === "year" ? `أحدث: ${base + 1}` : kind === "month" ? `التالي: ${base < max ? MONTHS[base] : ""}` : `التالي: ${base + 1}`}
        </Button>
      </div>
    </StepFrame>
  )
}

/* ── المهنة ──────────────────────────────────────────────────────── */

function ProfessionStep({ s, choices, onBack }: { s: SignupState; choices: Choices; onBack: () => void }) {
  const { size } = useSize()
  const open = s.code === null
  const contact = choices.support_contact
  return (
    <StepFrame
      screen="profession"
      title="المهنة"
      hint={
        open ? (
          <>
            تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ إلى{" "}
            <bdi dir="ltr" className="num font-semibold text-foreground">
              {contact}
            </bdi>
            .
          </>
        ) : (
          "تُفتح بها بوابتك. تغييرها بعد التسجيل بطلبٍ ممّن أعطاك الرابط."
        )
      }
      onBack={onBack}
      next={<NextButton id="signup-profession-next" disabled={s.profession === null} onClick={() => go(screenRoute("email"))} />}
    >
      <RadioCards<string>
        label="المهن"
        value={s.profession}
        onValueChange={(profession) => update({ profession })}
        columns={1}
        ids={Object.fromEntries(choices.professions.map((p) => [p.code, `signup-profession-${p.code}`]))}
        // في الحجم الكبير الاسم وحده: ثلاث بطاقاتٍ بسطريها لا تتّسع مع «التالي» في أقصر إطار.
        options={choices.professions.map((p) => ({ value: p.code, title: p.name, description: size === "compact" ? p.tagline : undefined }))}
      />
    </StepFrame>
  )
}

/* ── البريد ──────────────────────────────────────────────────────── */

function EmailStep({ s, onBack }: { s: SignupState; onBack: () => void }) {
  const [value, setValue] = React.useState(s.email)
  const [error, setError] = React.useState<string | null>(null)
  function submit(event: React.FormEvent) {
    event.preventDefault()
    const email = normalizeEmail(value)
    if (!emailIsValid(email)) {
      setError("اكتب بريداً صالحاً بحروفٍ لاتينية.")
      return
    }
    update({ email })
    go(screenRoute("review"))
  }
  return (
    <StepFrame screen="email" title="البريد الإلكتروني" onBack={onBack} next={<NextButton id="signup-email-next" form="signup-email-form" />}>
      <form id="signup-email-form" noValidate onSubmit={submit} className="flex flex-col gap-tg">
        <Field label="يكون اسم دخولك" error={error ?? undefined}>
          <Input id="signup-email-input" dir="ltr" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" autoCorrect="off" spellCheck={false} enterKeyHint="next" value={value} onChange={(event) => setValue(event.target.value)} />
        </Field>
      </form>
    </StepFrame>
  )
}

/* ── المراجعة ────────────────────────────────────────────────────── */

function ReviewStep({ s, choices, onBack }: { s: SignupState; choices: Choices; onBack: () => void }) {
  const profession = choices.professions.find((p) => p.code === s.profession)?.name ?? ""
  const open = s.code === null
  return (
    <StepFrame screen="review" title="راجِع قبل كلمة المرور" onBack={onBack} next={<NextButton id="signup-review-next" label="التالي: كلمة المرور" onClick={() => go(screenRoute("password"))} />}>
      <dl className="flex flex-col gap-tg-min text-flow">
        <div className="flex gap-2"><dt className="text-muted-foreground">الاسم:</dt><dd id="signup-review-name" className="font-bold">{s.name}</dd></div>
        <div className="flex gap-2"><dt className="text-muted-foreground">تاريخ الميلاد:</dt><dd id="signup-review-birth" className="num font-bold">{birthWords(s)}</dd></div>
        <div className="flex gap-2"><dt className="text-muted-foreground">المهنة:</dt><dd id="signup-review-profession" className="font-bold">{profession}</dd></div>
        <div className="flex gap-2"><dt className="text-muted-foreground">اسم الدخول:</dt><dd><bdi id="signup-review-email" dir="ltr" className="num font-bold">{s.email}</bdi></dd></div>
      </dl>
      <p id="signup-email-help" className="text-small text-muted-foreground gaze:short:hidden">
        {open ? (
          <>
            لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به. إن نُسيت كلمة المرور فاكتب إلى{" "}
            <bdi dir="ltr" className="num font-semibold text-foreground">{choices.support_contact}</bdi> من هذا البريد.
          </>
        ) : (
          "لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به. إن نُسيت كلمة المرور فرابطٌ جديد ممّن أعطاك رابط التسجيل."
        )}
      </p>
    </StepFrame>
  )
}

/* ── كلمة المرور وإنشاء الحساب ───────────────────────────────────── */

function PasswordStep({ s, choices, onBack, onFailure }: {
  s: SignupState
  choices: Choices
  onBack: () => void
  onFailure: (message: string) => void
}) {
  const [password, setPassword] = React.useState("")
  const [reveal, setReveal] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const min = choices.registration.password_min

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busy || getState().busy) return
    if (password.length < min) {
      setError(`كلمة المرور من ${min} حرفاً على الأقل.`)
      return
    }
    setError(null)
    setBusy(true)
    setState({ busy: true })
    const body: Record<string, unknown> = {
      name: s.name, birth_date: birthDate(s), email: s.email, password, profession: s.profession, accept_terms: true,
      ui_size: toServer(s.use ?? "compact"), terms_version: choices.notice.version,
    }
    if (s.code !== null) body.code = s.code
    const result = await api("POST", "/api/auth/register", { json: body })
    setState({ busy: false })
    setBusy(false)
    if (result.status === 204) {
      setState({ signup: null })
      reload()
      return
    }
    if (errorCode(result) === "REGISTER_CODE") {
      setState({ signup: null, flash: detail(result) })
      go("#/login", { replace: true })
      return
    }
    const field = errorField(result)
    const screen = field ? FIELD_SCREENS[field] : undefined
    if (screen && screen !== "password") {
      update({ alert: detail(result) })
      go(screenRoute(screen))
      return
    }
    onFailure(detail(result))
  }

  // «أنشئ حسابي» في المحتوى بعد الحقلين، و«أظهر كلمة المرور» في الموضع الذي كان فيه «التالي: كلمة
  // المرور» في الشاشة السابقة: نظرةٌ باقية عليه بعد الانتقال تجد زرّاً آمناً لا ما ينشئ الحساب.
  return (
    <StepFrame
      screen="password"
      title="كلمة المرور"
      onBack={onBack}
      next={
        <Button id="signup-reveal" width="full" aria-pressed={reveal} icon={reveal ? EyeOff : Eye} onClick={() => setReveal((shown) => !shown)}>
          {reveal ? "أخفِ كلمة المرور" : "أظهر كلمة المرور"}
        </Button>
      }
    >
      <form id="signup-password-form" noValidate onSubmit={submit} className="flex flex-col gap-tg">
        <Field label="اسم الدخول">
          <Input id="signup-password-login" dir="ltr" type="email" name="username" autoComplete="username" value={s.email} readOnly />
        </Field>
        <Field label={`كلمة مرورٍ جديدة، ${min} حرفاً على الأقل`} error={error ?? undefined}>
          <Input
            id="signup-password-input"
            dir="ltr"
            type={reveal ? "text" : "password"}
            name="password"
            autoComplete="new-password"
            minLength={min}
            maxLength={128}
            enterKeyHint="done"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Button id="signup-create" type="submit" variant="primary" size="lg" width="full" commit icon={UserPlus} busy={busy}>
          أنشئ حسابي
        </Button>
      </form>
    </StepFrame>
  )
}

/* ── المسار ─────────────────────────────────────────────────────── */

export function SignupFlow({ path, choices }: { path: string; choices: Choices }) {
  const signup = useStore((state) => state.signup)
  const { size, setSize } = useSize()
  const [notice, setNotice] = React.useState<string | null>(null)
  const checking = React.useRef(false)
  const open = choices.registration.mode === "open"
  const screen = screenFromRoute(path)
  const nameMax = choices.registration.name_max

  // إعادة تحميلٍ بعد محو الرابط: في الوضع المفتوح تسجيلٌ بلا رابط من أوّله.
  React.useEffect(() => {
    if (!signup && open) setState({ signup: newSignup(null) })
  }, [signup, open])

  // قبل الخطوة الأولى: هل يُنشأ حسابٌ الآن؟ (بلا رابط) أو هل الرمز صالح؟ (برابط).
  React.useEffect(() => {
    if (!signup || signup.checked || checking.current) return
    checking.current = true
    const request = signup.code === null
      ? api("GET", "/api/auth/registration")
      : api("POST", "/api/auth/signup-code", { json: { code: signup.code } })
    void request.then((result) => {
      checking.current = false
      if (result.status === 204) {
        update({ checked: true })
        return
      }
      const message = signup.code !== null && result.status === 422 ? LINK_INVALID : detail(result)
      if (signup.code === null || [403, 410, 422].includes(result.status)) {
        // لا يُنشأ حسابٌ الآن (اكتمل اليوم أو حدٌّ أو تغيّر الوضع)، أو رمزٌ لا يصلح: يُقال على شاشة الدخول.
        setState({ signup: null, flash: message })
        go("#/login", { replace: true })
      } else {
        setNotice(`${message} «حسناً» تعيد المحاولة.`)
      }
    })
  }, [signup])

  // رسالة الخادم عن حقلٍ تُعرض على خطوته بعد رسمها.
  React.useEffect(() => {
    if (signup?.alert) {
      setNotice(signup.alert)
      update({ alert: null })
    }
  }, [signup?.alert])

  if (!signup) {
    return open ? null : (
      <Notice message="افتح رابط التسجيل من جديد." onAck={() => go("#/login", { replace: true })}>
        <span />
      </Notice>
    )
  }
  if (!signup.checked) {
    return (
      <Notice message={notice} onAck={() => { setNotice(null); update({ checked: false }) }}>
        <span />
      </Notice>
    )
  }
  const missing = firstMissing(signup, nameMax)
  if (missing !== null && SCREEN_ORDER.indexOf(screen) > SCREEN_ORDER.indexOf(missing)) {
    return <Redirect to={screenRoute(missing)} />
  }
  const back = () => go(parentRoute(screen))

  let content: React.ReactNode
  switch (screen) {
    case "kept":
      content = <NoticeKeptScreen notice={choices.notice} onNext={() => go(screenRoute("sent"))} onBack={() => go("#/login")} />
      break
    case "sent":
      content = (
        <NoticeSentScreen
          notice={choices.notice}
          scope={null}
          onAgree={() => {
            update({ agreed: true })
            go(screenRoute("use"))
          }}
          onBack={back}
        />
      )
      break
    case "use":
      content = (
        <SignupSizeStep
          step={0}
          steps={STEPS}
          value={signup.use ?? size}
          choices={choices.ui_sizes.map((choice) => ({ code: choice.code, name: choice.name, line: choice.detail }))}
          onNext={(mode) => {
            update({ use: mode })
            setSize(mode)
            writeSizeToUrl(mode)
            go(screenRoute("name"))
          }}
          onBack={back}
        />
      )
      break
    case "name":
      content = <NameStep s={signup} nameMax={nameMax} onBack={back} />
      break
    case "year":
    case "month":
    case "day":
      content = <DateStep s={signup} kind={screen} earliest={choices.registration.earliest_year} onBack={back} />
      break
    case "profession":
      content = <ProfessionStep s={signup} choices={choices} onBack={back} />
      break
    case "email":
      content = <EmailStep s={signup} onBack={back} />
      break
    case "review":
      content = <ReviewStep s={signup} choices={choices} onBack={back} />
      break
    default:
      content = <PasswordStep s={signup} choices={choices} onBack={back} onFailure={setNotice} />
  }
  return (
    <Notice message={notice} onAck={() => setNotice(null)}>
      {content}
    </Notice>
  )
}
