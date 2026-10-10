/*
 * AIFlag — تنبيه سيمبول
 * =====================
 * ما طلبه المالك: إذا كان الإجراء خاطئاً «يظهر رفعٌ مع رسالة الذكاء باسم المستخدم وسبب
 * الخطأ». والقاعدة: النظام يقترح ولا يقرّر.
 *   • الرسالة «يا {الاسم}، …» — والاسم من قاعدة التطبيق، لا من النموذج: اسم المستخدم لا يصل
 *     مزوّد النموذج أبداً (prompt.py، PERSONA). يضيفه هنا `name`، أو يرسله الخادم في النصّ
 *     جاهزاً (inventory_flags.render) فلا يُمرَّر `name` ولا يُكرَّر النداء.
 *   • مصدره شارةٌ بنصّ: «مراجعة سيمبول» للنموذج (لون ai)، و«تنبيه» لقاعدةٍ في التطبيق.
 *   • السبب سطرٌ مستقلّ «السبب: …»، والشواهد إن وُجدت («آخر 3 فواتير: …»).
 *   • قراران للمستخدم وحده: «عدّل» يعيده إلى الحقل المعنيّ (آمن)، و«تابع رغم ذلك» يُسجَّل
 *     مع العملية أنه رأى التنبيه وقرّر (`data-commit`). لا قرار ثالث يتّخذه النظام.
 *     وفي مراجعةٍ تجمع تنبيهاتٍ كثيرة يكون القرار مرّةً واحدة أسفلها (inventory_spec §3.6):
 *     تُرسم البطاقة بلا قرار (`onEdit` و`onProceed` غائبان) وفيها «اذهب إلى السطر 3» (`goTo`).
 *   • بعد «تابع رغم ذلك» يبقى سطرٌ يقول ذلك، و«تراجع» يعيد التنبيه مفتوحاً.
 *   • القاعدة الثابتة (رصيدٌ لا يكفي، مبلغٌ سالب) ليست تنبيهاً: ذاك رفضٌ من الخادم في
 *     الحقل نفسه. هذا لما يمكن ويُستغرب.
 *   • الترتيب: «عدّل» في البداية و«تابع رغم ذلك» في النهاية، في الجزء الأعلى من الخطوة،
 *     بعيداً عن زرّ التسجيل في أسفلها: ما ضُغط لتظهر المراجعة لا يقع تحته ما يعتمد.
 *   • الحجم الكبير (`actionsFirst`): التنبيه وحده في شاشته، والقراران تحت رأسه مباشرةً، ثم الرسالة والسبب نصٌّ
 *     واحد يُقسم صفحاتٍ عند الحاجة وأزرار صفحاته في أسفل البطاقة (PagedText): أطول رسالةٍ تتّسع في أضيق هاتف
 *     بلا قصّ، وما يُضغط في أسفل الشاشة («التالي» في الشريط أو في الصفحات) بعيدٌ عن «تابع رغم ذلك».
 */

import * as React from "react"
import { AlertTriangle, CheckCircle2, CornerDownLeft, PencilLine, Sparkles, Undo2 } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PagedText } from "@/components/ui/paged-text"
import { cn } from "@/lib/utils"

export type FlagStatus = "open" | "acknowledged"

export interface AIFlagProps {
  /** اسم المستخدم من /api/me، أو null حين لم يضعه أو حين النداء في النصّ من الخادم. */
  name: string | null
  /** «ai»: من النموذج (الافتراضي). «rule»: من قاعدةٍ في التطبيق. */
  source?: "ai" | "rule"
  /** انتقالٌ آمن إلى ما يخصّه التنبيه: «اذهب إلى السطر 3». */
  goTo?: { label: string; onSelect: () => void }
  /** رسالة المراجِع بلا نداء: «سعر الوحدة أعلى بعشرة أضعاف من آخر شراء.» */
  message: string
  reason: string
  evidence?: string[]
  /** ما يخصّه التنبيه: «السطر 2: كرسي مكتب دوّار». */
  subject?: string
  status?: FlagStatus
  /** بلا `onEdit` و`onProceed` لا قرار في البطاقة: القرار أسفل المراجعة. */
  onEdit?: () => void
  onProceed?: () => void
  onUndo?: () => void
  /** الحجم الكبير: القراران تحت رأس البطاقة والنصّ بصفحاتٍ تحتهما، فيبعدان عن شريط الإجراءات أسفل
   *  الشاشة، حيث كان «راجع» الذي أظهر التنبيه. */
  actionsFirst?: boolean
  className?: string
}

