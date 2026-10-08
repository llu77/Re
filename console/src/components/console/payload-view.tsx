import type { Json } from "@/lib/types"

/**
 * عرض الحمولة كما ستُسلَّم
 * ========================
 * ما يعتمده الممارس هو هذه البنية بعينها، فتُعرض كاملةً بلا انتقاء ولا
 * تلخيص: كل مفتاح وكل قيمة، بالترتيب الذي أرسله الخادم. لا يُفسَّر شيء ولا
 * يُخفى شيء — ما لا تعرضه الشاشة يُعتمد دون أن يُرى.
 *
 * النصّ يُعرض نصّاً (React يهرّب كل شيء)، و`dir="auto"` يترك لكل قيمة
 * اتجاهها: العربية من اليمين، والمصطلح اللاتيني من اليسار.
 */
export function PayloadView({ value, label }: { value: Json; label?: string }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  if (typeof value === "boolean") return <span>{value ? "نعم" : "لا"}</span>
  if (typeof value === "number") return <bdi dir="ltr">{value}</bdi>
  if (typeof value === "string") {
    return value === "" ? (
      <span className="text-muted-foreground">(نصّ فارغ)</span>
    ) : (
      <span dir="auto" className="whitespace-pre-wrap break-words">
        {value}
      </span>
    )
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">(قائمة فارغة)</span>
    return (
      <ol className="flex list-decimal flex-col gap-2 ps-6" aria-label={label}>
        {value.map((item, index) => (
          <li key={index}>
            <PayloadView value={item} />
          </li>
        ))}
      </ol>
    )
  }
  const entries = Object.entries(value)
  if (entries.length === 0) return <span className="text-muted-foreground">(لا حقول)</span>
  return (
    <dl className="flex flex-col gap-3" aria-label={label}>
      {entries.map(([key, item]) => (
        <div key={key} className="flex flex-col gap-1 border-s-2 border-border ps-3">
          <dt className="text-sm text-muted-foreground">
            <bdi dir="ltr" className="font-mono">
              {key}
            </bdi>
          </dt>
          <dd>
            <PayloadView value={item} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
