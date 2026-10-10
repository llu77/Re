/*
 * حسابي
 * =====
 * الاسم والمهنة، و«طريقة الاستخدام» (الحجم)، والمصادر، والخروج، والحذف. لا شيء عن مفتاح
 * المرور هنا: هو زرّ دخولٍ وحده، والمتصفّح يحفظه بعد الدخول بكلمة المرور (قرار المالك).
 * «المصادر» باقية: سيمبول يُسنَد بمهامّ المهنة المأخوذة من O*NET (professions.py) وقد يقتبس
 * منها في جوابه، فيبقى إشعار O*NET (CC BY 4.0) على بعد ضغطة.
 *
 * طريقة الاستخدام (registration_spec §8.8): البطاقتان تختاران ولا تطبّقان؛ «طبّق» يرسل
 * PUT /api/me/ui-size، وبعد
 * ردّ الخادم يتبدّل الحجم كلّه (ردّ خادمٍ على ضغطة: مسموح). لماذا خطوتان؟ نظرةٌ عابرة على
 * «عادي» من حجمٍ كبير تصغّر الأهداف تحت من يحتاجها كبيرة؛ فالتبديل فعلٌ صريح بعد اختيار.
 * والزرّ في أسفل بطاقته والبطاقتان فوقه، فما يقع تحت موضعه بعد التبديل جزءٌ من البطاقة
 * نفسها أو نصّ، لا زرٌّ يعتمد (يقيسه tools/shoot.py). والخروج والحذف في آخر الشاشة.
 *
 * تخطيطٌ واحد للحجمين (الحزمة 2ج): صفّ الملف، ثم بطاقة «طريقة الاستخدام» ببطاقتيها الراديويتين
 * و«طبّق»، ثم «المصادر»، ثم صفّ الخروج والحذف في أسفل الشاشة. في الحجم الكبير عشرة أهدافٍ مع شريط
 * التبويب. والشاشة تملأ ما فوق الشريط في الحجم العادي أيضاً (`fill`) فيقع «رجوع» في التأكيد على
 * الزرّ الذي فُتح به لا على خيارٍ فوقه.
 */

import * as React from "react"
import { BookOpen, Check, Hand, LogOut, ScanEye, Trash2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { RadioCards } from "@/components/ui/radio-cards"
import { useSize, type SizeMode } from "@/lib/size"

export interface AccountProps {
  name: string | null
  profession: string
  /** «باللمس» و«بالعين أو بالرأس» من /api/choices (`ui_sizes`). */
  sizeNames: Record<SizeMode, string>
  /** يرسل الحجم إلى الخادم؛ رسالة الخطأ أو null. */
  saveSize: (mode: SizeMode) => Promise<string | null>
  onSources: () => void
  onLogout: () => void
  onDelete: () => void
  initialChoice?: SizeMode
}

export function AccountScreen({ name, profession, sizeNames, saveSize, onSources, onLogout, onDelete, initialChoice }: AccountProps) {
  const { size, setSize } = useSize()
  const gaze = size === "gaze"
  const [choice, setChoice] = React.useState<SizeMode>(initialChoice ?? size)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [applied, setApplied] = React.useState(false)

  async function apply() {
    setBusy(true)
    setError(null)
    const message = await saveSize(choice)
    setBusy(false)
    if (message) {
      setError(message)
      return
    }
    setSize(choice)
    setApplied(true)
  }

  const initial = name?.trim()?.[0] ?? null
  const SIZE_NAMES = sizeNames

  const profile = (
    <div className="flex items-center gap-3">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-pill bg-primary text-lead font-semibold text-primary-foreground gaze:size-12">
        {initial ?? "؟"}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="truncate text-lead font-semibold text-heading">{name ?? "بلا اسم"}</p>
        <Badge tone="info" className="self-start">
          المهنة: {profession}
        </Badge>
      </div>
    </div>
  )

  const choices = (
    <RadioCards<SizeMode>
      label="طريقة الاستخدام"
      value={choice}
      onValueChange={(value) => {
        setChoice(value)
        setApplied(false)
      }}
      options={[
        { value: "compact", title: SIZE_NAMES.compact, icon: Hand },
        { value: "gaze", title: SIZE_NAMES.gaze, icon: ScanEye },
      ]}
    />
  )

  const applyButton = (
    <Button
      id="account-ui-size-apply"
      variant="secondary"
      commit
      icon={Check}
      busy={busy}
      disabled={choice === size}
      onClick={() => void apply()}
    >
      طبّق
    </Button>
  )

  const failure = error ? (
    <Alert tone="danger" title="لم تُحفظ" live>
      {error}
    </Alert>
  ) : null

  const sources = (
    <Button id="account-sources" icon={BookOpen} onClick={onSources}>
      المصادر
    </Button>
  )
  // الخروج والحذف في شريط الإجراءات الأسفل، الحذف في البداية والخروج في النهاية: شاشة التأكيد تضع
  // «رجوع» في الخانة نفسها، فأقرب ما إلى نظرٍ باقٍ على الضغطة لا يعتمد شيئاً (كما في الواجهة القائمة).
  const leaving = (
    <div className="grid w-full grid-cols-2 gap-tg">
      <Button id="account-delete" variant="danger-outline" icon={Trash2} onClick={onDelete}>
        احذف حسابي
      </Button>
      <Button id="account-logout" icon={LogOut} onClick={onLogout}>
        تسجيل الخروج
      </Button>
    </div>
  )

  return (
    <Screen title="حسابي" fill actions={leaving}>
      {profile}
      <section aria-labelledby="size-title" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad shadow-card">
        <div className="flex flex-col gap-0.5">
          <h2 id="size-title" className="text-lead font-semibold text-heading">
            طريقة الاستخدام
          </h2>
          <p className="text-small text-muted-foreground">
            الحالية: {SIZE_NAMES[size]}. تُحفظ مع حسابك{gaze ? "." : "، ولا تُرسَل إلى مزوّد النموذج."}
          </p>
        </div>
        {choices}
        {failure}
        <div className="grid grid-cols-2 items-center gap-tg">
          {applyButton}
          <p role="status" className="text-small text-muted-foreground">
            {applied ? "حُفظت في حسابك." : "تُحفظ في حسابك لا في هذا الجهاز."}
          </p>
        </div>
      </section>
      <section aria-label="الحساب" className="grid grid-cols-2 gap-tg">
        {sources}
      </section>
    </Screen>
  )
}
