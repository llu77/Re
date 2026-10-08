import { ChevronLeft, Flag } from "lucide-react"

import { PAGE_SIZE } from "@/lib/api"
import { formatDateTime, formatRelative, kindLabel, shortId, sideLabel } from "@/lib/labels"
import type { Proposal } from "@/lib/types"

import { ErrorNotice, LoadingList } from "./feedback"
import { href } from "./route"

/**
 * طابور المراجعة: ما ينتظر قرار الممارس، بترتيب الخادم نفسه — العلامات
 * الحمراء أولاً، ثم الأولوية، ثم زمن الانتظار. الواجهة لا تعيد الفرز.
 *
 * لا اختيار متعدّد ولا «اعتماد الكل»: كل قرارٍ في صفحة المقترح وحده، كما
 * تفرض البوابة (لا نقطة نهاية تقبل مصفوفة معرّفات).
 *
 * الطابور صفحةٌ من `PAGE_SIZE`؛ إن كان بعدها غيرها قيل ذلك فوقها.
 */
export function QueuePage({
  items,
  more,
  error,
}: {
  items: Proposal[] | null
  more: boolean
  error: string | null
}) {
  if (error && !items) return <ErrorNotice message={error} />
  if (!items) return <LoadingList label="جارٍ تحميل الطابور" />
  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
        لا مقترحات بانتظار المراجعة.
      </p>
    )
  }

  const now = new Date()
  return (
    <>
      {more ? (
        <p className="rounded-md border border-primary/30 bg-accent p-3">
          يُعرض أول {PAGE_SIZE} مقترحاً بترتيب الطابور، وبعدها مقترحاتٌ أخرى بانتظار المراجعة.
          كل قرارٍ يُفسح للتالي.
        </p>
      ) : null}
      <ol className="flex flex-col gap-3" aria-label="المقترحات بانتظار المراجعة">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={href({ name: "proposal", id: item.id })}
              className="group flex min-h-12 items-center gap-4 rounded-lg border bg-card p-4 outline-none ring-offset-background transition-colors hover:border-primary/50 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-lg font-bold">{kindLabel(item.kind)}</span>
                  {item.is_red_flag ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-destructive px-2.5 py-0.5 text-sm text-destructive-foreground">
                      <Flag className="size-4" aria-hidden="true" />
                      علامة حمراء
                    </span>
                  ) : null}
                  <span className="rounded-full bg-secondary px-2.5 py-0.5 text-sm">
                    الأولوية {item.priority}
                  </span>
                </div>
                <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
                  <div className="flex gap-1">
                    <dt>المريض</dt>
                    <dd>
                      <bdi dir="ltr" className="font-mono" title={item.patient_id}>
                        {shortId(item.patient_id)}
                      </bdi>
                    </dd>
                  </div>
                  {item.affected_side ? (
                    <div className="flex gap-1">
                      <dt className="sr-only">الجانب المصاب</dt>
                      <dd>{sideLabel(item.affected_side)}</dd>
                    </div>
                  ) : null}
                  <div className="flex gap-1">
                    <dt>في الطابور</dt>
                    <dd title={formatDateTime(item.queued_at)}>{formatRelative(item.queued_at, now)}</dd>
                  </div>
                  <div className="flex gap-1">
                    <dt>تنتهي مهلته</dt>
                    <dd title={formatDateTime(item.expires_at)}>{formatRelative(item.expires_at, now)}</dd>
                  </div>
                </dl>
              </div>
              <ChevronLeft
                className="size-5 shrink-0 text-muted-foreground group-hover:text-primary"
                aria-hidden="true"
              />
            </a>
          </li>
        ))}
      </ol>
    </>
  )
}
