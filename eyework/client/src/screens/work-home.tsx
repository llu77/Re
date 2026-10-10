/*
 * الرئيسية: أزرارٌ تبدأ العمل
 * ==========================
 * تحديث المالك (2026-10-09): «اضف ازرار للبدء فالمهام والعمل وكل ما يتطلب كل مهنة». الرئيسية
 * أزرارٌ تفتح شاشات عملٍ حقيقية، ولا شيء يُقرأ قبلها: لا مهامّ ولا مهارات ولا شرح.
 *   • الزرّ الأوّل (`primary`) بعرض الشاشة وتعبئته ملوّنة: أكثر ما يبدأ به الموظف يومه، في
 *     المكان نفسه كل يوم. والباقي صفوفٌ تحته (بلاطاتٌ في عمودين في الحجم الكبير).
 *   • كل زرٍّ رابطٌ آمن (`data-safe`): يفتح شاشةً ولا يعتمد شيئاً، فما يقع تحت موضع «أنشئ
 *     حسابي» بعد التسجيل، أو تحت أيّ ضغطةٍ قبله، لا يعتمد شيئاً (registration_spec §8.6).
 *   • حسابٌ جديدٌ يرى الأزرار نفسها؛ والشاشة التي لا بيانات فيها بعد تقول ذلك بنفسها.
 */

import { ChevronLeft, type LucideIcon } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { TABLET_QUERY, WIDE_QUERY, useMatch, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { Workspace } from "@/lib/workspace"

export function WorkHome({ workspace, userName, onNavigate }: { workspace: Workspace; userName: string | null; onNavigate: (href: string) => void }) {
  return (
    <Screen title={homeTitle(userName)}>
      <HomeGrid workspace={workspace} onNavigate={onNavigate} />
    </Screen>
  )
}

export function homeTitle(userName: string | null): string {
  const name = userName?.trim()
  return name ? `أهلاً، ${name}` : "الرئيسية"
}

/** أزرار البدء وحدها: تستعملها الرئيسية المشتركة ورئيسيتا المخزون والدعم بما فوقها من ملخّص. `counts`
 *  عددٌ بجانب اسم الزرّ، والصفر لا يُكتب.
 *
 *  الحجم العادي: الزرّ الأوّل (`primary`) بالتعبئة الملوّنة بعرض الشاشة، والباقي صفوفٌ بنمط قوائم الإعدادات في iOS
 *  (أيقونةٌ في مربّعٍ هادئ، والاسم، والعدد، وسهمٌ في آخره)، مأخوذٌ تخطيطها من «Preferences Card» (ssychui، 21st.dev:
 *  https://21st.dev/@ssychui/components/preferences-card، بشروط 21st.dev ورخصة صفحة المكوّن) بلا framer-motion ولا
 *  سطر شرحٍ تحت الاسم؛ بين الصفوف 8px (فجوة الهدفين في هذا الحجم)، وعمودان من الآيباد.
 *  الحجم الكبير: بلاطاتٌ نصّية في عمودين، فتتّسع الأزرار في الهاتف الأضيق. */
export function HomeGrid({ workspace, onNavigate, counts }: { workspace: Workspace; onNavigate: (href: string) => void; counts?: Record<string, number> }) {
  const gaze = useSize().size === "gaze"
  const tablet = useMatch(TABLET_QUERY)
  const wide = useMatch(WIDE_QUERY)
  if (!gaze) {
    return (
      <ul aria-label="ابدأ عملاً" className="grid grid-cols-1 gap-tg tablet:grid-cols-2">
        {workspace.home.map((entry) => (
          <li key={entry.id} className={cn(entry.primary && "tablet:col-span-2")}>
            <HomeRow id={`home-${entry.id}`} href={entry.route} icon={entry.icon} label={entry.label} count={counts?.[entry.id]}
                     primary={entry.primary} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
    )
  }
  // الحجم الكبير في الهاتف: الأساسيّ خانةٌ كبقية الأزرار لا صفٌّ وحده، فتتّسع أزرار الدعم الستة في ثلاثة صفوف
  // (أربعة صفوفٍ بمراكز 96px هي ما يتّسع له 320×635 مع التحية).
  const primaryRow = tablet
  const columns = wide ? 3 : 2
  const cells = workspace.home.filter((entry) => !(entry.primary && primaryRow)).length
  // زرٌّ وحيد في صفّه الأخير يملأ الصفّ في الهاتف والآيباد، لا نصفه.
  const lastAlone = !wide && cells % columns === 1
  return (
    <ul aria-label="ابدأ عملاً" className="grid grid-cols-2 gap-tg gaze:gap-x-6 lg:grid-cols-3">
      {workspace.home.map((entry, index) => {
        const row = entry.primary && primaryRow
        return (
          <li key={entry.id} className={cn(row && "col-span-2 lg:col-span-3", lastAlone && index === workspace.home.length - 1 && "col-span-2")}>
            <a
              id={`home-${entry.id}`}
              href={entry.route}
              data-safe=""
              onClick={(event) => {
                event.preventDefault()
                onNavigate(entry.route)
              }}
              className={cn(
                "flex h-full min-h-ctl w-full items-center justify-center whitespace-nowrap rounded-ctl border px-2 text-center font-medium leading-none",
                entry.primary ? "border-transparent bg-primary text-primary-foreground shadow-sm shadow-black/5" : "border-border bg-card text-foreground shadow-sm shadow-black/5",
              )}
            >
              <span>
                {entry.label}
                {counts?.[entry.id] ? <span className="num"> · {counts[entry.id]}</span> : null}
              </span>
            </a>
          </li>
        )
      })}
    </ul>
  )
}

/** صفٌّ يفتح شاشة في الحجم العادي: الرئيسية، و«الإعدادات» تحتها، وقوائم «حسابي». رابطٌ آمن (`data-safe`). */
export function HomeRow({ id, href, icon: Icon, label, count, primary = false, onNavigate, className }: {
  id: string
  href: string
  icon: LucideIcon
  label: string
  count?: number
  primary?: boolean
  onNavigate: (href: string) => void
  className?: string
}) {
  return (
    <a
      id={id}
      href={href}
      data-safe=""
      onClick={(event) => {
        event.preventDefault()
        onNavigate(href)
      }}
      className={cn(
        primary
          ? "flex min-h-ctl-lg w-full items-center justify-center gap-2 rounded-ctl bg-primary px-4 font-semibold text-primary-foreground hov:bg-primary/90"
          : "flex min-h-[3.25rem] w-full items-center gap-3 rounded-card bg-card px-3 shadow-card hov:bg-muted/60",
        className,
      )}
    >
      {primary ? (
        <Icon aria-hidden="true" className="size-icon shrink-0" strokeWidth={2} />
      ) : (
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
          <Icon aria-hidden="true" className="size-[1.125rem]" strokeWidth={1.75} />
        </span>
      )}
      <span className={cn("min-w-0 truncate", primary ? "" : "flex-1 font-medium text-foreground")}>{label}</span>
      {!primary && count ? (
        <span className="num shrink-0 rounded-pill bg-primary px-2 py-0.5 text-small font-semibold leading-none text-primary-foreground">{count}</span>
      ) : null}
      {primary ? null : <ChevronLeft aria-hidden="true" className="size-4 shrink-0 text-muted-foreground/70" strokeWidth={2} />}
    </a>
  )
}
