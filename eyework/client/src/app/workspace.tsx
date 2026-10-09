/*
 * البوابة بعد الدخول
 * ==================
 * مساحة عمل المهنة (lib/workspace.ts) في الهيكل الموحّد: الرأس وقائمة الأقسام وزرّ الأدوات
 * واحدٌ للجميع. في هذه الحزمة التسويق وحده له مساحة عمل («حملة جديدة» و«حملاتي» وأداة الحملة
 * تحت #/marketing/…)؛ وأمين المخزون والدعم الفني يصلان «حسابي» حتى تصل أدواتهما في حزمتيهما،
 * فلا زرٌّ يفتح ما ليس موجوداً.
 */

import * as React from "react"

import { AccountFlow } from "@/app/account-flow"
import { MarketingFlow } from "@/app/marketing-flow"
import type { AssistantApi } from "@/components/tools/assistant-tool"
import { Redirect } from "@/components/redirect"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import { api, detail } from "@/lib/api"
import { go } from "@/lib/router"
import { setState, type Choices, type Me } from "@/lib/store"
import { WORKSPACES, type Workspace } from "@/lib/workspace"
import { WorkHome } from "@/screens/work-home"

interface AssistantAnswer {
  status: "ANSWER" | "DONT_KNOW" | "OUT_OF_SCOPE"
  text: string
  question_sent: string
  sources: { line: string; href: string }[]
  usage: { per_day: number; used_today: number }
}

/** «اسأل سيمبول» من ورقة الأدوات: سؤالٌ واحد بسياق الشاشة (نوعها ومعرّفها لا بياناتها)، والجواب كما يردّه الخادم. */
export function assistantApi(me: Me, choices: Choices, screen: "HOME" | "CAMPAIGN", id: string | null = null): AssistantApi {
  return {
    remaining: Math.max(0, me.ai.assistant.per_day - me.ai.assistant.used_today),
    questionMax: choices.assistant.question_max,
    ask: async (question) => {
      const result = await api<AssistantAnswer>("POST", "/api/ai/assistant", { json: { screen: { kind: screen, id }, question } })
      if (result.status !== 200 || !result.data) return { ok: false, message: detail(result) }
      const answer = result.data
      return {
        ok: true,
        reply: {
          answer: answer.text,
          note: answer.sources.length ? answer.sources.map((source) => source.line).join("\n") : null,
          remaining: Math.max(0, answer.usage.per_day - answer.usage.used_today),
        },
      }
    },
  }
}

export function navigate(href: string) {
  go(href)
}

export function workspaceOf(me: Me): Workspace | null {
  return me.profession === "MARKETING" ? WORKSPACES.MARKETING : null
}

/** الرئيسية تترك الحملة الحالية: ما يصل بعدها لطلبٍ أقدم لا يجد حملةً يحدّثها. */
function ClearCampaign() {
  React.useEffect(() => {
    setState({ campaign: null })
  }, [])
  return null
}

export function WorkspaceView({ path, choices, me }: { path: string; choices: Choices; me: Me }) {
  const workspace = workspaceOf(me)
  if (!workspace) return <AccountFlow path={path} choices={choices} me={me} />
  if (path.startsWith(`${workspace.base}/`)) return <MarketingFlow path={path} choices={choices} me={me} workspace={workspace} />
  if (path !== "#/" && path !== "#" && path !== workspace.base) return <Redirect to="#/" />
  return (
    <WorkspaceShell
      workspace={workspace}
      current="home"
      userName={me.display_name}
      onNavigate={navigate}
      tools={{ userName: me.display_name, assistant: assistantApi(me, choices, "HOME"), supportContact: choices.support_contact }}
    >
      <ClearCampaign />
      <WorkHome workspace={workspace} userName={me.display_name} onNavigate={navigate} />
    </WorkspaceShell>
  )
}
