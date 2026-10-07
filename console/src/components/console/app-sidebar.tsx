import { ClipboardList, LogOut, Siren, type LucideIcon } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

import { href, type Route } from "./route"
import { SymbolMark } from "./symbol-mark"

/**
 * الشريط الجانبي للوحة
 * ====================
 * المكوّن كما ورد، مضبوطٌ من الخارج بالأصناف وحدها لثلاثة أمور:
 *
 *   • **اليمين لا اليسار.** الواجهة عربية، فالشريط في بداية السطر (`side="right"`)،
 *     والتلميح يظهر نحو المحتوى (`side: "left"`)، والشارة في الطرف الآخر.
 *   • **48px لكل زرّ**، مطويّاً أو مفتوحاً، كبقية المنصّة. المكوّن يفرض 32px
 *     في الوضع المطويّ (`!size-8`)؛ يُستبدل هنا، ويتّسع الشريط المطويّ له
 *     (`--sidebar-width-icon` في `ConsoleShell`).
 *   • **العدد مقروءٌ لا مرئيٌّ فقط.** الشارة زخرفية لقارئ الشاشة، والعدد في
 *     اسم الرابط وفي التلميح حين يُطوى الشريط فتختفي الشارة.
 */

interface Item {
  route: Route
  label: string
  icon: LucideIcon
  count: number | null
  urgent: boolean
}

const BUTTON = cn(
  "text-start text-base",
  "group-data-[collapsible=icon]:!size-12 group-data-[collapsible=icon]:!p-3.5",
  "[&>svg]:size-5",
)

export function AppSidebar({
  route,
  queueCount,
  redFlagCount,
  email,
  onSignOut,
  signingOut,
}: {
  route: Route
  queueCount: number | null
  redFlagCount: number | null
  email: string
  onSignOut: () => void
  signingOut: boolean
}) {
  const items: Item[] = [
    {
      route: { name: "queue" },
      label: "طابور المراجعة",
      icon: ClipboardList,
      count: queueCount,
      urgent: false,
    },
    {
      route: { name: "red-flags" },
      label: "البلاغات العاجلة",
      icon: Siren,
      count: redFlagCount,
      urgent: (redFlagCount ?? 0) > 0,
    },
  ]
  const active = route.name === "proposal" ? "queue" : route.name

  return (
    <Sidebar side="right" collapsible="icon">
      <SidebarHeader>
        <div className="flex min-h-12 items-center gap-3 px-1.5">
          <SymbolMark />
          <div className="flex min-w-0 flex-col leading-tight group-data-[collapsible=icon]:hidden">
            <span className="font-bold text-sidebar-primary" lang="en" dir="ltr">
              Symbol AI
            </span>
            <span className="text-sm text-sidebar-foreground">لوحة الممارس</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="أقسام اللوحة">
          <SidebarGroup>
            <SidebarGroupLabel className="text-sm">المراجعة</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {items.map((item) => {
                  const isActive = active === item.route.name
                  const counted = item.count === null ? item.label : `${item.label}، ${item.count}`
                  return (
                    <SidebarMenuItem key={item.route.name}>
                      <SidebarMenuButton
                        asChild
                        size="lg"
                        isActive={isActive}
                        // الشارة مرسومةٌ فوق الزرّ لا بجانبه، والمكوّن لا يحجز
                        // لها مكاناً: بلا هذا يمرّ الاسم الطويل تحتها.
                        className={cn(BUTTON, item.count !== null && "pe-12")}
                        tooltip={{ children: counted, side: "left" }}
                      >
                        <a
                          href={href(item.route)}
                          aria-current={isActive ? "page" : undefined}
                          aria-label={counted}
                        >
                          <item.icon aria-hidden="true" />
                          <span>{item.label}</span>
                        </a>
                      </SidebarMenuButton>
                      {item.count !== null ? (
                        <SidebarMenuBadge
                          aria-hidden="true"
                          className={cn(
                            "left-2 right-auto h-6 min-w-6 rounded-full px-1.5 text-sm",
                            "peer-data-[size=lg]/menu-button:top-3",
                            item.urgent
                              ? "bg-destructive text-destructive-foreground peer-hover/menu-button:text-destructive-foreground peer-data-[active=true]/menu-button:text-destructive-foreground"
                              : "bg-sidebar-accent",
                          )}
                        >
                          {item.count}
                        </SidebarMenuBadge>
                      ) : null}
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </nav>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <p
              className="truncate px-2 pb-1 text-sm text-sidebar-foreground group-data-[collapsible=icon]:hidden"
              dir="ltr"
              title={email}
            >
              {email}
            </p>
            <SidebarMenuButton
              size="lg"
              className={BUTTON}
              tooltip={{ children: "تسجيل الخروج", side: "left" }}
              onClick={onSignOut}
              disabled={signingOut}
            >
              <LogOut aria-hidden="true" className="rtl:-scale-x-100" />
              <span>{signingOut ? "جارٍ الخروج…" : "تسجيل الخروج"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail aria-label="إظهار الشريط الجانبي أو طيّه" title="إظهار الشريط الجانبي أو طيّه" />
    </Sidebar>
  )
}
