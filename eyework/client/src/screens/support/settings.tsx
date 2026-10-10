/*
 * إعدادات الدعم
 * =============
 * التوقيع في آخر كل ردّ (لا يُرسل إلى سيمبول)، وأهداف زمن الخدمة لكل أولوية (أول ردٍّ والحلّ)، واستعمال سيمبول
 * اليوم، وإشعار المكتب والنسخة التي وافقتَ عليها. في الحجم الكبير قسمٌ واحد في الشاشة.
 */

import * as React from "react"
import { Save, ShieldCheck } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { Tabs } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/toast"
import { PRIORITIES, PRIORITY, SLA_FIRST, SLA_RESOLVE, USAGE_KIND, type Priority, type Settings } from "@/lib/support"
import { useSize } from "@/lib/size"
import { GazeHost, Picker } from "@/screens/inventory/common"

import type { Fail } from "./common"

type Section = "signature" | "sla" | "usage"

export function SettingsScreen({ settings, onSave, onNotice, onBack }: {
  settings: Settings
  onSave: (body: { signature?: string | null; sla?: Partial<Settings["sla"]> }) => Promise<Fail>
  onNotice: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const toast = useToast()
  const [section, setSection] = React.useState<Section>("signature")
  const [signature, setSignature] = React.useState(settings.signature ?? "")
  const [sla, setSla] = React.useState(settings.sla)
  const [priority, setPriority] = React.useState<Priority>("URGENT")
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)

  async function save(id: string, body: { signature?: string | null; sla?: Partial<Settings["sla"]> }) {
    setBusy(id)
    setFail(null)
    const result = await onSave(body)
    setBusy(null)
    setFail(result)
    if (!result) toast.show({ title: "حُفظت الإعدادات", tone: "success" })
  }

  const signatureBlock = (
    <div className="flex flex-col gap-tg">
      <Field label="التوقيع" hint={gaze ? undefined : "في آخر كل ردّ، سطرٌ واحد. مثلاً: فريق الدعم الفني."} error={fail?.field === "signature" ? fail.message : null}>
        <Input id="settings-signature" autoComplete="off" maxLength={60} value={signature} onChange={(event) => setSignature(event.target.value)} />
      </Field>
      <Button id="settings-save-signature" variant="primary" icon={Save} busy={busy === "signature"} onClick={() => void save("signature", { signature: signature.trim() || null })} className="self-start gaze:w-full">
        احفظ التوقيع
      </Button>
    </div>
  )

  const target = (p: Priority) => (
    <div key={p} className="grid grid-cols-2 gap-tg">
      <Picker id={`settings-first-${p}`} label={gaze ? "أول ردّ خلال" : `${PRIORITY[p]}: أول ردّ خلال`}
        options={Object.entries(SLA_FIRST).map(([value, label]) => ({ value, label }))} value={String(sla[p].first_reply_minutes)}
        onValueChange={(value) => setSla({ ...sla, [p]: { ...sla[p], first_reply_minutes: Number(value) } })} />
      <Picker id={`settings-resolve-${p}`} label={gaze ? "الحلّ خلال" : `${PRIORITY[p]}: الحلّ خلال`}
        options={Object.entries(SLA_RESOLVE).map(([value, label]) => ({ value, label }))} value={String(sla[p].resolve_minutes)}
        onValueChange={(value) => setSla({ ...sla, [p]: { ...sla[p], resolve_minutes: Number(value) } })} />
    </div>
  )
  const slaBlock = (
    <div className="flex flex-col gap-tg">
      <GazeHost>
        {gaze ? (
          <>
            <Picker id="settings-priority" label="الأولوية" options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY[p] }))} value={priority} onValueChange={(value) => setPriority(value as Priority)} />
            {target(priority)}
          </>
        ) : PRIORITIES.map(target)}
      </GazeHost>
      <Button id="settings-save-sla" variant="primary" icon={Save} busy={busy === "sla"} onClick={() => void save("sla", { sla })} className="self-start gaze:w-full">
        احفظ الأهداف
      </Button>
    </div>
  )
  const usageBlock = (
    <div className="flex flex-col gap-tg">
      <ul aria-label="استعمال سيمبول اليوم" className="flex flex-col gap-1 text-flow">
        {settings.ai_usage.map((u) => (
          <li key={u.kind}>{USAGE_KIND[u.kind] ?? u.kind}: <span className="num">{u.used_today ?? 0}</span>{u.per_day === null ? "" : <> من <span className="num">{u.per_day}</span></>}</li>
        ))}
      </ul>
      <p className="text-small text-muted-foreground">{settings.notice.accepted ? `وافقتَ على إشعار المكتب (${settings.notice.accepted}).` : "لم توافق على إشعار المكتب بعد."}</p>
      <Button id="settings-notice" icon={ShieldCheck} onClick={onNotice} className="self-start gaze:w-full">
        إشعار المكتب
      </Button>
    </div>
  )
  const failAlert = fail && fail.field !== "signature" ? <Alert tone="danger" title="لم تُحفظ" live>{fail.message}</Alert> : null

  if (gaze) {
    return (
      <Screen title="إعدادات الدعم" actions={<><Button id="settings-prev" icon={BackIcon} onClick={onBack}>الرئيسية</Button><span aria-hidden="true" /></>}>
        <Tabs items={[{ id: "signature", label: "التوقيع" }, { id: "sla", label: "زمن الخدمة" }, { id: "usage", label: "الاستعمال والإشعار" }]} value={section} onValueChange={(id) => { setFail(null); setSection(id as Section) }} label="الإعدادات">
          {failAlert}
          {section === "signature" ? signatureBlock : section === "sla" ? slaBlock : usageBlock}
        </Tabs>
      </Screen>
    )
  }
  return (
    <Screen title="إعدادات الدعم" back={{ id: "settings-back", label: "الرئيسية", onClick: onBack }}>
      {failAlert}
      <section aria-label="التوقيع" className="flex flex-col gap-tg">{signatureBlock}</section>
      <section aria-labelledby="settings-sla-title" className="flex flex-col gap-tg">
        <h2 id="settings-sla-title" className="text-lead font-semibold">أهداف زمن الخدمة</h2>
        {slaBlock}
      </section>
      <section aria-labelledby="settings-usage-title" className="flex flex-col gap-tg">
        <h2 id="settings-usage-title" className="text-lead font-semibold">سيمبول اليوم</h2>
        {usageBlock}
      </section>
    </Screen>
  )
}
