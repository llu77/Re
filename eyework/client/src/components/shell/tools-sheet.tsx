/*
 * ToolsSheet — ورقة الأدوات
 * ========================
 * «أدواتٌ تساعد الموظف في أداء المهام»، من «الأدوات» في شريط التبويب أو الشريط الجانبي (وفي الحجم
 * الكبير على الهاتف من ورقة المحادثة)، في كل شاشةٍ من البوابة. فيها أوّلاً ما تسجّله الشاشة الحالية من
 * أدوات مهنتها (`context`، الأرجح أوّلاً)، ثم أداة البوابة المشتركة:
 *   مساعدة           ما تفعله الشاشة، وكيف يعمل سيمبول، وبمن يُتّصل
 * والسؤال إلى سيمبول من زرّه العائم (components/chat). لا أكثر: ما لم يطلبه المالك لا يُضاف. في الحجم
 * الكبير أربع أدواتٍ في الصفحة و«السابقة» و«التالية»: لا تمرير في الورقة. و«إغلاق» في ذيل الورقة، و«كل
 * الأدوات» في بدايته يعود إلى الشبكة.
 */

import * as React from "react"
import { CircleHelp, LayoutGrid, type LucideIcon } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { HelpTool } from "@/components/tools/help-tool"
import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { Sheet } from "@/components/ui/dialog"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { Workspace } from "@/lib/workspace"

/** أداةٌ في الورقة: لوحةٌ تُرسم داخلها، أو انتقالٌ إلى شاشة. */
export interface ToolEntry {
  id: string
  label: string
  icon: LucideIcon | "symbol"
  panel?: () => React.ReactNode
  route?: string
}

export interface ToolsProps {
  workspace: Workspace
  /** الشاشة الحالية (بند الرئيسية، أو "home"، أو null في «حسابي»): للمساعدة. */
  screen: string | null
  onNavigate: (href: string) => void
  /** أدوات المهنة لهذه الشاشة، الأرجح أوّلاً (يسجّلها مسار المهنة). */
  context?: ToolEntry[]
  /** بريد من يدير التطبيق (EYEWORK_SUPPORT_CONTACT)، أو null. */
  supportContact: string | null
}

const GAZE_PER_PAGE = 4

export function ToolsSheet({ open, initialTool, onClose, workspace, screen, onNavigate, context = [], supportContact }: ToolsProps & {
  open: boolean
  /** تُفتح على أداةٍ بعينها (من الشريط الجانبي). */
  initialTool: string | null
  onClose: () => void
}) {
  const { size } = useSize()
  // كل فتحٍ نسخةٌ جديدة (المضيف يغيّر `key`): تبدأ من الأداة المطلوبة أو الشبكة، لا ممّا بقي من الفتح السابق.
  const [toolId, setToolId] = React.useState<string | null>(initialTool)
  const [page, setPage] = React.useState(0)

  const shared: ToolEntry[] = [
    {
      id: "help",
      label: "مساعدة",
      icon: CircleHelp,
      panel: () => <HelpTool workspace={workspace} screen={screen} contact={supportContact} />,
    },
  ]
  const tools = [...context, ...shared.filter((tool) => !context.some((own) => own.id === tool.id))]
  const active = tools.find((tool) => tool.id === toolId) ?? null
  const perPage = size === "gaze" ? GAZE_PER_PAGE : tools.length
  const pages = Math.max(1, Math.ceil(tools.length / perPage))
  const current = Math.min(page, pages - 1)
  const visible = tools.slice(current * perPage, current * perPage + perPage)

  function choose(tool: ToolEntry) {
    if (tool.route) {
      onClose()
      onNavigate(tool.route)
    } else {
      setToolId(tool.id)
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      eyebrow={active ? "الأدوات" : workspace.name}
      title={active ? active.label : "الأدوات"}
      footer={
        active ? (
          <Button icon={LayoutGrid} onClick={() => setToolId(null)}>
            كل الأدوات
          </Button>
        ) : null
      }
    >
      {active?.panel ? (
        active.panel()
      ) : (
        <div className="flex flex-col gap-tg">
          {/* في الحجم الكبير تبدأ البلاطات أسفل قليلاً من أوّل صفٍّ في لوحة الأداة: ما يقع تحت تسمية البلاطة بعد
              فتحها قائمتها، لا لسانٌ يغيّر قيمة («عبارات» و«أسئلة»). */}
          <ul className="grid grid-cols-2 gap-tg gaze:mt-4 gaze:gap-x-6">
            {visible.map((tool) => (
              <li key={tool.id}>
                <button
                  type="button"
                  data-safe=""
                  onClick={() => choose(tool)}
                  className={cn(
                    "flex h-full min-h-ctl-lg w-full flex-col items-start gap-2 rounded-card bg-muted p-3 text-start hov:bg-secondary",
                    "gaze:justify-center gaze:gap-1.5",
                  )}
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-card text-secondary-foreground shadow-card gaze:size-9">
                    {tool.icon === "symbol" ? <SymbolMark className="size-icon" /> : <tool.icon aria-hidden="true" className="size-icon" strokeWidth={1.75} />}
                  </span>
                  <span className="font-medium leading-snug text-foreground">{tool.label}</span>
                </button>
              </li>
            ))}
          </ul>
          {pages > 1 ? (
            <nav aria-label="صفحات الأدوات" className="grid grid-cols-2 gap-tg gaze:gap-x-6">
              <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>
                السابقة
              </Button>
              <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
                التالية
              </Button>
            </nav>
          ) : null}
        </div>
      )}
    </Sheet>
  )
}
