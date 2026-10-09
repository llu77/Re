/*
 * WorkspaceShell — بوابة العمل الموحّدة
 * ====================================
 * تطبيقٌ واحد ودخولٌ واحد وبوابةٌ واحدة؛ والمهنة تحدّد ما فيها (lib/workspace.ts):
 *
 *   الهاتف:            الشاشة، وتحتها شريط التبويب [الرئيسية · الأقسام · الأدوات · حسابي]
 *   الآيباد والحاسوب:  شريطٌ جانبي [العلامة · الرئيسية · البنود · اسأل سيمبول · مساعدة · حسابي]
 *                      والشاشة بجانبه؛ وفي العريض بحجم اللمس قائمةٌ وتفصيلٌ معاً (`pane`).
 *   الحجم الكبير:      الشريط الجانبي سكّةٌ بالبنود الأربعة نفسها؛ لا تمرير: الغلاف بارتفاع الشاشة.
 *
 * «الأقسام» و«الأدوات» ورقتان على <dialog>: ما خلفهما خاملٌ من المتصفّح نفسه. ولا شيء هنا
 * يعتمد: كل بندٍ رابطٌ أو زرٌّ آمن. ويُكتب `data-keyboard` على <html> ما دام حقلٌ مركَّزاً
 * (lib/keyboard.ts) فيختفي شريط التبويب تحت لوحة المفاتيح.
 */

import * as React from "react"
import { CircleHelp, House, LayoutGrid, UserRound, Wrench } from "lucide-react"

import { SectionsSheet } from "@/components/shell/sections-sheet"
import { Sidebar } from "@/components/shell/sidebar"
import { TabBar, type NavEntry } from "@/components/shell/tab-bar"
import { ToolsSheet, type ToolsProps } from "@/components/shell/tools-sheet"
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
  /** قائمةٌ تُعرض بجانب الشاشة في العريض بحجم اللمس («حملاتي» بجانب الحملة). */
  pane?: React.ReactNode
  children: React.ReactNode
}

export function WorkspaceShell({ workspace, current, userName, onNavigate, tools, pane, children }: WorkspaceShellProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const tablet = useMatch(TABLET_QUERY)
  const wide = useMatch(WIDE_QUERY)
  const [sections, setSections] = React.useState(false)
  const [tool, setTool] = React.useState<{ open: boolean; initial: string | null }>({ open: false, initial: null })
  const main = React.useRef<HTMLElement>(null)
  useKeyboardFlag(main)

  const home: NavEntry = { id: "nav-home", label: "الرئيسية", icon: House, href: workspace.base, current: current === "home" }
  const account: NavEntry = { id: "nav-account", label: "حسابي", icon: UserRound, href: "#/account", current: current === null }
  const sectionsEntry: NavEntry = { id: "nav-sections", label: "الأقسام", icon: LayoutGrid, onClick: () => setSections(true) }
  const toolsEntry: NavEntry = { id: "nav-tools", label: "الأدوات", icon: Wrench, onClick: () => setTool({ open: true, initial: null }) }
  const four = [home, sectionsEntry, toolsEntry, account]

  const entries: NavEntry[] = workspace.home.map((entry) => ({
    id: `nav-entry-${entry.id}`,
    label: entry.label,
    icon: entry.icon,
    href: entry.route,
    current: entry.id === current,
  }))
  const sidebarGroups: NavEntry[][] = gaze
    ? [[home, sectionsEntry], [toolsEntry], [account]]
    : [
        [home, ...entries],
        [
          { id: "nav-assistant", label: "اسأل سيمبول", icon: "symbol", onClick: () => setTool({ open: true, initial: "assistant" }) },
          { id: "nav-help", label: "مساعدة", icon: CircleHelp, onClick: () => setTool({ open: true, initial: "help" }) },
        ],
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
            "mx-auto w-full px-edge focus-visible:outline-none",
            twoPanes ? "max-w-[72rem]" : "max-w-content",
            gaze ? "flex min-h-0 flex-1 flex-col pb-safe pt-tg" : "pt-sec",
            !gaze && (tablet ? "pb-safe" : "pb-tab"),
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
      {tablet ? null : <TabBar items={four} onNavigate={onNavigate} />}
      <SectionsSheet open={sections} workspace={workspace} current={current} onClose={() => setSections(false)} onNavigate={onNavigate} />
      <ToolsSheet
        open={tool.open}
        initialTool={tool.initial}
        onClose={() => setTool({ open: false, initial: null })}
        workspace={workspace}
        screen={current}
        onNavigate={onNavigate}
        {...tools}
      />
    </div>
  )
}
