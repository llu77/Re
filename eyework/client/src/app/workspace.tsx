/*
 * البوابة بعد الدخول
 * ==================
 * مساحة عمل المهنة (lib/workspace.ts) في الهيكل الموحّد: شريط التبويب أو الشريط الجانبي وورقتا الأقسام والأدوات
 * واحدٌ للجميع. التسويق له أداة الحملة تحت #/marketing/…، وأمين المخزون بوابته تحت #/inventory/…
 * (app/inventory-flow.tsx)، والدعم الفني مكتبه تحت #/support/… (app/support-flow.tsx).
 */

import * as React from "react"

import { AccountFlow } from "@/app/account-flow"
import { InventoryFlow } from "@/app/inventory-flow"
import { MarketingFlow } from "@/app/marketing-flow"
import { SupportFlow } from "@/app/support-flow"
import { Redirect } from "@/components/redirect"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import type { ChatApi, ChatScreenKind } from "@/lib/chat"
import { currentHash, go } from "@/lib/router"
import { setState, type Choices, type Me } from "@/lib/store"
import { WORKSPACES, type Workspace } from "@/lib/workspace"
import { WorkHome } from "@/screens/work-home"

/** المحادثة مع سيمبول من شاشةٍ بعينها: نوعها ومعرّفها لا بياناتها، وأسئلتها الجاهزة وحصّة اليوم من الخادم. */
export function chatApi(me: Me, choices: Choices, kind: ChatScreenKind, id: string | null = null): ChatApi {
  return {
    screen: { kind, id },
    ready: choices.assistant.ready[kind] ?? [],
    questionMax: choices.assistant.question_max,
    remaining: Math.max(0, me.ai.assistant.per_day - me.ai.assistant.used_today),
  }
}

export function navigate(href: string) {
  go(href)
}

export function workspaceOf(me: Me): Workspace | null {
  if (me.profession === "MARKETING") return WORKSPACES.MARKETING
  if (me.profession === "STOREKEEPER") return WORKSPACES.STOREKEEPER
  if (me.profession === "SUPPORT") return WORKSPACES.SUPPORT
  return null
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
  if (workspace.profession === "STOREKEEPER" || workspace.profession === "SUPPORT") {
    if (path === "#/" || path === "#") return <Redirect to={workspace.base} />
    if (path === workspace.base || path.startsWith(`${workspace.base}/`) || path.startsWith(`${workspace.base}?`)) {
      const Flow = workspace.profession === "STOREKEEPER" ? InventoryFlow : SupportFlow
      // المسار باستعلامه (`?status=draft`، `?draft=1`): الموجّه يمرّر الوسم بلا استعلام.
      return <Flow path={currentHash()} choices={choices} me={me} workspace={workspace} />
    }
    return <Redirect to={workspace.base} />
  }
  if (path.startsWith(`${workspace.base}/`)) return <MarketingFlow path={path} choices={choices} me={me} workspace={workspace} />
  if (path !== "#/" && path !== "#" && path !== workspace.base) return <Redirect to="#/" />
  return (
    <WorkspaceShell
      workspace={workspace}
      current="home"
      userName={me.display_name}
      onNavigate={navigate}
      tools={{ supportContact: choices.support_contact }}
      chat={chatApi(me, choices, "HOME")}
    >
      <ClearCampaign />
      <WorkHome workspace={workspace} userName={me.display_name} onNavigate={navigate} />
    </WorkspaceShell>
  )
}
