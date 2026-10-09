/*
 * PagedText — نصٌّ طويل بلا تمرير
 * ===============================
 * في الحجم الكبير لا تمرّ الشاشة، والنصّ الطويل (جواب سيمبول، مسوّدة ردّ) لا يُقصّ: يُقسم
 * صفحاتٍ عند نهايات الجمل، وتحته «السابق» و«التالي» ورقم الصفحة. وفي الحجم العادي يُعرض
 * كلّه (الصفحة تمرّ). التقسيم بعدد الحروف لا بقياس الشاشة: لا يتغيّر وحده بعد الرسم.
 */

import * as React from "react"

import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { useShortScreen, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

/** الجمل: تنتهي بنقطةٍ أو علامة استفهامٍ أو تعجّبٍ يليها فراغ، أو بسطرٍ جديد. «ر.س» و«5,200.00»
 *  لا تنتهي عندهما جملة. */
export function sentences(text: string): string[] {
  const out: string[] = []
  let start = 0
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i]
    const next = text[i + 1]
    const end = ch === "\n" || (".!؟?".includes(ch) && (next === undefined || /\s/.test(next)))
    if (end) {
      let j = i + 1
      while (j < text.length && /\s/.test(text[j]) && text[j] !== "\n") j += 1
      out.push(text.slice(start, j))
      start = j
      i = j - 1
    }
  }
  if (start < text.length) out.push(text.slice(start))
  return out
}

/** يقسم النصّ صفحاتٍ لا تزيد كلٌّ منها على `max` حرفاً إلا جملةً واحدةً أطول منه. */
export function paginate(text: string, max: number): string[] {
  const pages: string[] = []
  let current = ""
  for (const sentence of sentences(text)) {
    if (current && [...current].length + [...sentence].length > max) {
      pages.push(current.trim())
      current = ""
    }
    current += sentence
  }
  if (current.trim()) pages.push(current.trim())
  return pages.length ? pages : [""]
}

export interface PagedTextProps {
  text: string
  /** حروف الصفحة في الحجم الكبير: الشاشة الطويلة ثم القصيرة. */
  perPage?: { gaze: number; gazeShort: number }
  className?: string
  /** اسم النصّ لقارئ الشاشة في أزرار الصفحات: «جواب سيمبول». */
  label: string
}

export function PagedText({ text, perPage = { gaze: 320, gazeShort: 160 }, className, label }: PagedTextProps) {
  const { size } = useSize()
  const short = useShortScreen()
  const pages = size === "gaze" ? paginate(text, short ? perPage.gazeShort : perPage.gaze) : [text]
  const [page, setPage] = React.useState(0)
  const current = Math.min(page, pages.length - 1)
  return (
    <div className="flex flex-col gap-tg">
      <p className={cn("text-flow whitespace-pre-line", className)} aria-live={pages.length > 1 ? "polite" : undefined}>
        {pages[current]}
      </p>
      {pages.length > 1 ? (
        <nav aria-label={`صفحات ${label}`} className="flex items-center justify-between gap-tg">
          <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>
            السابق
          </Button>
          <span className="num whitespace-nowrap text-small text-muted-foreground">
            {current + 1} من {pages.length}
          </span>
          <Button iconEnd={NextIcon} disabled={current >= pages.length - 1} onClick={() => setPage(current + 1)}>
            التالي
          </Button>
        </nav>
      ) : null}
    </div>
  )
}
