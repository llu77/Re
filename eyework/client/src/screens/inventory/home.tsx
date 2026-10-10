/*
 * رئيسية أمين المخزون
 * ===================
 * أزرار المالك السبعة كما في الرئيسية المشتركة (HomeGrid)، وفوقها سطران من الخادم (/summary):
 * «يحتاج انتباهك» (جلسة الجرد المفتوحة، والمسودات، ونقص التسليم بلا مرتجع، والإشعارات الدائنة المتأخّرة أو المنتظرة،
 * وما تحت حدّ الطلب، وما لم يُجرد منذ تسعين يوماً)
 * و«هذا الشهر» (المشتريات والمرتجعات). في الحجم العادي كل بندٍ رابطٌ آمن إلى قائمته؛ وفي الحجم الكبير
 * سطرٌ واحد يُقرأ (أوّل البنود وعدد ما بعده، أو «لا شيء ينتظرك»): الأزرار السبعة وشريط التبويب أحد عشر هدفاً، ورابط
 * الإعدادات الثاني عشر.
 */

import { Settings2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { ButtonLink } from "@/components/ui/button"
import { BASE, countRoute, type Summary } from "@/lib/inventory"
import { useSize } from "@/lib/size"
import type { Workspace } from "@/lib/workspace"
import { HomeGrid, homeTitle } from "@/screens/work-home"

import { Money } from "./common"

interface AttentionItem {
  id: string
  text: string
  href: string
}

export function attentionItems(summary: Summary): AttentionItem[] {
  const a = summary.attention
  const items: AttentionItem[] = []
  if (a.open_count) items.push({ id: "open-count", text: `جلسة جرد مفتوحة ${a.open_count.label}`, href: countRoute(a.open_count.id) })
  if (a.purchase_drafts) items.push({ id: "drafts", text: `فواتير لم تُسجَّل: ${a.purchase_drafts}`, href: `${BASE}/purchases?status=draft` })
  if (a.return_drafts) items.push({ id: "return-drafts", text: `مرتجعات لم تُسجَّل: ${a.return_drafts}`, href: `${BASE}/returns?status=draft` })
  if (a.short_delivery) items.push({ id: "short", text: `فواتير وصل منها أقلّ ولم يُرجَع الفرق: ${a.short_delivery}`, href: `${BASE}/returns/new` })
  if (a.credit_note_overdue) items.push({ id: "overdue", text: `إشعارات دائنة تأخّرت: ${a.credit_note_overdue}`, href: `${BASE}/returns?awaiting=1` })
  else if (a.awaiting_credit_note) items.push({ id: "awaiting", text: `مرتجعات تنتظر إشعاراً دائناً: ${a.awaiting_credit_note}`, href: `${BASE}/returns?awaiting=1` })
  if (a.low_stock) items.push({ id: "low", text: `منتجات تحت حدّ الطلب: ${a.low_stock}`, href: `${BASE}/stock?filter=low` })
  if (a.uncounted) items.push({ id: "uncounted", text: `لم تُجرد منذ تسعين يوماً: ${a.uncounted}`, href: `${BASE}/stock?filter=uncounted` })
  return items
}

export function InventoryHome({ workspace, userName, summary, onNavigate }: {
  workspace: Workspace
  userName: string | null
  summary: Summary | null
  onNavigate: (href: string) => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const items = summary ? attentionItems(summary) : []
  const store = summary?.settings?.store_name ?? null
  return (
    <Screen
      title={homeTitle(userName)}
      description={store ? <span>{store}</span> : undefined}
      aside={
        <ButtonLink id="home-settings" href={`${BASE}/settings`} icon={Settings2} onClick={(event) => { event.preventDefault(); onNavigate(`${BASE}/settings`) }}>
          الإعدادات
        </ButtonLink>
      }
    >
      <HomeGrid workspace={workspace} onNavigate={onNavigate} />
      {summary ? (
        <section id="home-summary" aria-label="ملخّص المخزون" className="flex flex-col gap-2 rounded-card border border-border bg-card p-pad gaze:short:hidden">
          {gaze ? (
            // سطرٌ واحد في الحجم الكبير: الأزرار السبعة ورابط الإعدادات يملآن الهاتف الأضيق (320×635).
            <p className="truncate text-small font-semibold">
              {items.length ? (
                <span className="text-warning">{items[0].text}{items.length > 1 ? ` (+${items.length - 1})` : ""}</span>
              ) : (
                // مجموع الشهر في «المجاميع»: مبلغٌ بجوار هذه العبارة يُقصّ على 320.
                <span className="text-muted-foreground">لا شيء ينتظرك.</span>
              )}
            </p>
          ) : (
            <>
              {items.length ? (
                <ul className="flex flex-col gap-tg-min text-small">
                  {items.slice(0, 4).map((item) => (
                    <li key={item.id}>
                      <a href={item.href} data-safe="" onClick={(event) => { event.preventDefault(); onNavigate(item.href) }} className="inline-flex min-h-ctl items-center font-semibold text-warning underline decoration-2 underline-offset-4">
                        {item.text}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-small text-muted-foreground">لا شيء ينتظرك.</p>
              )}
              <p className="text-small text-muted-foreground">
                هذا الشهر: مشترياتٌ <Money halalas={summary.month_totals.purchases.gross} className="font-semibold text-foreground" /> ومرتجعاتٌ{" "}
                <Money halalas={summary.month_totals.returns.gross} className="font-semibold text-foreground" />. قيمة المخزون{" "}
                <Money halalas={summary.stock_value} className="font-semibold text-foreground" />.
              </p>
            </>
          )}
        </section>
      ) : null}
      <div className="tablet:hidden">
        <ButtonLink id="home-settings-phone" href={`${BASE}/settings`} icon={Settings2} onClick={(event) => { event.preventDefault(); onNavigate(`${BASE}/settings`) }} className="gaze:w-full">
          إعدادات المخزن
        </ButtonLink>
      </div>
    </Screen>
  )
}
