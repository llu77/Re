/*
 * التسجيل، خطوةً خطوة، والبيانات في الذاكرة حتى الأخيرة (portal.js). هنا في النموذج:
 * «قبل أن تبدأ»، والاسم، وسنة الميلاد — بقية الخطوات على النمط نفسه (المواصفة).
 * «التالي» أسفل النهاية في كل خطوة: الموضع نفسه، والاعتماد الوحيد «أنشئ حسابي» في
 * الأخيرة داخل المحتوى.
 */
import * as React from "react"
import {
  ChevronLeft,
  ChevronRight,
  Database,
  Globe,
  Mail,
  Minus,
  Plus,
  ShieldCheck,
  Trash2,
  UserRound,
  type LucideIcon,
} from "lucide-react"

import { DwellArc } from "@/components/brand/dwell-arc"
import { ChoiceGroup, ValueDisplay } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, Step, TopBar } from "@/components/frame/screen"
import { Button } from "@/components/ui/button"
import { Callout } from "@/components/ui/callout"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SIGNUP_STEPS } from "@/lib/labels"
import { go } from "@/lib/router"
import { getState, setState, showAlert, useStore, type SignupState } from "@/lib/store"

const EMPTY: SignupState = { agreed: false, name: "", year: null, month: null, day: null, profession: null, email: "" }

function signup(): SignupState {
  return getState().signup ?? EMPTY
}

function patch(next: Partial<SignupState>) {
  setState({ signup: { ...signup(), ...next } })
}

function Back({ to }: { to: string }) {
  return (
    <Button icon={ChevronRight} data-back="" onClick={() => go(to)}>
      رجوع
    </Button>
  )
}

function Progress({ step }: { step: (typeof SIGNUP_STEPS)[number] }) {
  const n = SIGNUP_STEPS.indexOf(step) + 1
  return (
    <Step arc={<DwellArc value={n} total={SIGNUP_STEPS.length} />}>
      الخطوة {n} من {SIGNUP_STEPS.length}
    </Step>
  )
}

const NOTICE: { icon: LucideIcon; text: string }[] = [
  { icon: Database, text: "يُحفظ: الاسم، وتاريخ الميلاد، والمهنة، وكلمة المرور مجزّأةً لا نصّاً." },
  { icon: Mail, text: "البريد لا يُحفظ، بل بصمةٌ منه للدخول: لا يصله شيء، ولا يُستردّ الحساب به." },
  {
    icon: Globe,
    text: "يُرسَل إلى مزوّد النموذج (Anthropic) خارج المملكة نصُّ ما تطلبه من سيمبول وصورة المنتج، لا اسمك ولا تاريخ ميلادك، ويحذفها خلال 30 يوماً إلا ما تُبقيه سياسته أو القانون.",
  },
  { icon: Trash2, text: "تحذف حسابك وبياناته متى شئت من «حسابي». والنسخ الاحتياطية الأقدم تبقى حتى تُحذف." },
]

export function SignupNotice() {
  return (
    <Screen name="signup-notice">
      <TopBar start={<Back to="#/welcome" />} step="قبل أن تبدأ" />
      <Content>
        <h2 tabIndex={-1} className="text-title">
          ما يُحفظ وما يُرسل
        </h2>
        <ul className="flex flex-col gap-2">
          {NOTICE.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3">
              <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                <Icon aria-hidden="true" strokeWidth={2.25} className="size-[1.1rem]" />
              </span>
              <p className="line text-small leading-relaxed">{text}</p>
            </li>
          ))}
        </ul>
      </Content>
      <BottomBar
        end={
          <Button
            id="signup-agree"
            variant="secondary"
            iconEnd={ChevronLeft}
            onClick={() => {
              patch({ agreed: true })
              go("#/signup/name")
            }}
          >
            أوافق وأتابع
          </Button>
        }
      />
    </Screen>
  )
}

/* الاسم كما يفحصه الخادم (auth.check_name): مسافاتٌ مفردة، و«ی/ک» عربية. */
function normalizeName(raw: string): string {
  return raw.replace(/ی/g, "ي").replace(/ک/g, "ك").replace(/\s+/g, " ").trim()
}

