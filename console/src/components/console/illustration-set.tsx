import { exerciseLabel, sideLabel } from "@/lib/labels"
import type { AffectedSide, Json } from "@/lib/types"

import { ErrorNotice } from "./feedback"

/**
 * الرسوم كما سيراها المريض
 * ========================
 * مجموعة الرسوم تُعتمد من الصورة لا من ترميزها: آلاف الحروف من SVG لا تُظهر
 * أيّ جانبٍ يعلّمه الرسم، وهو ما يعتمده الممارس فعلاً.
 *
 * الفحص فحص بوابة المريض نفسه (`drawIllustration` في `portal/app.js`): جذرٌ
 * SVG، ولا خطأ تحليل، ولا سكربت ولا `foreignObject` ولا صورة، ولا معالج حدث
 * ولا مرجع. ما لا يجتازه لا يُرسم هناك، فلا يُرسم هنا ولا يُعرض اعتماده.
 *
 * ويُعرض ما اجتاز صورةً (`<img>` بعنوان `data:`) لا عناصر في الصفحة: الـSVG
 * داخل `<img>` لا ينفّذ شيفرة ولا يجلب مورداً، وسياسة المحتوى تسمح بـ`data:`
 * للصور وحدها.
 */

const SVG_NAMESPACE = "http://www.w3.org/2000/svg"

export interface Drawing {
  exerciseType: string
  /** عنوان الصورة، أو `null` إن لم يجتز الرسم الفحص فلا يُعرض. */
  source: string | null
}

function imageSource(markup: string): string | null {
  let parsed: Document
  try {
    parsed = new DOMParser().parseFromString(markup, "image/svg+xml")
  } catch {
    return null
  }
  const root = parsed.documentElement
  // بلا فضاء أسماء SVG لا يُرسم شيء، لا هنا ولا عند المريض.
  if (!root || root.localName !== "svg" || root.namespaceURI !== SVG_NAMESPACE) return null
  if (parsed.getElementsByTagName("parsererror").length > 0) return null

  for (const element of [root, ...Array.from(root.querySelectorAll("*"))]) {
    const name = element.localName.toLowerCase()
    if (name === "script" || name === "foreignobject" || name === "image") return null
    for (const attribute of element.getAttributeNames()) {
      const lowered = attribute.toLowerCase()
      if (lowered.startsWith("on") || lowered.endsWith("href")) return null
    }
  }
  const checked = new XMLSerializer().serializeToString(root)
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(checked)}`
}

/**
 * رسوم الحمولة بالترتيب الذي أرسله الخادم. حمولةٌ بلا قائمة `illustrations`
 * تعطي قائمةً فارغة، وعنصرٌ بلا `svg` نصّي يُعدّ رسماً لا يُعرض.
 */
export function drawingsOf(payload: Record<string, Json>): Drawing[] {
  const items = payload.illustrations
  if (!Array.isArray(items)) return []
  return items.map((item) => {
    const entry = item !== null && typeof item === "object" && !Array.isArray(item) ? item : {}
    const exerciseType = typeof entry.exercise_type === "string" ? entry.exercise_type : ""
    return {
      exerciseType,
      source: typeof entry.svg === "string" ? imageSource(entry.svg) : null,
    }
  })
}

/** الاعتماد يُعرض حين يُرى كل ما سيصل: رسمٌ واحدٌ على الأقل، وكلّها تُرسم. */
export const allDrawn = (drawings: Drawing[]) =>
  drawings.length > 0 && drawings.every((drawing) => drawing.source !== null)

export function IllustrationSet({
  drawings,
  side,
}: {
  drawings: Drawing[]
  side: AffectedSide | null
}) {
  if (drawings.length === 0) {
    return <ErrorNotice message="لا رسوم في هذه المجموعة، فلا يُعرض اعتمادها." />
  }
  return (
    <ol className="flex flex-col gap-4" aria-label="الرسوم كما سيراها المريض">
      {drawings.map((drawing, index) => {
        const label = drawing.exerciseType ? exerciseLabel(drawing.exerciseType) : "رسمٌ بلا نوع"
        return (
          <li key={index}>
            <figure className="flex flex-col gap-2">
              {drawing.source ? (
                <img
                  src={drawing.source}
                  alt={`${label}، كما سيراه المريض`}
                  className="h-auto w-full max-w-xl rounded-md border"
                />
              ) : (
                <ErrorNotice message="لا يمكن عرض هذا الرسم كما سيراه المريض، فلا يُعرض اعتماد المجموعة." />
              )}
              <figcaption>
                <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="text-muted-foreground">التمرين</dt>
                    <dd className="min-w-0 [overflow-wrap:anywhere]">
                      {label}{" "}
                      {drawing.exerciseType && label !== drawing.exerciseType ? (
                        <bdi dir="ltr" className="font-mono text-muted-foreground">
                          {drawing.exerciseType}
                        </bdi>
                      ) : null}
                    </dd>
                  </div>
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="text-muted-foreground">الجانب المصاب</dt>
                    <dd>{side ? sideLabel(side) : "غير محدّد"}</dd>
                  </div>
                </dl>
              </figcaption>
            </figure>
          </li>
        )
      })}
    </ol>
  )
}
