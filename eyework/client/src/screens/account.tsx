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
 * الحجم العادي: صفحةٌ واحدة. الحجم الكبير: «حسابي» قائمة أزرار، و«حجم الواجهة» شاشتها
 * (لا تتّسع الثلاث بلا تمرير في 635px)، والشرح فيها فوق البطاقتين: ما يقع تحت موضع زرّ
 * «حجم الواجهة» بعد فتحها نصٌّ لا خيار.
 */

import * as React from "react"
import { BookOpen, Check, Hand, LogOut, ScanEye, Trash2 } from "lucide-react"

import { Screen, ScreenActions } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RadioCards } from "@/components/ui/radio-cards"
import { useSize, type SizeMode } from "@/lib/size"

export interface AccountProps {
  name: string | null
  profession: string
  /** «باللمس» و«بتتبّع العين» من /api/choices (`ui_sizes`). */
  sizeNames: Record<SizeMode, string>
  /** يرسل الحجم إلى الخادم؛ رسالة الخطأ أو null. */
  saveSize: (mode: SizeMode) => Promise<string | null>
  onSources: () => void
  onLogout: () => void
  onDelete: () => void
  initialChoice?: SizeMode
  /** الحجم الكبير: القائمة أو شاشة الحجم. */
  initialView?: "menu" | "size"
}

export function AccountScreen({
  name, profession, sizeNames, saveSize, onSources, onLogout, onDelete, initialChoice, initialView = "menu",
}: AccountProps) {
  const { size, setSize } = useSize()
  const gaze = size === "gaze"
  const [choice, setChoice] = React.useState<SizeMode>(initialChoice ?? size)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [applied, setApplied] = React.useState(false)
  const [view, setView] = React.useState<"menu" | "size">(initialView)

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
      <span className="flex size-12 shrink-0 items-center justify-center rounded-pill bg-primary text-title font-bold text-primary-foreground gaze:size-14">
        {initial ?? "؟"}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="truncate text-title font-bold text-heading">{name ?? "بلا اسم"}</p>
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
        { value: "compact", title: size === "compact" ? `${SIZE_NAMES.compact} (الحالية)` : SIZE_NAMES.compact, icon: Hand },
        { value: "gaze", title: size === "gaze" ? `${SIZE_NAMES.gaze} (الحالية)` : SIZE_NAMES.gaze, icon: ScanEye },
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
      className="gaze:w-full"
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

  if (gaze && view === "size") {
    return (
      <Screen
        title="طريقة الاستخدام"
        actions={
          <Button icon={BackIcon} onClick={() => setView("menu")}>
            حسابي
          </Button>
        }
      >
        <p className="text-flow text-muted-foreground">الحالية: {SIZE_NAMES[size]}. تُحفظ مع حسابك، وتُفتح بها البوابة على كل جهاز.</p>
        {choices}
        {failure}
        {applyButton}
      </Screen>
    )
  }

  if (gaze) {
    return (
      <Screen title="حسابي" actions={leaving}>
        {profile}
        <section aria-label="الحساب" className="grid grid-cols-2 gap-tg">
          <Button id="account-size" icon={ScanEye} onClick={() => setView("size")} className="col-span-2 justify-between">
            <span>طريقة الاستخدام</span>
            <span className="font-normal text-muted-foreground">{SIZE_NAMES[size]}</span>
          </Button>
          {sources}
        </section>
      </Screen>
    )
  }

  return (
    <Screen title="حسابي">
      {profile}
      <Card as="section" aria-labelledby="size-title">
        <CardHeader>
          <CardTitle id="size-title">طريقة الاستخدام</CardTitle>
          <CardDescription>الحالية: {SIZE_NAMES[size]}. تُحفظ مع حسابك، ولا تُرسَل إلى مزوّد النموذج.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-tg">
          {choices}
          {failure}
          <div className="flex flex-wrap items-center gap-tg">
            {applyButton}
            <p role="status" className="text-small text-muted-foreground">
              {applied ? "حُفظت في حسابك." : "تُحفظ في حسابك لا في هذا الجهاز."}
            </p>
          </div>
        </CardContent>
      </Card>
      <section aria-label="الحساب" className="grid grid-cols-2 gap-tg tablet:grid-cols-3">
        {sources}
      </section>
      <ScreenActions>{leaving}</ScreenActions>
    </Screen>
  )
}
