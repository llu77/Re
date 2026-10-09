/*
 * ToolsSheet — ورقة الأدوات
 * ========================
 * «أدواتٌ تساعد الموظف في أداء المهام»، من «الأدوات» في شريط التبويب أو الشريط الجانبي، في كل
 * شاشةٍ من البوابة. فيها أوّلاً ما تسجّله الشاشة الحالية من أدوات مهنتها (`context`، الأرجح
 * أوّلاً)، ثم أداتا البوابة المشتركتان:
 *   اسأل سيمبول      سؤالٌ إلى المساعد بسياق الشاشة وحده (POST /api/ai/assistant)
 *   مساعدة           ما تفعله الشاشة، وكيف يعمل سيمبول، وبمن يُتّصل
 * لا أكثر: ما لم يطلبه المالك لا يُضاف. في الحجم الكبير أربع أدواتٍ في الصفحة و«السابقة»
 * و«التالية»: لا تمرير في الورقة. و«إغلاق» في ذيل الورقة، و«كل الأدوات» في بدايته يعود
 * إلى الشبكة.
 */

import * as React from "react"
import { CircleHelp, LayoutGrid, type LucideIcon } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { AssistantTool, type AssistantApi } from "@/components/tools/assistant-tool"
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
  description?: string
  icon: LucideIcon | "symbol"
  panel?: () => React.ReactNode
  route?: string
}

export interface ToolsProps {
  workspace: Workspace
  /** الشاشة الحالية (بند الرئيسية، أو "home"، أو null في «حسابي»): للمساعدة وسياق سيمبول. */
  screen: string | null
  userName: string | null
  onNavigate: (href: string) => void
  /** أدوات المهنة لهذه الشاشة، الأرجح أوّلاً (يسجّلها مسار المهنة). */
  context?: ToolEntry[]
  assistant: AssistantApi
  /** بريد من يدير التطبيق (EYEWORK_SUPPORT_CONTACT)، أو null. */
  supportContact: string | null
}

const GAZE_PER_PAGE = 4

export function ToolsSheet({ open, initialTool, onClose, workspace, screen, userName, onNavigate, context = [], assistant, supportContact }: ToolsProps & {
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
      id: "assistant",
      label: "اسأل سيمبول",
      description: "سؤالٌ عن عملك، وجوابٌ تقرّر فيه",
      icon: "symbol",
      panel: () => <AssistantTool userName={userName} screen={screen} workspace={workspace} api={assistant} />,
    },
    {
      id: "help",
      label: "مساعدة",
      description: "ما في هذه الشاشة",
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
      description={active ? undefined : "ما يساعدك وأنت تعمل، في كل شاشة."}
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
          <ul className="grid grid-cols-2 gap-tg">
            {visible.map((tool) => (
              <li key={tool.id}>
                <button
                  type="button"
                  data-safe=""
                  onClick={() => choose(tool)}
                  className={cn(
                    "flex h-full min-h-ctl-lg w-full flex-col items-start gap-2 rounded-card border border-control bg-card p-3 text-start hov:bg-muted",
                    "gaze:justify-center gaze:gap-1.5",
                  )}
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-ctl bg-secondary text-secondary-foreground gaze:size-9">
                    {tool.icon === "symbol" ? <SymbolMark className="size-icon" /> : <tool.icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />}
                  </span>
                  <span className="flex flex-col">
                    <span className="font-semibold leading-snug text-foreground">{tool.label}</span>
                    {tool.description ? (
                      <span className="text-small leading-snug text-muted-foreground gaze:hidden">{tool.description}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {pages > 1 ? (
            <nav aria-label="صفحات الأدوات" className="grid grid-cols-2 gap-tg">
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
