/*
 * «عبارات وأسئلة جاهزة» — أداة مكتب الدعم في ورقة الأدوات
 * =======================================================
 * العبارات القصيرة التي تتكرّر في الردود، والأسئلة التي تُطلب بها المعلومات، بالعربية أو بالإنجليزية كما
 * يحفظها الخادم (support_rules.PHRASES وQUESTIONS). «انسخ» يضعها في الحافظة لتُلصق في محادثة العميل أو في
 * محرّر الردّ. ثلاثٌ في الصفحة (اثنتان في الحجم الكبير): الورقة لا تمرّ تحت زرّ «كل الأدوات».
 */

import * as React from "react"
import { Copy } from "lucide-react"

import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Tabs } from "@/components/ui/tabs"
import { usePageSize, useSize } from "@/lib/size"

export interface PhraseEntry {
  id: string
  ar: string
  en: string
}

type Loaded = { phrases: PhraseEntry[]; questions: PhraseEntry[] }

export function PhrasesTool({ load }: { load: () => Promise<Loaded | { fail: string }> }) {
  const [data, setData] = React.useState<Loaded | null>(null)
  const [fail, setFail] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)
  const [tab, setTab] = React.useState<"phrases" | "questions">("phrases")
  const [english, setEnglish] = React.useState(false)
  const [page, setPage] = React.useState(0)
  const [copied, setCopied] = React.useState<string | null>(null)
  const size = usePageSize({ compact: 3, gaze: 2, gazeShort: 1 })
  const gaze = useSize().size === "gaze"
  React.useEffect(() => {
    let current = true
    void load().then((result) => {
      if (!current) return
      if ("fail" in result) setFail(result.fail)
      else setData(result)
    })
    return () => {
      current = false
    }
  }, [load, attempt])
  if (fail && !data) {
    return (
      <div className="flex flex-col gap-tg">
        <p role="alert" className="text-small font-semibold text-destructive">{fail}</p>
        <Button id="phrases-retry" onClick={() => { setFail(null); setAttempt(attempt + 1) }}>حاول مرةً أخرى</Button>
      </div>
    )
  }
  if (!data) return <p className="text-small text-muted-foreground">تُقرأ العبارات…</p>
  const items = tab === "phrases" ? data.phrases : data.questions
  const pages = Math.max(1, Math.ceil(items.length / size))
  const current = Math.min(page, pages - 1)
  const visible = items.slice(current * size, current * size + size)

  async function copy(entry: PhraseEntry) {
    try {
      await navigator.clipboard.writeText(english ? entry.en : entry.ar)
      setCopied(entry.id)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="flex flex-col gap-tg">
      <Tabs
        items={[{ id: "phrases", label: "عبارات" }, { id: "questions", label: "أسئلة" }]}
        value={tab}
        onValueChange={(id) => { setTab(id as "phrases" | "questions"); setPage(0); setCopied(null) }}
        label="عبارات وأسئلة"
        stretch
      >
        {/* كل عبارةٍ زرٌّ واحد ينسخها: صفٌّ بسطرين على الأكثر، فتتّسع الصفحة في الورقة بلا تمرير. */}
        <ul aria-label={tab === "phrases" ? "عبارات جاهزة" : "أسئلة جاهزة"} className="flex flex-col gap-tg">
          {visible.map((entry) => (
            <li key={entry.id}>
              <Button id={`phrase-copy-${entry.id}`} data-wrap="" icon={Copy} width="full" onClick={() => void copy(entry)} className="justify-start whitespace-normal py-2 text-start font-normal leading-snug">
                <span className="line-clamp-2" dir={english ? "ltr" : "rtl"}>{english ? entry.en : entry.ar}</span>
              </Button>
            </li>
          ))}
        </ul>
      </Tabs>
      {gaze ? (
        // الحجم الكبير: ثلاثة أزرارٍ لا تتّسع في صفٍّ بعرض 288: اللغة صفٌّ ومعها سطر «نُسخت»، والصفحات صفٌّ تحته.
        <>
          <div className="flex items-center gap-x-6">
            <Button id="phrases-language" isValue onClick={() => setEnglish(!english)}>{english ? "بالعربية" : "بالإنجليزية"}</Button>
            <p role="status" className="min-w-0 text-small font-semibold text-success">{copied ? "نُسخت." : ""}</p>
          </div>
          {pages > 1 ? (
            <div className="grid grid-cols-2 gap-x-6">
              <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>السابق</Button>
              <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>التالي</Button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p role="status" className="min-h-[1lh] text-small font-semibold text-success">{copied ? "نُسخت." : ""}</p>
          <div className="flex items-center justify-between gap-tg">
            {pages > 1 ? (
              <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>السابق</Button>
            ) : <span aria-hidden="true" />}
            <Button id="phrases-language" isValue onClick={() => setEnglish(!english)}>{english ? "بالعربية" : "بالإنجليزية"}</Button>
            {pages > 1 ? (
              <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>التالي</Button>
            ) : <span aria-hidden="true" />}
          </div>
        </>
      )}
    </div>
  )
}
