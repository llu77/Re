/*
 * الرئيسية: أزرارٌ تبدأ العمل
 * ==========================
 * تحديث المالك (2026-10-09): «اضف ازرار للبدء فالمهام والعمل وكل ما يتطلب كل مهنة». الرئيسية
 * أزرارٌ تفتح شاشات عملٍ حقيقية، ولا شيء يُقرأ قبلها: لا مهامّ ولا مهارات ولا شرح.
 *   • الزرّ الأوّل (`primary`) بعرض الشاشة وتعبئته ملوّنة: أكثر ما يبدأ به الموظف يومه، في
 *     المكان نفسه كل يوم. والباقي بلاطاتٌ في عمودين (ثلاثةٌ في الحاسوب).
 *   • كل زرٍّ رابطٌ آمن (`data-safe`): يفتح شاشةً ولا يعتمد شيئاً، فما يقع تحت موضع «أنشئ
 *     حسابي» بعد التسجيل، أو تحت أيّ ضغطةٍ قبله، لا يعتمد شيئاً (registration_spec §8.6).
 *   • حسابٌ جديدٌ يرى الأزرار نفسها؛ والشاشة التي لا بيانات فيها بعد تقول ذلك بنفسها.
 */

import { Screen } from "@/components/shell/screen"
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
 *  عددٌ بجانب اسم الزرّ («بانتظار قراري · 3»)، والصفر لا يُكتب. */
export function HomeGrid({ workspace, onNavigate, counts }: { workspace: Workspace; onNavigate: (href: string) => void; counts?: Record<string, number> }) {
  return (
      <ul
        aria-label="ابدأ عملاً"
        // زرٌّ وحيد في صفّه الأخير (عددٌ فرديّ بعد الأساسي) يملأ الصفّ في الهاتف، لا نصفه.
        className="grid grid-cols-2 gap-tg lg:grid-cols-3 max-lg:[&>li:last-child:nth-child(even)]:col-span-2"
      >
        {workspace.home.map((entry) => {
          const Icon = entry.icon
          return (
            <li key={entry.id} className={cn(entry.primary && "col-span-2 lg:col-span-3")}>
              <a
                id={`home-${entry.id}`}
                href={entry.route}
                data-safe=""
                onClick={(event) => {
                  event.preventDefault()
                  onNavigate(entry.route)
                }}
                className={cn(
                  "flex h-full min-h-ctl w-full items-center gap-3 rounded-card border px-4 py-3 font-bold",
                  "compact:min-h-[5.5rem] compact:flex-col compact:items-start compact:justify-between",
                  entry.primary
                    ? "border-primary bg-primary text-primary-foreground compact:min-h-ctl-lg compact:flex-row compact:items-center compact:justify-start hov:bg-primary/90 gaze:justify-start"
                    // الحجم الكبير: نصف عرض 320px لا يتّسع لمربّع الأيقونة والنصّ معاً (يخرج النصّ من حدّ الزرّ)،
                    // فالبنود الثانوية نصٌّ في الوسط بلا أيقونة؛ والرئيسي بعرض الشاشة يبقى بأيقونته.
                    : "border-control bg-card text-foreground hov:bg-muted gaze:justify-center gaze:text-center",
                )}
              >
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-ctl gaze:size-10",
                    entry.primary ? "bg-primary-foreground/15" : "bg-secondary text-secondary-foreground gaze:hidden",
                  )}
                >
                  <Icon aria-hidden="true" className="size-5 gaze:size-6" strokeWidth={2.25} />
                </span>
                <span className="leading-snug">
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
