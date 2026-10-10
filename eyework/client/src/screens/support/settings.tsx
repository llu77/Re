/*
 * إعدادات الدعم
 * =============
 * التوقيع في آخر كل ردّ (لا يُرسل إلى سيمبول)، واتفاقية مستوى الخدمة لكل أولوية (زمن الردّ الأول وزمن الحلّ)، واستعمال سيمبول
 * اليوم، وإشعار المكتب والنسخة التي وافقتَ عليها. في الحجم الكبير قسمٌ واحد في الشاشة، ولكل أولويةٍ قسمها: هدفاها
 * عدّادان بقيمهما (أقصر/أطول، لا منتقٍ تنزل خياراته تحت الشاشة)، و«احفظ الأهداف» في الشريط.
 */

import * as React from "react"
import { CheckCircle2, Save, ShieldCheck } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button } from "@/components/ui/button"
import { ChoiceStepper } from "@/components/ui/choice-stepper"
import { Field, Input } from "@/components/ui/input"
import { PRIORITIES, PRIORITY, SLA_FIRST, SLA_RESOLVE, USAGE_KIND, type Priority, type Settings } from "@/lib/support"
import { useSize } from "@/lib/size"
import { GazeHost, GazeSlot, Picker } from "@/screens/inventory/common"

import type { Fail } from "./common"

type Section = "signature" | "sla" | "usage" | `sla-${Priority}`

/** المدد مرتّبةً من الأقصر: لعدّاد الحجم الكبير. */
function durations(labels: Record<number, string>): { value: number; label: string }[] {
  return Object.keys(labels).map(Number).sort((a, b) => a - b).map((minutes) => ({ value: minutes, label: labels[minutes] }))
}

