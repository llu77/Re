/*
 * تسلسل البدء لحسابٍ قائم
 * =======================
 * حسابٌ بلا طريقة استخدامٍ (دعوة، أو أقدم من الحزمة 1) يُسأل «كيف تستخدم الجهاز؟» قبل أيّ
 * شاشة؛ وحسابٌ وافق على إشعارٍ أقدم (أو لم يوافق قطّ) يقرأ الحالي ويوافق، وقبلها لا يُرسَل
 * له شيءٌ إلى النموذج (require_current_terms). ما ينقص وحده يُسأل، بهذا الترتيب.
 */

import * as React from "react"

import { Notice } from "@/components/ui/notice"
import { api, detail } from "@/lib/api"
import { refreshMe } from "@/lib/session"
import { go, reload } from "@/lib/router"
import { toServer, useSize, type SizeMode } from "@/lib/size"
import type { Choices, Me } from "@/lib/store"
import { SignupSizeStep } from "@/screens/auth"
import { NoticeKeptScreen, NoticeSentScreen } from "@/screens/notice"

const STEPS = [
  { id: "use", label: "طريقة الاستخدام" },
  { id: "terms", label: "قبل أن تبدأ" },
]

export function StartFlow({ path, choices, me }: { path: string; choices: Choices; me: Me }) {
  const { size, setSize } = useSize()
  const [notice, setNotice] = React.useState<string | null>(null)
  const [screen, setScreen] = React.useState<"kept" | "sent">("kept")
  const needSize = me.ui_size === null

  async function saveSize(mode: SizeMode) {
    const result = await api("PUT", "/api/me/ui-size", { json: { ui_size: toServer(mode) } })
    if (result.status !== 204) {
      setNotice(detail(result))
      return
    }
    setSize(mode)
    await refreshMe()
  }

  async function agree() {
    const result = await api("POST", "/api/me/terms", { json: { terms_version: choices.notice.version } })
    if (result.status !== 204) {
      setNotice(detail(result))
      return
    }
    await refreshMe()
    go("#/", { replace: true })
  }

  async function logout() {
    await api("POST", "/api/auth/logout")
    reload()
  }

  if (path.startsWith("#/account/logout")) {
    return (
      <Notice message="للخروج قبل إكمال البدء اضغط «حسناً» ثم «رجوع»." onAck={() => go("#/", { replace: true })}>
        <span />
      </Notice>
    )
  }

  let content: React.ReactNode
  if (needSize) {
    content = (
      <SignupSizeStep
        step={0}
        steps={STEPS}
        value={size}
        choices={choices.ui_sizes.map((choice) => ({ code: choice.code, name: choice.name, line: choice.detail }))}
        onNext={(mode) => void saveSize(mode)}
        onBack={() => void logout()}
      />
    )
  } else if (screen === "kept") {
    content = <NoticeKeptScreen notice={choices.notice} onNext={() => setScreen("sent")} onBack={() => void logout()} />
  } else {
    content = <NoticeSentScreen notice={choices.notice} scope={me.profession} onAgree={() => void agree()} onBack={() => setScreen("kept")} />
  }
  return (
    <Notice message={notice} onAck={() => setNotice(null)}>
      {content}
    </Notice>
  )
}
