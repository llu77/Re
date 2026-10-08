import * as React from "react"
import { Siren } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { ApiError, PAGE_SIZE, type PractitionerApi } from "@/lib/api"
import { formatDateTime, formatRelative, shortId } from "@/lib/labels"
import type { RedFlag } from "@/lib/types"

import { ErrorNotice, LoadingList } from "./feedback"

const NOTE_MAX = 2000

/**
 * البلاغات العاجلة: ما كتبه المرضى ولم يستلمه ممارسٌ بعد، الأقدم أولاً.
 * الاستلام يُسجَّل مرةً واحدة ومنه يُحسب زمن التصعيد، فهو خطوتان أيضاً.
 *
 * القائمة صفحةٌ من `PAGE_SIZE`، والأقدم أولاً: ما لا يُعرض هو الأحدث. يُقال
 * ذلك فوقها بلونها، لا يُترك العدد يوحي بأنه الكلّ.
 */
export function RedFlagsPage({
  api,
  items,
  more,
  error,
  onAcknowledged,
}: {
  api: PractitionerApi
  items: RedFlag[] | null
  more: boolean
  error: string | null
  onAcknowledged: (message: string) => void
}) {
  if (error && !items) return <ErrorNotice message={error} />
  if (!items) return <LoadingList label="جارٍ تحميل البلاغات" />
  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
        لا بلاغات عاجلة غير مستلَمة.
      </p>
    )
  }

  const now = new Date()
  return (
    <>
      {more ? (
        <p className="rounded-md border-2 border-destructive/40 bg-destructive/5 p-3 text-destructive">
          تُعرض أقدم {PAGE_SIZE} بلاغاً، وبعدها بلاغاتٌ أحدث لم تُستلَم بعد. تظهر هنا كلما استُلم
          بلاغٌ مما يُعرض.
        </p>
      ) : null}
      <ol className="flex flex-col gap-4" aria-label="البلاغات غير المستلَمة">
        {items.map((flag) => (
          <li key={flag.id}>
            <FlagCard api={api} flag={flag} now={now} onAcknowledged={onAcknowledged} />
          </li>
        ))}
      </ol>
    </>
  )
}

function FlagCard({
  api,
  flag,
  now,
  onAcknowledged,
}: {
  api: PractitionerApi
  flag: RedFlag
  now: Date
  onAcknowledged: (message: string) => void
}) {
  const [open, setOpen] = React.useState(false)
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const noteId = `note-${flag.id}`
  const titleId = `flag-${flag.id}`
  // التركيز يتبع الخطوة، كما في صفحة المقترح.
  const noteField = React.useRef<HTMLTextAreaElement>(null)
  const openButton = React.useRef<HTMLButtonElement>(null)
  const wasOpen = React.useRef<boolean | null>(null)

  React.useEffect(() => {
    const previous = wasOpen.current
    wasOpen.current = open
    if (previous === null) return
    if (open) noteField.current?.focus()
    else openButton.current?.focus()
  }, [open])

  async function acknowledge() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await api.acknowledge(flag.id, note.trim() || null)
      onAcknowledged("سُجّل استلام البلاغ.")
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تسجيل الاستلام.")
      setBusy(false)
    }
  }

  return (
    <article aria-labelledby={titleId} className="flex flex-col gap-3 rounded-lg border-2 border-destructive/40 bg-card p-4">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h2 id={titleId} className="inline-flex items-center gap-2 font-bold text-destructive">
          <Siren className="size-5" aria-hidden="true" />
          بلاغ <span title={formatDateTime(flag.reported_at)}>{formatRelative(flag.reported_at, now)}</span>
        </h2>
        <p className="text-sm text-muted-foreground">
          المريض{" "}
          <bdi dir="ltr" className="font-mono" title={flag.patient_id}>
            {shortId(flag.patient_id)}
          </bdi>
        </p>
      </header>

      <blockquote className="whitespace-pre-wrap break-words border-s-4 border-destructive/40 ps-3 text-lg" dir="auto">
        {flag.body}
      </blockquote>

      {!open ? (
        <div>
          <Button ref={openButton} className="h-12 min-w-36 text-base" onClick={() => setOpen(true)}>
            استلام البلاغ
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <Label htmlFor={noteId} className="text-base">
            ملاحظة (اختيارية)
          </Label>
          <textarea
            id={noteId}
            ref={noteField}
            value={note}
            maxLength={NOTE_MAX}
            rows={3}
            dir="auto"
            onChange={(event) => setNote(event.target.value)}
            className="w-full rounded-md border border-input bg-background p-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex flex-wrap gap-3">
            <Button className="h-12 min-w-36 text-base" aria-disabled={busy} onClick={acknowledge}>
              {busy ? "جارٍ التسجيل…" : "تأكيد الاستلام"}
            </Button>
            <Button
              variant="outline"
              className="h-12 min-w-36 text-base"
              aria-disabled={busy}
              onClick={() => {
                if (busy) return
                setOpen(false)
                setNote("")
              }}
            >
              تراجع
            </Button>
          </div>
        </div>
      )}

      {error ? <ErrorNotice message={error} /> : null}
    </article>
  )
}
