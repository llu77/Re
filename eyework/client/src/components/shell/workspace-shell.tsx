/*
 * WorkspaceShell — بوابة العمل الموحّدة
 * ====================================
 * تطبيقٌ واحد ودخولٌ واحد وبوابةٌ واحدة؛ والمهنة تحدّد ما فيها (lib/workspace.ts):
 *
 *   الهاتف:            الشاشة، وتحتها شريط التبويب [الرئيسية · الأقسام · الأدوات · حسابي]، وفوقه زرّ
 *                      «اسأل سيمبول» العائم في ركن النهاية
 *   الآيباد والحاسوب:  شريطٌ جانبي [العلامة · الرئيسية · البنود · الأدوات · مساعدة · حسابي] والشاشة
 *                      بجانبه، والزرّ العائم في الركن السفلي؛ وفي العريض بحجم اللمس قائمةٌ وتفصيلٌ معاً (`pane`).
 *   الحجم الكبير:      لا شيء يطفو: شريط التبويب [الرئيسية · سيمبول · حسابي] والسكّة [الرئيسية · الأقسام ·
 *                      سيمبول · حسابي]، و«الأدوات» من ورقة المحادثة (شاشةٌ باثني عشر هدفاً لا تتّسع لبندٍ خامس)؛
 *                      ولا تمرير: الغلاف بارتفاع الشاشة.
 *
 * «الأقسام» و«الأدوات» والمحادثة أوراقٌ على <dialog>: ما خلفها خاملٌ من المتصفّح نفسه. ولا شيء هنا
 * يعتمد: كل بندٍ رابطٌ أو زرٌّ آمن. ويُكتب `data-keyboard` على <html> ما دام حقلٌ مركَّزاً
 * (lib/keyboard.ts) فيختفي شريط التبويب والزرّ العائم تحت لوحة المفاتيح.
 */

import * as React from "react"
import { CircleHelp, House, LayoutGrid, UserRound, Wrench } from "lucide-react"

