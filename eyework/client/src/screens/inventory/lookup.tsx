/*
 * «ابحث عن منتج» — أداةٌ في ورقة الأدوات
 * =====================================
 * تبحث بالاسم أو الرمز أو الباركود وتعرض بطاقة المنتج: رمزه ووحدته ورصيده وسعره، وآخر ثلاثة
 * أسعار شراءٍ مسجّلة (المستند وتاريخه ومورّده). لا تغادر الشاشة: مسودةٌ مفتوحة تبقى كما هي.
 * في الحجم الكبير ثلاث نتائج والحقل و«نتائج البحث»: أقلّ من اثني عشر هدفاً مع الورقة.
 */

import * as React from "react"
import { ArrowRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Field, Input } from "@/components/ui/input"
import { formatDay } from "@/lib/format"
import * as inv from "@/lib/inventory"
import { useSize } from "@/lib/size"

import { Money, Qty } from "./common"

export function ItemLookup() {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [query, setQuery] = React.useState("")
  const [items, setItems] = React.useState<inv.ItemOption[]>([])
  const [chosen, setChosen] = React.useState<inv.ItemDetail | null>(null)
  const [failure, setFailure] = React.useState<string | null>(null)
  const latest = React.useRef(0)

  // كل حرفٍ طلب، والردّ الأحدث وحده يُعرض (لا مؤقّت يؤجّل الطلب).
  React.useEffect(() => {
    const q = query.trim()
    if (!q) {
      setItems([])
      return
    }
    const seq = ++latest.current
    void inv.searchItems(q).then((result) => {
      if (seq !== latest.current) return
      setItems(result.status === 200 && result.data ? result.data.items : [])
    })
  }, [query])

  async function open(item: inv.ItemOption) {
    const result = await inv.getItem(item.id)
    if (result.status === 200 && result.data) {
      setChosen(result.data)
      setFailure(null)
    } else {
      setFailure("تعذّر فتح المنتج. حاول مرة أخرى.")
    }
  }

  if (chosen) {
    const prices = chosen.recent_purchases.slice(0, 3)
    return (
      <div className="flex flex-col gap-tg">
        <div className="flex flex-col gap-1 rounded-card border border-border bg-card p-pad">
          <p className="font-bold">{chosen.name}</p>
          <p className="text-small text-muted-foreground">
            <span className="num">{chosen.code}</span> · {chosen.unit_name}
          </p>
          <p className="text-small">
            الرصيد <Qty milli={chosen.on_hand_milli} unit={chosen.unit_name} className="font-semibold" /> · السعر{" "}
            <Money halalas={chosen.price_halalas} className="font-semibold" />
          </p>
        </div>
        <section aria-labelledby="lookup-prices" className="flex flex-col gap-1">
          <h3 id="lookup-prices" className="text-small font-bold">آخر أسعار الشراء</h3>
          {prices.length ? (
            <ul className="flex flex-col gap-1 text-small">
              {prices.map((p) => (
                <li key={`${p.document}-${p.invoice_date}`}>
                  {p.unit_price_halalas === null ? "—" : <Money halalas={p.unit_price_halalas} className="font-semibold" />} ·{" "}
                  <span className="num">{p.document}</span> · {formatDay(p.invoice_date)}
                  {p.supplier_name ? ` · ${p.supplier_name}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-small text-muted-foreground">لم يُشترَ بعد.</p>
          )}
        </section>
        <Button id="lookup-back" icon={ArrowRight} onClick={() => setChosen(null)}>
          نتائج البحث
        </Button>
      </div>
    )
  }

  const shown = items.slice(0, gaze ? 3 : 5)
  return (
    <div className="flex flex-col gap-tg">
      <Field label="الاسم أو الرمز أو الباركود">
        <Input id="lookup-query" value={query} maxLength={60} onChange={(event) => setQuery(event.target.value)} />
      </Field>
      {failure ? <p className="text-small text-destructive" role="alert">{failure}</p> : null}
      {query.trim() && !shown.length ? <p className="text-small text-muted-foreground">لا منتج بهذا البحث.</p> : null}
      {shown.length ? (
        <ul aria-label="المنتجات" className="flex flex-col gap-tg-min">
          {shown.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-safe=""
                aria-label={`افتح ${item.name}`}
                onClick={() => void open(item)}
                className="flex min-h-ctl w-full flex-col items-start justify-center rounded-card border border-control bg-card px-3 py-2 text-start hov:bg-muted"
              >
                <span className="font-semibold">{item.name}</span>
                <span className="text-small text-muted-foreground">
                  <span className="num">{item.code}</span> · <Qty milli={item.on_hand_milli} unit={item.unit_name} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
