/*
 * WorkspaceShell — بوابة العمل الموحّدة
 * ====================================
 * تطبيقٌ واحد ودخولٌ واحد وبوابةٌ واحدة؛ والمهنة تحدّد ما فيها (lib/workspace.ts):
 *
 *   ┌ الرأس ───────────────────────────────────────────────────────────┐
 *   │ الهاتف والكبير: [المهنة · الشاشة الحالية ▾]                [حسابي] │
 *   │ الحاسوب:  [صياغة | أمين المخزون] [الرئيسية · جديد ▾ · المخزون…] [سارة] │
 *   └──────────────────────────────────────────────────────────────────┘
 *   الشاشة
 *                                              [الأدوات] ← عائمٌ في الطرف الأسفل
 *
 * قائمة الرأس هي أزرار الرئيسية نفسها بعد «الرئيسية»: من أيّ شاشةٍ إلى أيّ عمل بضغطتين.
 * في الحجم العادي تمرّ الصفحة والرأس لاصقٌ في أعلاها؛ وفي الكبير لا تمرير: الغلاف بارتفاع
 * الشاشة، والشاشة تأخذ ما بقي (Screen)، وخانة زرّ الأدوات محجوزةٌ في شريط الإجراءات.
 * حين تُفتح القائمة يصير المحتوى خاملاً وغير مرئي، فلا يُصاب من حوافّها.
 */

import * as React from "react"
import { House, PlusCircle, UserRound } from "lucide-react"

import { BrandMark } from "@/components/brand/marks"
import { ToolsFab, type ToolsProps } from "@/components/shell/tools-fab"
import { DropdownNavigation, type NavItem } from "@/components/ui/dropdown-navigation"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { Workspace } from "@/lib/workspace"

export interface WorkspaceShellProps {
  workspace: Workspace
  /** بند الرئيسية الحالي، أو "home" في الرئيسية، أو null في «حسابي». */
  current: string | null
  userName: string | null
  onNavigate: (href: string) => void
  tools: Omit<ToolsProps, "workspace" | "screen" | "onNavigate">
  children: React.ReactNode
  /** صفحة العرض: قائمة الأقسام مفتوحة. */
  navOpen?: boolean
}

export function WorkspaceShell({ workspace, current, userName, onNavigate, tools, children, navOpen = false }: WorkspaceShellProps) {
  const { size } = useSize()
  const [menuOpen, setMenuOpen] = React.useState(navOpen)
  const content = React.useRef<HTMLElement>(null)

  // React 18 لا يعرف الخاصيّة `inert`، فتُكتب على العنصر نفسه.
  React.useEffect(() => {
    if (content.current) content.current.inert = menuOpen
  }, [menuOpen])

  const home: NavItem = { id: "home", label: "الرئيسية", icon: House, href: workspace.base, current: current === "home" }
  const entries: NavItem[] = workspace.home.map((entry) => ({
    id: entry.id,
    label: entry.label,
    icon: entry.icon,
    href: entry.route,
    current: entry.id === current,
  }))
  // الحاسوب: ما يُنشئ مستنداً تحت «جديد ▾» حين يكون اثنين فأكثر (نمط القائمة الفرعية في الأصل).
  const creates = workspace.home.filter((entry) => entry.creates)
  const bar: NavItem[] =
    creates.length > 1
      ? [
          home,
          {
            id: "new",
            label: "جديد",
            icon: PlusCircle,
            href: creates[0].route,
            current: creates.some((entry) => entry.id === current),
            subMenus: [{ title: "ابدأ مستنداً", items: entries.filter((item) => creates.some((entry) => entry.id === item.id)) }],
          },
          ...entries.filter((item) => !creates.some((entry) => entry.id === item.id)),
        ]
      : [home, ...entries]
  const initial = userName?.trim()?.[0] ?? null
  const currentLabel = current === null ? "حسابي" : current === "home" ? "الرئيسية" : (entries.find((item) => item.current)?.label ?? "الرئيسية")

  const account = (
    <a
      href="#/account"
      data-safe=""
      aria-current={current === null ? "page" : undefined}
      onClick={(event) => {
        event.preventDefault()
        onNavigate("#/account")
      }}
      className={cn(
        "flex min-h-ctl shrink-0 items-center gap-2 rounded-ctl border-2 px-2",
        current === null ? "border-primary bg-secondary" : "border-control bg-card hov:bg-muted",
        "gaze:w-ctl gaze:flex-col gaze:justify-center gaze:gap-0.5 gaze:px-1",
      )}
    >
      <span className="flex size-7 shrink-0 items-center justify-center rounded-pill bg-primary text-small font-bold text-primary-foreground gaze:size-8">
        {initial ?? <UserRound aria-hidden="true" className="size-4" />}
      </span>
      <span className="flex min-w-0 flex-col leading-tight gaze:items-center">
        <span className="max-w-[7rem] truncate text-small font-bold text-foreground gaze:hidden">{userName ?? "حسابي"}</span>
        <span className="text-small text-muted-foreground gaze:text-[0.8125rem] gaze:font-semibold gaze:text-foreground">حسابي</span>
      </span>
    </a>
  )

  return (
    <div className={cn("bg-background", size === "gaze" ? "flex h-dvh flex-col overflow-hidden" : "min-h-dvh")}>
      <a
        href="#content"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:start-edge focus-visible:top-edge focus-visible:z-50 focus-visible:rounded-ctl focus-visible:bg-card focus-visible:p-3"
      >
        تخطَّ إلى المحتوى
      </a>
      <header
        className={cn(
          "z-20 shrink-0 border-b border-border bg-card pb-1.5 pt-[max(0.375rem,env(safe-area-inset-top))]",
          size === "compact" && "sticky top-0",
          "gaze:border-b-0 gaze:bg-background gaze:pb-0 gaze:pt-safe",
        )}
      >
        <div className="relative mx-auto flex max-w-content items-center gap-tg px-edge gaze:max-w-3xl">
          {/* الحاسوب، الحجم العادي */}
          <div className="hidden shrink-0 items-center gap-2.5 lg:flex gaze:hidden">
            <BrandMark />
            <span className="flex flex-col leading-tight">
              <span className="font-bold text-heading">صياغة</span>
              <span className="text-small text-muted-foreground">{workspace.name}</span>
            </span>
          </div>
          <DropdownNavigation
            variant="bar"
            label="أعمال البوابة"
            items={bar}
            onNavigate={onNavigate}
            onOpenChange={setMenuOpen}
            className="hidden flex-1 lg:block gaze:hidden"
          />
          {/* الهاتف، والحجم الكبير في كل شاشة */}
          <DropdownNavigation
            variant="switcher"
            label="أعمال البوابة"
            caption={workspace.name}
            currentLabel={currentLabel}
            items={[home, ...entries]}
            onNavigate={onNavigate}
            onOpenChange={setMenuOpen}
            defaultOpen={navOpen ? "switcher" : null}
            className="flex-1 lg:hidden gaze:block"
          />
          {account}
        </div>
      </header>

      <main
        ref={content}
        id="content"
        tabIndex={-1}
        className={cn(
          "mx-auto w-full max-w-content px-edge focus-visible:outline-none gaze:max-w-3xl",
          size === "gaze" ? "flex min-h-0 flex-1 flex-col pb-safe pt-tg" : "pb-[calc(var(--fab)+2*var(--edge)+env(safe-area-inset-bottom))] pt-sec",
          menuOpen && "invisible",
        )}
      >
        {children}
      </main>

      <ToolsFab workspace={workspace} screen={current} onNavigate={onNavigate} {...tools} hidden={menuOpen} />
    </div>
  )
}
