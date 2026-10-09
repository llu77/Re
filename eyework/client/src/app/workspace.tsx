/*
 * البوابة بعد الدخول
 * ==================
 * مساحة عمل المهنة (lib/workspace.ts) في الهيكل الموحّد: الرأس وقائمة الأقسام وزرّ الأدوات
 * واحدٌ للجميع. في هذه الحزمة التسويق وحده له مساحة عمل («حملة جديدة» و«حملاتي» تفتحان
 * أداة الحملة القائمة عند «/» حتى تُنقل شاشاتها)؛ وأمين المخزون والدعم الفني يصلان «حسابي»
 * حتى تصل أدواتهما في حزمتيهما، فلا زرٌّ يفتح ما ليس موجوداً.
 */

import * as React from "react"

import { AccountFlow } from "@/app/account-flow"
import type { AssistantApi } from "@/components/tools/assistant-tool"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import { api, detail } from "@/lib/api"
import { go } from "@/lib/router"
import type { Choices, Me } from "@/lib/store"
import { WORKSPACES, currentEntry, type Workspace } from "@/lib/workspace"
import { WorkHome } from "@/screens/work-home"

/** أداة الحملة في هذه الحزمة: شاشات العميل القائم عند «/»، انتقالاً كاملاً. */
const CURRENT_CLIENT: Record<string, string> = {
  "#/marketing/new": "/#/new",
  "#/marketing/campaigns": "/#/",
}

interface AssistantAnswer {
  status: "ANSWER" | "DONT_KNOW" | "OUT_OF_SCOPE"
  text: string
  question_sent: string
  sources: { line: string; href: string }[]
  usage: { per_day: number; used_today: number }
}

/** «اسأل سيمبول» من الزرّ العائم: سؤالٌ واحد بسياق الشاشة، والجواب كما يردّه الخادم. */
export function assistantApi(me: Me, choices: Choices, screen: "HOME" | "CAMPAIGN"): AssistantApi {
  return {
    remaining: Math.max(0, me.ai.assistant.per_day - me.ai.assistant.used_today),
    questionMax: choices.assistant.question_max,
    ask: async (question) => {
      const result = await api<AssistantAnswer>("POST", "/api/ai/assistant", { json: { screen: { kind: screen }, question } })
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
  const current = CURRENT_CLIENT[href.split("?")[0]]
  if (current) location.assign(current)
  else go(href)
}

export function workspaceOf(me: Me): Workspace | null {
  return me.profession === "MARKETING" ? WORKSPACES.MARKETING : null
}

function Leave({ to }: { to: string }) {
  React.useEffect(() => navigate(to), [to])
  return null
}

export function WorkspaceView({ path, choices, me }: { path: string; choices: Choices; me: Me }) {
  const workspace = workspaceOf(me)
  if (!workspace) return <AccountFlow path={path} choices={choices} me={me} />
  const entry = currentEntry(workspace, path)
  if (entry) return <Leave to={entry.route} />
  if (path !== "#/" && path !== "#" && path !== workspace.base) return <Leave to="#/" />
  return (
    <WorkspaceShell
      workspace={workspace}
      current="home"
      userName={me.display_name}
      onNavigate={navigate}
      tools={{ userName: me.display_name, assistant: assistantApi(me, choices, "HOME"), supportContact: choices.support_contact }}
    >
      <WorkHome workspace={workspace} userName={me.display_name} onNavigate={navigate} />
    </WorkspaceShell>
  )
}
