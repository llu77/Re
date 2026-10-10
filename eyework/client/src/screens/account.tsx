/*
 * حسابي
 * =====
 * الاسم والمهنة، و«طريقة الاستخدام» (الحجم)، والخروج، والحذف. لا شيء عن مفتاح المرور هنا: هو زرّ دخولٍ
 * وحده، والمتصفّح يحفظه بعد الدخول بكلمة المرور (قرار المالك).
 *
 * طريقة الاستخدام (registration_spec §8.8): البطاقتان تختاران ولا تطبّقان؛ «طبّق» يرسل PUT /api/me/ui-size،
 * وبعد ردّ الخادم يتبدّل الحجم كلّه (ردّ خادمٍ على ضغطة: مسموح). لماذا خطوتان؟ نظرةٌ عابرة على «عادي» من
 * حجمٍ كبير تصغّر الأهداف تحت من يحتاجها كبيرة؛ فالتبديل فعلٌ صريح بعد اختيار. والزرّ تحت البطاقتين، فما
 * يقع تحت موضعه بعد التبديل جزءٌ من البطاقة نفسها أو نصّ، لا زرٌّ يعتمد. والخروج والحذف في آخر الشاشة.
 *
 * باللمس صفحةٌ واحدة: صفّ الملف، ثم «طريقة الاستخدام» ببطاقتيها و«طبّق»، ثم صفّ الخروج والحذف في أسفل
 * الشاشة. وفي الحجم الكبير صفحتان (لا تتّسع واحدة في 320×635): «حسابي» بالاسم والمهنة سطراً تحت العنوان،
 * و«طريقة الاستخدام: …» وصفّ الخروج والحذف؛ و«طريقة الاستخدام» بالبطاقتين و«طبّق» في أسفلها و«رجوع» في
 * أعلاها. والشاشة تملأ ما فوق الشريط في الحجمين (`fill`) فيقع «رجوع» في التأكيد على الزرّ الذي فُتح به.
 */

import * as React from "react"
import { Check, Hand, LogOut, ScanEye, SlidersHorizontal, Trash2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
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
  onLogout: () => void
  onDelete: () => void
  initialChoice?: SizeMode
}

export function AccountScreen({ name, profession, sizeNames, saveSize, onLogout, onDelete, initialChoice }: AccountProps) {
  const { size, setSize } = useSize()
  const gaze = size === "gaze"
  const [choice, setChoice] = React.useState<SizeMode>(initialChoice ?? size)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [applied, setApplied] = React.useState(false)
  // في الحجم الكبير صفحتان: «حسابي» بأزراره، و«طريقة الاستخدام» بالخيارين و«طبّق». الصفحة الواحدة
  // لا تتّسع في 320×635.
  const [sizePage, setSizePage] = React.useState(false)

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
    <div className="flex items-center gap-3 rounded-card bg-card p-pad shadow-card">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-pill bg-secondary text-lead font-semibold text-secondary-foreground">
        {initial ?? "؟"}
      </span>
      <div className="flex min-w-0 flex-col">
        <p className="truncate font-semibold text-heading">{name ?? "بلا اسم"}</p>
        <p className="truncate text-small text-muted-foreground">{profession}</p>
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

  if (gaze && sizePage) {
    // الخياران و«طبّق» في أسفل الصفحة، وموضع «طريقة الاستخدام» في «حسابي» (أعلاها) نصٌّ هنا لا خيار.
    return (
      <Screen
        title="طريقة الاستخدام"
        description={`الحالية: ${SIZE_NAMES[size]}`}
        back={{ id: "account-size-back", label: "رجوع", onClick: () => setSizePage(false) }}
        fill
      >
        <div className="mt-auto flex flex-col gap-tg">
          {choices}
          {failure}
          <div className="grid grid-cols-2 items-center gap-tg">
            {applyButton}
            <p role="status" className="text-small text-muted-foreground">
              {applied ? "حُفظت." : ""}
            </p>
          </div>
        </div>
      </Screen>
    )
  }

  if (gaze) {
    return (
      <Screen title="حسابي" description={`${name ?? "بلا اسم"} · ${profession}`} fill actions={leaving}>
        <Button id="account-size" width="full" icon={SlidersHorizontal} onClick={() => setSizePage(true)} className="justify-between">
          <span className="min-w-0 truncate">طريقة الاستخدام: {SIZE_NAMES[size]}</span>
        </Button>
      </Screen>
    )
  }

  return (
    <Screen title="حسابي" fill actions={leaving}>
      {profile}
      <section aria-labelledby="size-title" className="flex flex-col gap-tg">
        <h2 id="size-title" className="px-1 text-small font-medium text-muted-foreground">
          طريقة الاستخدام
        </h2>
        {choices}
        {failure}
        <div className="grid grid-cols-2 items-center gap-tg">
          {applyButton}
          <p role="status" className="text-small text-muted-foreground">
            {applied ? "حُفظت." : ""}
          </p>
        </div>
      </section>
    </Screen>
  )
}