export function SettingsScreen({ settings, onSave, onNotice, onBack }: {
  settings: Settings
  onSave: (body: { signature?: string | null; sla?: Partial<Settings["sla"]> }) => Promise<Fail>
  onNotice: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [section, setSection] = React.useState<Section>("signature")
  const [signature, setSignature] = React.useState(settings.signature ?? "")
  const [sla, setSla] = React.useState(settings.sla)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)

  // «حُفظت» سطرٌ تحت زرّ الحفظ لا إشعارٌ عائم: الإشعار يبقى حتى يُغلق ويغطّي أعلى الشاشة في الحجم الكبير.
  const [saved, setSaved] = React.useState<string | null>(null)
  async function save(id: string, body: { signature?: string | null; sla?: Partial<Settings["sla"]> }) {
    setBusy(id)
    setFail(null)
    setSaved(null)
    const result = await onSave(body)
    setBusy(null)
    setFail(result)
    if (!result) setSaved(id)
  }
  const savedLine = (id: string) => saved === id ? <p id="settings-saved" role="status" className="text-small font-semibold text-success">حُفظت الإعدادات.</p> : null

  const signatureBlock = (
    <div className="flex flex-col gap-tg">
      <Field label="التوقيع" error={fail?.field === "signature" ? fail.message : null}>
        <Input id="settings-signature" autoComplete="off" maxLength={60} value={signature} onChange={(event) => setSignature(event.target.value)} />
      </Field>
      <Button id="settings-save-signature" variant="primary" icon={Save} busy={busy === "signature"} onClick={() => void save("signature", { signature: signature.trim() || null })} className="self-start gaze:w-full">
        احفظ التوقيع
      </Button>
      {savedLine("signature")}
    </div>
  )

  const target = (p: Priority) => (
    <div key={p} className="grid grid-cols-2 gap-tg gaze:gap-x-6">
      <Picker id={`settings-first-${p}`} label={`${PRIORITY[p]}: زمن الردّ الأول`}
        options={Object.entries(SLA_FIRST).map(([value, label]) => ({ value, label }))} value={String(sla[p].first_reply_minutes)}
        onValueChange={(value) => setSla({ ...sla, [p]: { ...sla[p], first_reply_minutes: Number(value) } })} />
      <Picker id={`settings-resolve-${p}`} label={`${PRIORITY[p]}: زمن الحلّ`}
        options={Object.entries(SLA_RESOLVE).map(([value, label]) => ({ value, label }))} value={String(sla[p].resolve_minutes)}
        onValueChange={(value) => setSla({ ...sla, [p]: { ...sla[p], resolve_minutes: Number(value) } })} />
    </div>
  )
  // الحجم الكبير: أولويةٌ في كل قسم، وهدفاها عدّادان (حقلان بعنوانيهما بينهما 28).
  const gazeTargets = (p: Priority) => (
    <div className="flex flex-col gap-tg">
      <ChoiceStepper id={`settings-first-${p}`} label="زمن الردّ الأول" options={durations(SLA_FIRST)} value={sla[p].first_reply_minutes} prevLabel="أقصر" nextLabel="أطول"
        onChange={(minutes) => { setSaved(null); setSla({ ...sla, [p]: { ...sla[p], first_reply_minutes: minutes } }) }} />
      <ChoiceStepper id={`settings-resolve-${p}`} label="زمن الحلّ" options={durations(SLA_RESOLVE)} value={sla[p].resolve_minutes} prevLabel="أقصر" nextLabel="أطول"
        onChange={(minutes) => { setSaved(null); setSla({ ...sla, [p]: { ...sla[p], resolve_minutes: minutes } }) }} />
      {saved === "sla" ? <p role="status" className="sr-only">حُفظت الإعدادات.</p> : null}
    </div>
  )
  const saveSla = (
    <Button id="settings-save-sla" variant="primary" icon={gaze && saved === "sla" ? CheckCircle2 : Save} busy={busy === "sla"} onClick={() => void save("sla", { sla })} className="self-start gaze:w-full">
      {gaze && saved === "sla" ? "حُفظت الأهداف" : "احفظ الأهداف"}
    </Button>
  )
  const slaBlock = (
    <div className="flex flex-col gap-tg">
      <GazeHost>
        {PRIORITIES.map(target)}
        <GazeSlot id="settings-save-sla-slot" field={false}>
          {saveSla}
          {savedLine("sla")}
        </GazeSlot>
      </GazeHost>
    </div>
  )
  const usageBlock = (
    <div className="flex flex-col gap-tg">
      {/* بين النصّين 12 لا فجوة هدفين: فوق «إشعار المكتب» وحده فجوةٌ كاملة. */}
      <div className="flex flex-col gap-tg-min">
        <ul aria-label="استعمال سيمبول اليوم" className="flex flex-col gap-1 text-flow">
          {settings.ai_usage.map((u) => (
            <li key={u.kind}>{USAGE_KIND[u.kind] ?? u.kind}: <span className="num">{u.used_today ?? 0}</span>{u.per_day === null ? "" : <> من <span className="num">{u.per_day}</span></>}</li>
          ))}
        </ul>
        <p className="text-small text-muted-foreground">{settings.notice.accepted ? `وافقتَ على إشعار المكتب (${settings.notice.accepted}).` : "لم توافق على إشعار المكتب بعد."}</p>
      </div>
      <Button id="settings-notice" icon={ShieldCheck} onClick={onNotice} className="self-start gaze:w-full">
        إشعار المكتب
      </Button>
    </div>
  )
  const failAlert = fail && fail.field !== "signature" ? <Alert tone="danger" title="لم تُحفظ" live>{fail.message}</Alert> : null

  if (gaze) {
    // الأقسام تُقلَّب في مكانها (لا قائمةٌ تنفتح فوق المحتوى فيقع ما يُضبط تحت ضغطةٍ اختارت القسم).
    const priority = section.startsWith("sla-") ? (section.slice(4) as Priority) : null
    const sections: { value: Section; label: string }[] = [
      { value: "signature", label: "التوقيع" },
      ...PRIORITIES.map((p) => ({ value: `sla-${p}` as Section, label: `أهداف «${PRIORITY[p]}»` })),
      { value: "usage", label: "الاستعمال والإشعار" },
    ]
    return (
      <Screen title="إعدادات الدعم" actions={<><Button id="settings-prev" icon={BackIcon} onClick={onBack}>الرئيسية</Button>{priority ? saveSla : <span aria-hidden="true" />}</>}>
        <ChoiceStepper id="settings-section" label="الإعدادات" options={sections} value={section}
          onChange={(id) => { setFail(null); setSaved(null); setSection(id) }} />
        {failAlert}
        {section === "signature" ? signatureBlock : priority ? gazeTargets(priority) : usageBlock}
      </Screen>
    )
  }
  return (
    <Screen title="إعدادات الدعم" back={{ id: "settings-back", label: "الرئيسية", onClick: onBack }}>
      {failAlert}
      <section aria-label="التوقيع" className="flex flex-col gap-tg">{signatureBlock}</section>
      <section aria-labelledby="settings-sla-title" className="flex flex-col gap-tg">
        <h2 id="settings-sla-title" className="text-lead font-semibold">اتفاقية مستوى الخدمة</h2>
        {slaBlock}
      </section>
      <section aria-labelledby="settings-usage-title" className="flex flex-col gap-tg">
        <h2 id="settings-usage-title" className="text-lead font-semibold">سيمبول اليوم</h2>
        {usageBlock}
      </section>
    </Screen>
  )
}