/** «يا سارة، …» أو الرسالة كما هي. الفاصلة العربية بعد الاسم، ولا نداءٌ على نداء. */
export function addressed(name: string | null, message: string): string {
  const trimmed = name?.trim()
  if (!trimmed || message.startsWith("يا ")) return message
  return `يا ${trimmed}، ${message}`
}

export function AIFlag({
  name, source = "ai", goTo, message, reason, evidence, subject, status = "open", onEdit, onProceed, onUndo,
  actionsFirst = false, className,
}: AIFlagProps) {
  const titleId = React.useId()
  const done = status === "acknowledged"
  const decides = Boolean(onEdit && onProceed)
  const actions = !decides ? null : (
    <div className="mt-1 grid grid-cols-2 items-center gap-tg gaze:gap-x-6">
      {done ? (
        <>
          {onUndo ? (
            <Button icon={Undo2} onClick={onUndo}>
              تراجع
            </Button>
          ) : (
            <span />
          )}
          <p role="status" className="text-small font-semibold text-foreground">
            تابعتَ رغم التنبيه، ويُحفظ قرارك مع العملية.
          </p>
        </>
      ) : (
        <>
          <Button variant="secondary" icon={PencilLine} onClick={onEdit}>
            عدّل
          </Button>
          <Button commit onClick={onProceed} className="border-warning-line">
            تابع رغم ذلك
          </Button>
        </>
      )}
    </div>
  )
  const label = (
    <span className="flex shrink-0 items-center gap-2 text-small font-bold text-foreground">
      <span className="flex size-7 items-center justify-center rounded-ctl bg-card">
        <SymbolMark className="size-4" />
      </span>
      {source === "ai" ? "تنبيه من سيمبول" : "تنبيه"}
    </span>
  )
  const tone = done ? "border-transparent bg-muted" : "border-warning-line/40 bg-warning-tint"
  const text = addressed(name, message)

  if (actionsFirst) {
    // الحجم الكبير: البطاقة تملأ شاشتها، وما يخصّه التنبيه («السطر 2: …») في طرف رأسها.
    return (
      <section
        role="group"
        aria-label={text}
        data-flag-status={status}
        className={cn("flex min-h-0 flex-1 flex-col gap-2 rounded-card border px-3 py-2.5", tone, className)}
      >
        <header className="flex items-center justify-between gap-2">
          {label}
          {subject ? <p className={cn("min-w-0 truncate text-small font-semibold", done ? "text-muted-foreground" : "text-warning")}>{subject}</p> : null}
        </header>
        {actions}
        <PagedText
          fill
          label="التنبيه"
          text={`${text}\nالسبب: ${reason}`}
          perPage={{ gaze: 120, gazeShort: 60 }}
          className={cn("font-semibold", done ? "text-muted-foreground" : "text-foreground")}
        />
      </section>
    )
  }

  // الحالتان بالارتفاع نفسه والترتيب نفسه: بعد «تابع رغم ذلك» لا يتحرّك شيءٌ تحت النظر،
  // ويحلّ في موضعها نصٌّ لا يُضغط، و«تراجع» في موضع «عدّل».
  return (
    <section
      role="group"
      aria-labelledby={titleId}
      data-flag-status={status}
      className={cn("flex flex-col gap-3 rounded-card border p-pad", tone, className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        {label}
        {done ? (
          <Badge tone="neutral" icon={CheckCircle2} className="gaze:hidden">
            قرّرتَ المتابعة
          </Badge>
        ) : source === "ai" ? (
          <Badge tone="ai" icon={Sparkles} className="gaze:hidden">
            مراجعة سيمبول
          </Badge>
        ) : (
          <Badge tone="warning" icon={AlertTriangle} className="gaze:hidden">
            قاعدة في التطبيق
          </Badge>
        )}
      </header>
      {subject ? <p className={cn("text-small font-semibold", done ? "text-muted-foreground" : "text-warning")}>{subject}</p> : null}
      <p id={titleId} className={cn("font-semibold leading-snug", done ? "text-muted-foreground" : "text-foreground")}>
        {text}
      </p>
      <p className="text-small text-foreground">
        <span className="font-semibold">السبب: </span>
        {reason}
      </p>
      {evidence && evidence.length > 0 ? (
        <ul className="flex list-disc flex-col gap-0.5 ps-5 text-small text-muted-foreground">
          {evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
      {goTo ? (
        <div>
          <Button icon={CornerDownLeft} onClick={goTo.onSelect}>
            {goTo.label}
          </Button>
        </div>
      ) : null}
      {actions}
    </section>
  )
}