import { ChatLauncher } from "@/components/chat/chat-launcher"
import { ChatSheet } from "@/components/chat/chat-sheet"
import { SectionsSheet } from "@/components/shell/sections-sheet"
import { Sidebar } from "@/components/shell/sidebar"
import { TabBar, type NavEntry } from "@/components/shell/tab-bar"
import { ToolsSheet, type ToolsProps } from "@/components/shell/tools-sheet"
import type { ChatApi } from "@/lib/chat"
import { useKeyboardFlag } from "@/lib/keyboard"
import { TABLET_QUERY, WIDE_QUERY, useMatch, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { Workspace } from "@/lib/workspace"

export interface WorkspaceShellProps {
  workspace: Workspace
  /** بند الرئيسية الحالي، أو "home" في الرئيسية، أو null في «حسابي». */
  current: string | null
  userName: string | null
  onNavigate: (href: string) => void
  tools: Omit<ToolsProps, "workspace" | "screen" | "onNavigate">
  /** المحادثة مع سيمبول من هذه الشاشة: نوعها ومعرّفها وأسئلتها الجاهزة (lib/chat.ts). */
  chat: ChatApi
  /** قائمةٌ تُعرض بجانب الشاشة في العريض بحجم اللمس («حملاتي» بجانب الحملة). */
  pane?: React.ReactNode
  children: React.ReactNode
}

export function WorkspaceShell({ workspace, current, userName, onNavigate, tools, chat, pane, children }: WorkspaceShellProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const tablet = useMatch(TABLET_QUERY)
  const wide = useMatch(WIDE_QUERY)
  const [sections, setSections] = React.useState(false)
  // `gen` يزيد مع كل فتح فتُرسم الورقة من جديد (key) بحالةٍ نظيفة.
  const [tool, setTool] = React.useState<{ open: boolean; initial: string | null; gen: number }>({ open: false, initial: null, gen: 0 })
  const openTool = (initial: string | null) => setTool((t) => ({ open: true, initial, gen: t.gen + 1 }))
  const [chatOpen, setChatOpen] = React.useState(false)
  const main = React.useRef<HTMLElement>(null)
  useKeyboardFlag(main)

  const home: NavEntry = { id: "nav-home", label: "الرئيسية", icon: House, href: workspace.base, current: current === "home" }
  const account: NavEntry = { id: "nav-account", label: "حسابي", icon: UserRound, href: "#/account", current: current === null }
  const sectionsEntry: NavEntry = { id: "nav-sections", label: "الأقسام", icon: LayoutGrid, onClick: () => setSections(true) }
  const toolsEntry: NavEntry = { id: "nav-tools", label: "الأدوات", icon: Wrench, onClick: () => openTool(null) }
  const chatEntry: NavEntry = { id: "nav-chat", label: "سيمبول", icon: "symbol", accent: true, onClick: () => setChatOpen(true) }
  const four = [home, sectionsEntry, toolsEntry, account]

  const entries: NavEntry[] = workspace.home.map((entry) => ({
    id: `nav-entry-${entry.id}`,
    label: entry.label,
    icon: entry.icon,
    href: entry.route,
    current: entry.id === current,
  }))
  const sidebarGroups: NavEntry[][] = gaze
    ? [[home, sectionsEntry], [chatEntry], [account]]
    : [
        [home, ...entries],
        [toolsEntry, { id: "nav-help", label: "مساعدة", icon: CircleHelp, onClick: () => openTool("help") }],
        [account],
      ]

  const twoPanes = Boolean(pane) && wide && !gaze
  return (
    <div className={cn("bg-background", gaze ? "flex h-dvh flex-col overflow-hidden" : "min-h-dvh")}>
      <a
        href="#content"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:start-edge focus-visible:top-edge focus-visible:z-50 focus-visible:rounded-ctl focus-visible:bg-card focus-visible:p-3"
      >
        تخطَّ إلى المحتوى
      </a>
      <div className={cn("flex", gaze && "min-h-0 flex-1")}>
        {tablet ? <Sidebar workspaceName={workspace.name} userName={userName} groups={sidebarGroups} onNavigate={onNavigate} /> : null}
        <main
          ref={main}
          id="content"
          tabIndex={-1}
          className={cn(
            "chrome-portal mx-auto w-full px-edge focus-visible:outline-none",
            twoPanes ? "max-w-[72rem]" : "max-w-content",
            // الحجم الكبير على الهاتف: بين آخر صفٍّ وشريط التبويب فاصل قسمٍ كامل، فمركزاهما على بعد 96 على الأقل.
            gaze ? cn("flex min-h-0 flex-1 flex-col pt-tg", tablet ? "pb-safe" : "pb-sec") : "pt-sec",
            // الحجم العادي: آخر المحتوى فوق شريط التبويب وفوق زرّ «اسأل سيمبول» العائم.
            !gaze && (tablet ? "pb-launcher" : "pb-tab-launcher"),
          )}
        >
          {twoPanes ? (
            <div className="grid grid-cols-[20rem_minmax(0,1fr)] gap-sec">
              <div className="min-w-0">{pane}</div>
              <div className="min-w-0">{children}</div>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
      {/* الحجم الكبير على الهاتف: ثلاثة بنود، و«سيمبول» أوسطها. أربعةٌ لا تتّسع في 320px بحدّ الهدف وفجوته،
          و«الأقسام» هي أزرار الرئيسية نفسها، و«الأدوات» في ورقة المحادثة. */}
      {tablet ? null : <TabBar items={gaze ? [home, chatEntry, account] : four} onNavigate={onNavigate} />}
      {gaze ? null : <ChatLauncher tablet={tablet} onOpen={() => setChatOpen(true)} />}
      <ChatSheet
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        chat={chat}
        workspace={workspace}
        current={current}
        userName={userName}
        onNavigate={onNavigate}
        onTools={
          gaze
            ? () => {
                setChatOpen(false)
                openTool(null)
              }
            : undefined
        }
      />
      <SectionsSheet open={sections} workspace={workspace} current={current} onClose={() => setSections(false)} onNavigate={onNavigate} />
      <ToolsSheet
        key={tool.gen}
        open={tool.open}
        initialTool={tool.initial}
        onClose={() => setTool((t) => ({ ...t, open: false }))}
        workspace={workspace}
        screen={current}
        onNavigate={onNavigate}
        {...tools}
      />
    </div>
  )
}
