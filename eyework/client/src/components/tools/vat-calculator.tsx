/*
 * حاسبة الضريبة
 * =============
 * مبلغٌ واحد، وهل هو قبل الضريبة أم شاملها، فتظهر الثلاثة: الصافي والضريبة والإجمالي.
 * النسبة من الخادم (/api/choices: `vat_rate_bp`)، والحساب بالهللة وبتقريب السطر نفسه الذي
 * يحسب به الخادم الفاتورة (lib/money.ts). ومهنةٌ تريد تقريب قاعدتها بعينه تمرّر `compute`
 * (المخزون: GET /api/inventory/tools/vat)، فيُعرض ما يردّه الخادم، والأحدث وحده.
 * «انسخ» يضع الرقم في الحافظة بالضغط نفسه (Clipboard API تحتاج ضغطة المستخدم).
 * الترتيب: الحقل، ثم النتيجة، ثم «قبل الضريبة / شاملها»: ما يقع تحت موضع «حاسبة الضريبة» في
 * شبكة الأدوات بعد فتحها حقلٌ أو نصّ، لا خيارٌ يتغيّر بنظرةٍ باقية.
 */

import * as React from "react"
import { Copy } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { formatAmount, parseAmount, splitGross, vatOnNet } from "@/lib/money"

export type Basis = "net" | "gross"
export interface VatResult {
  net: number
  vat: number
  gross: number
}
export type VatCompute = (amount: number, basis: Basis) => Promise<VatResult | { error: string }>

/** الحساب في الواجهة: بالهللة، والتقريب نصفٌ إلى الأعلى كما في الخادم. */
export function computeVat(amount: number, basis: Basis, rateBp: number): VatResult {
  if (basis === "net") {
    const vat = vatOnNet(amount, rateBp)
    return { net: amount, vat, gross: amount + vat }
  }
  return { ...splitGross(amount, rateBp), gross: amount }
}

export function VatCalculator({ rateBp, compute, initial = "" }: { rateBp: number; compute?: VatCompute; initial?: string }) {
  const [text, setText] = React.useState(initial)
  const [basis, setBasis] = React.useState<Basis>("net")
  const [copied, setCopied] = React.useState<string | null>(null)
  const [remote, setRemote] = React.useState<VatResult | null>(null)
  const [failure, setFailure] = React.useState<string | null>(null)
  const latest = React.useRef(0)
  const amount = parseAmount(text)
  const invalid = text.trim() !== "" && amount === null
  const rate = `${rateBp / 100}%`

  // من الخادم: كل تغييرٍ طلب، والردّ الأحدث وحده يُعرض (لا مؤقّت يؤجّل الطلب).
  React.useEffect(() => {
    if (!compute || amount === null) {
      setRemote(null)
      return
    }
    const seq = ++latest.current
    void compute(amount, basis).then((answer) => {
      if (seq !== latest.current) return
      if ("error" in answer) {
        setRemote(null)
        setFailure(answer.error)
      } else {
        setRemote(answer)
        setFailure(null)
      }
    })
  }, [compute, amount, basis])

  const result = amount === null ? null : compute ? remote : computeVat(amount, basis, rateBp)

  async function copy(label: string, value: number) {
    try {
      await navigator.clipboard.writeText(formatAmount(value).replace(/,/g, ""))
      setCopied(`نُسخ ${label}.`)
    } catch {
      setCopied("لم يُسمح بالنسخ في هذا المتصفّح.")
    }
  }

  return (
    <div className="flex flex-col gap-tg">
      <Field label="المبلغ" error={invalid ? "اكتب مبلغاً مثل 1250 أو 1250.50." : null}>
        <Input
          numeric
          unit="ر.س"
          inputMode="decimal"
          autoComplete="off"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setCopied(null)
          }}
        />
      </Field>
      <dl aria-live="polite" className="grid grid-cols-3 gap-2 rounded-card bg-muted p-3 text-center">
        <div className="flex flex-col gap-0.5">
          <dt className="text-small text-muted-foreground">الصافي</dt>
          <dd className="num font-bold" dir="ltr">{result ? formatAmount(result.net) : "—"}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-small text-muted-foreground">الضريبة <span className="num">{rate}</span></dt>
          <dd className="num font-bold" dir="ltr">{result ? formatAmount(result.vat) : "—"}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-small text-muted-foreground">الإجمالي</dt>
          <dd className="num font-bold text-heading" dir="ltr">{result ? formatAmount(result.gross) : "—"}</dd>
        </div>
      </dl>
      <RadioCards<Basis>
        label="المبلغ المكتوب"
        gazeColumns={2}
        value={basis}
        onValueChange={(value) => {
          setBasis(value)
          setCopied(null)
        }}
        options={[
          { value: "net", title: "قبل الضريبة" },
          { value: "gross", title: "شامل الضريبة" },
        ]}
      />
      <div className="grid grid-cols-2 gap-tg gaze:grid-cols-1 gaze:short:hidden">
        <Button icon={Copy} disabled={!result} onClick={() => result && copy("الصافي", result.net)} className="gaze:hidden">
          انسخ الصافي
        </Button>
        <Button icon={Copy} disabled={!result} onClick={() => result && copy("الإجمالي", result.gross)}>
          انسخ الإجمالي
        </Button>
      </div>
      <p role="status" className="min-h-[1.45em] text-small text-success gaze:short:hidden">
        {copied}
      </p>
      {failure ? (
        <p role="alert" className="text-small font-medium text-destructive">
          {failure}
        </p>
      ) : null}
    </div>
  )
}
