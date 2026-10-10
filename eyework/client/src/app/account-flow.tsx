/*
 * حسابي والخروج والحذف
 * ====================
 * الخروج بخطوتين كالحذف (الدخول من جديد بالنظر أغلى خطوةٍ في التطبيق)، والحذف بخطوتين ولا
 * يُسترجع شيء. طريقة الاستخدام تُحفظ بـPUT /api/me/ui-size ثم يتبدّل الحجم. لا «مصادر»: سيمبول
 * لا يُسنَد بمحتوى O*NET في هذه الواجهة (assistant_prompt.py)، فلا نسبة تُعرض.
 */

import * as React from "react"
import { LogOut, Trash2 } from "lucide-react"

import { chatApi, navigate, workspaceOf } from "@/app/workspace"
import { Wordmark } from "@/components/brand/marks"
import { Screen } from "@/components/shell/screen"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import { BackIcon, Button } from "@/components/ui/button"
import { Notice } from "@/components/ui/notice"
import { api, detail } from "@/lib/api"
import { refreshMe } from "@/lib/session"
import { go, reload } from "@/lib/router"
import { toServer, type SizeMode } from "@/lib/size"
import type { Choices, Me } from "@/lib/store"
import { AccountScreen } from "@/screens/account"

function ConfirmScreen({ title, question, text, label, icon, onYes, onBack, busy, backSlot }: {
  title: string
  question: string
  /** ما لا يُستعاد بعد التأكيد، سطراً واحداً؛ ولا شيء حيث لا يضيع شيء. */
  text?: string
  label: string
  icon: typeof LogOut
  onYes: () => void
  onBack: () => void
  busy: boolean
  /** خانة «رجوع» في شريط الإجراءات: خانة الزرّ الذي ضُغط في «حسابي» (الحذف في البداية والخروج في النهاية). */
  backSlot: "start" | "end"
}) {
  // التأكيد في المحتوى و«رجوع» في الخانة التي ضُغط فيها الزرّ في «حسابي»: ما يقع تحت نظرٍ باقٍ
  // على الضغطة «رجوع»، وأقرب ما إليه «رجوع»، لا ما يعتمد (كما في الواجهة القائمة).
  const back = (
    <Button id="account-confirm-back" icon={BackIcon} onClick={onBack}>
      رجوع
    </Button>
  )
  return (
    <Screen
      title={question}
      fill
      above={<p className="text-small font-semibold text-muted-foreground">{title}</p>}
      actions={
        <div className="grid w-full grid-cols-2 gap-tg gaze:gap-x-6">
          {backSlot === "start" ? back : <span aria-hidden="true" />}
          {backSlot === "end" ? back : <span aria-hidden="true" />}
        </div>
      }
    >
      {text ? <p className="text-flow">{text}</p> : null}
      <Button id="account-confirm-yes" variant="danger" size="lg" width="full" commit icon={icon} busy={busy} onClick={onYes}>
        {label}
      </Button>
    </Screen>
  )
}

export function AccountFlow({ path, choices, me }: { path: string; choices: Choices; me: Me }) {
  const [notice, setNotice] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const workspace = workspaceOf(me)
  const names = Object.fromEntries(choices.ui_sizes.map((choice) => [choice.code === "GAZE" ? "gaze" : "compact", choice.name])) as Record<SizeMode, string>
  const profession = choices.professions.find((p) => p.code === me.profession)?.name ?? "—"

  async function saveSize(mode: SizeMode): Promise<string | null> {
    const result = await api("PUT", "/api/me/ui-size", { json: { ui_size: toServer(mode) } })
    if (result.status !== 204) return detail(result)
    await refreshMe()
    return null
  }

  async function logout() {
    if (busy) return
    setBusy(true)
    const result = await api("POST", "/api/auth/logout")
    setBusy(false)
    if (result.status === 204 || result.status === 401) reload()
    else setNotice(detail(result))
  }

  async function remove() {
    if (busy) return
    setBusy(true)
    const result = await api("POST", "/api/me/delete")
    setBusy(false)
    if (result.status === 204) reload()
    else if (result.status !== 401) setNotice(detail(result))
  }

  let content: React.ReactNode
  if (path.startsWith("#/account/logout")) {
    content = (
      <ConfirmScreen
        title="تسجيل الخروج"
        question="تسجيل الخروج؟"
        label="نعم، اخرج"
        icon={LogOut}
        busy={busy}
        backSlot="end"
        onYes={() => void logout()}
        onBack={() => go("#/account")}
      />
    )
  } else if (path.startsWith("#/account/delete")) {
    content = (
      <ConfirmScreen
        title="حذف الحساب"
        question="حذف الحساب نهائياً؟"
        text="يُحذف الحساب وكل ما فيه، ولا يُسترجع."
        label="نعم، احذف حسابي"
        icon={Trash2}
        busy={busy}
        backSlot="start"
        onYes={() => void remove()}
        onBack={() => go("#/account")}
      />
    )
  } else {
    content = (
      <AccountScreen
        name={me.display_name}
        profession={profession}
        sizeNames={names}
        saveSize={saveSize}
        onLogout={() => go("#/account/logout")}
        onDelete={() => go("#/account/delete")}
      />
    )
  }

  const framed = workspace ? (
    <WorkspaceShell
      workspace={workspace}
      current={null}
      userName={me.display_name}
      onNavigate={navigate}
      tools={{ supportContact: choices.support_contact }}
      chat={chatApi(me, choices, "HOME")}
    >
      {content}
    </WorkspaceShell>
  ) : (
    // مهنةٌ بلا مساحة عملٍ بعد: «حسابي» هو الرئيسية، بلا قائمة أقسامٍ ولا أدوات.
    <div className="min-h-dvh bg-background pt-[env(safe-area-inset-top)]">
      {/* رأسٌ بارتفاعٍ ثابت (3.5rem + الحدّ): تحسبه `.chrome-bare` لتملأ الشاشة ما تحته. */}
      <header className="h-14 border-b border-border bg-card">
        <div className="mx-auto flex h-full max-w-content items-center gap-2.5 px-edge">
          <span className="flex flex-col items-start gap-1">
            <Wordmark className="text-lead" />
            <span className="text-small leading-tight text-muted-foreground">{profession}</span>
          </span>
        </div>
      </header>
      <main className="chrome-bare mx-auto w-full max-w-content px-edge pb-safe pt-sec">{content}</main>
    </div>
  )
  return (
    <Notice message={notice} onAck={() => setNotice(null)}>
      {framed}
    </Notice>
  )
}
