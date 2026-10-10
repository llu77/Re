/*
 * DataTable — جدولٌ يُقرأ ويُفتح منه
 * =================================
 * الأصل: shadcn/ui data-table (TanStack) — والمبدأ لا المكتبة: الفرز والتصفية والصفحات
 * من الخادم، فيكفي هنا العرض والصفحات.
 *   • الحاسوب في الحجم العادي: <table> حقيقي برؤوس أعمدة (scope="col")، وهدف كل صفٍّ
 *     زرٌّ في خليّته الأولى ارتفاعه 44 داخل صفٍّ 52: فبين هدفي صفّين 8.
 *   • الهاتف، والحجم الكبير في كل شاشة: قائمة بطاقات، كل بطاقةٍ زرٌّ واحد وبينها `gap-tg-min`؛
 *     وفي الكبير بين بطاقتين تُفتحان فجوة هدفين (48: بين مساحتي إصابتهما 24، وبين مركزيهما أكثر من 96).
 *     والأعمدة الثانوية سطرٌ تحت الاسم.
 *   • لا تمرير في الحجم الكبير: صفحاتٌ بـ«السابق» و«التالي» (صفّان في الصفحة، `LIST_PAGE`)؛ وفي العادي
 *     صفحاتٌ أطول تمرّ بها الصفحة.
 *   • الأرقام لاتينيةٌ بعرضٍ ثابت ومحاذاةٌ إلى الطرف، فتصطفّ المنازل.
 */

import * as React from "react"

import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { usePageSize, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface Column<T> {
  id: string
  header: string
  cell: (row: T) => React.ReactNode
  /** أرقامٌ ومبالغ: محاذاةٌ إلى الطرف وخطٌّ بعرضٍ ثابت. */
  numeric?: boolean
  className?: string
}

export interface DataTableProps<T> {
  /** عنوان الجدول لقارئ الشاشة (caption). */
  caption: string
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  /** عنوان الصفّ: الخليّة الأولى في الجدول، وسطر البطاقة الأول. */
  primary: (row: T) => React.ReactNode
  /** سطر البطاقة الثاني (الهاتف والحجم الكبير). */
  secondary?: (row: T) => React.ReactNode
  /** طرف البطاقة: مبلغٌ أو شارة. */
  trailing?: (row: T) => React.ReactNode
  /** يفتح الصفّ؛ بلا قيمةٍ يُقرأ الصفّ فقط. */
  onOpen?: (row: T) => void
  /** اسم زرّ الصفّ لقارئ الشاشة: «افتح الفاتورة 1043». */
  openLabel?: (row: T) => string
  pageSize?: { compact: number; gaze: number; gazeShort?: number }
  /** الصفحة الحالية من 0؛ بلا قيمةٍ يديرها الجدول. */
  page?: number
  onPageChange?: (page: number) => void
  /** عدد الصفوف كلّها إن كانت الصفحات من الخادم. */
  total?: number
  empty?: React.ReactNode
  className?: string
}

export function DataTable<T>({
  caption, columns, rows, rowKey, primary, secondary, trailing, onOpen, openLabel,
  pageSize = { compact: 10, gaze: 2, gazeShort: 1 }, page: controlled, onPageChange, total, empty, className,
}: DataTableProps<T>) {
  const { size } = useSize()
  const [own, setOwn] = React.useState(0)
  const page = controlled ?? own
  const perPage = usePageSize(pageSize)
  const serverPaged = total !== undefined
  const count = serverPaged ? total : rows.length
  const pages = Math.max(1, Math.ceil(count / perPage))
  const current = Math.min(page, pages - 1)
  const visible = serverPaged ? rows : rows.slice(current * perPage, current * perPage + perPage)

  function go(next: number) {
    const clamped = Math.max(0, Math.min(pages - 1, next))
    if (onPageChange) onPageChange(clamped)
    else setOwn(clamped)
  }

  if (count === 0) return <>{empty}</>

  const list = (
    <ul aria-label={caption} className={cn("flex flex-col gap-tg-min", onOpen && "gaze:gap-tg", size === "compact" && "tablet:hidden")}>
      {visible.map((row) => {
        const body = (
          <>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5 text-start">
              <span className="truncate font-semibold text-foreground">{primary(row)}</span>
              {secondary ? <span className="truncate text-small text-muted-foreground">{secondary(row)}</span> : null}
            </span>
            {trailing ? <span className="flex shrink-0 flex-col items-end gap-1">{trailing(row)}</span> : null}
            {onOpen ? <NextIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground/70" /> : null}
          </>
        )
        const box = "flex min-h-ctl w-full items-center gap-3 rounded-card border border-transparent bg-card px-3 py-2 shadow-card"
        return (
          <li key={rowKey(row)}>
            {onOpen ? (
              <button
                type="button"
                data-safe=""
                aria-label={openLabel?.(row)}
                onClick={() => onOpen(row)}
                className={cn(box, "hov:bg-muted")}
              >
                {body}
              </button>
            ) : (
              <div className={box}>{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )

  const table =
    size === "compact" ? (
      <div className="hidden overflow-hidden rounded-card bg-card shadow-card tablet:block">
        <table className="w-full border-collapse text-body">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-muted text-small text-muted-foreground">
            <tr>
              {columns.map((column) => (
                <th key={column.id} scope="col" className={cn("h-10 px-3 text-start font-semibold", column.numeric && "text-end", column.className)}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={rowKey(row)} className="h-row border-t border-border">
                {columns.map((column, index) => (
                  <td key={column.id} className={cn("px-3 py-1", column.numeric && "num text-end", column.className)}>
                    {index === 0 && onOpen ? (
                      <button
                        type="button"
                        data-safe=""
                        aria-label={openLabel?.(row)}
                        onClick={() => onOpen(row)}
                        className="-mx-2 inline-flex min-h-ctl items-center rounded-ctl px-2 font-semibold text-primary underline decoration-2 underline-offset-4 hov:bg-secondary"
                      >
                        {column.cell(row)}
                      </button>
                    ) : (
                      column.cell(row)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : null

  return (
    <div className={cn("flex flex-col gap-tg", className)}>
      {list}
      {table}
      {pages > 1 ? (
        // ثلاث خانات: الزرّان في الطرفين ورقم الصفحة بينهما نصٌّ لا هدف؛ يتّسعان في أضيق هاتفٍ بلا نصٍّ يخرج من زرّه.
        <nav aria-label={`صفحات ${caption}`} className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-tg-min">
          <Button icon={BackIcon} disabled={current === 0} onClick={() => go(current - 1)} className="justify-self-start">
            السابق
          </Button>
          <span className="num whitespace-nowrap text-small text-muted-foreground" aria-live="polite">
            <span className="gaze:hidden">الصفحة </span>
            {current + 1} من {pages}
          </span>
          <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => go(current + 1)} className="justify-self-end">
            التالي
          </Button>
        </nav>
      ) : null}
    </div>
  )
}