function nameIsValid(name: string, max: number): boolean {
  return name.length > 0 && name.length <= max && /^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$/.test(name)
}

export function SignupName() {
  const field = React.useRef<HTMLInputElement>(null)
  const max = useStore((s) => s.choices?.registration.name_max ?? 30)

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const name = normalizeName(field.current?.value ?? "")
    if (!nameIsValid(name, max)) {
      showAlert("signup-name", `الاسم: حروفٌ عربية أو لاتينية فقط، حتى ${max} حرفاً.`)
      return
    }
    patch({ name })
    go("#/signup/year")
  }

  return (
    <Screen name="signup-name">
      <TopBar start={<Back to="#/signup" />} step={<Progress step="name" />} />
      <Content as="form" id="signup-name-form" onSubmit={onSubmit}>
        <h2 tabIndex={-1} className="text-title">
          ما الاسم الذي يناديك به سيمبول؟
        </h2>
        <div className="flex flex-col gap-1">
          <Label htmlFor="signup-name-input">الاسم الأول يكفي، حتى {max} حرفاً</Label>
          <Input
            ref={field}
            id="signup-name-input"
            type="text"
            icon={UserRound}
            defaultValue={signup().name}
            autoComplete="given-name"
            autoCapitalize="words"
            enterKeyHint="next"
            maxLength={60}
            required
          />
        </div>
        <Callout icon={ShieldCheck} variant="plain" className="mt-1">
          يظهر الاسم في تحيّة سيمبول وحدها، ولا يُرسل إلى مزوّد النموذج.
        </Callout>
      </Content>
      <BottomBar
        end={
          <Button
            id="signup-name-next"
            type="submit"
            form="signup-name-form"
            variant="secondary"
            iconEnd={ChevronLeft}
          >
            التالي
          </Button>
        }
      />
    </Screen>
  )
}

const YEAR_PRESETS = [1960, 1970, 1980, 1990, 2000, 2010]

export function SignupYear() {
  const year = useStore((s) => s.signup?.year ?? null)
  const earliest = useStore((s) => s.choices?.registration.earliest_year ?? 1900)
  const latest = new Date().getFullYear()
  const down = year === null || year - 1 < earliest ? null : year - 1
  const up = year === null || year + 1 > latest ? null : year + 1
  return (
    <Screen name="signup-year">
      <TopBar start={<Back to="#/signup/name" />} step={<Progress step="year" />} />
      <Content>
        <h2 tabIndex={-1} className="text-title">
          سنة الميلاد
        </h2>
        <ValueDisplay
          id="signup-year-value"
          digits={year === null ? null : String(year)}
          words={year === null ? "" : `سنة الميلاد: ${year}`}
          empty="لم تُحدَّد السنة بعد."
        />
        <ChoiceGroup
          id="signup-year-presets"
          label="سنواتٌ جاهزة"
          columns={3}
          options={YEAR_PRESETS.filter((v) => v >= earliest && v <= latest).map((v) => ({ value: v, label: String(v) }))}
          selected={year}
          onPick={(value) => patch({ year: value })}
        />
        <div className="spaced grid flex-none grid-cols-2 gap-gap">
          <Button
            id="signup-year-down"
            icon={Minus}
            disabled={down === null}
            onClick={() => down !== null && patch({ year: down })}
          >
            {down === null ? "أقدم" : `أقدم: ${down}`}
          </Button>
          <Button id="signup-year-up" icon={Plus} disabled={up === null} onClick={() => up !== null && patch({ year: up })}>
            {up === null ? "أحدث" : `أحدث: ${up}`}
          </Button>
        </div>
      </Content>
      <BottomBar
        end={
          <Button
            id="signup-year-next"
            variant="secondary"
            iconEnd={ChevronLeft}
            disabled={year === null}
            onClick={() => go("#/signup/month")}
          >
            التالي
          </Button>
        }
      />
    </Screen>
  )
}
