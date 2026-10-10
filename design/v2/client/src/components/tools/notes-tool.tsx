/*
 * ملاحظات سريعة
 * =============
 * سطورٌ قصيرة يكتبها الموظف لنفسه أثناء العمل («اتّصل بالمورد بخصوص الكراسي»). تُحفظ في
 * حسابه على الخادم (جدول quick_notes بعزل الصفوف) لا في المتصفّح: التطبيق لا يخزّن في
 * الجهاز شيئاً. حدٌّ للعدد وللطول من الخادم، والحذف بخطوتين في مكانه.
 */

import * as React from "react"
import { Save, Trash2 } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Textarea } from "@/components/ui/input"
import { formatDay, formatTime } from "@/lib/format"
import { useSize } from "@/lib/size"

export interface Note {
  id: string
  text: string
  created_at: string
}

type Result<T> = ({ ok: true } & T) | { ok: false; message: string }

export interface NotesApi {
  max: number
  maxLength: number
  load: () => Promise<Result<{ notes: Note[] }>>
  add: (text: string) => Promise<Result<{ note: Note }>>
  remove: (id: string) => Promise<Result<object>>
}

export function NotesTool({ api }: { api: NotesApi }) {
  const { size } = useSize()
  const [notes, setNotes] = React.useState<Note[] | null>(null)
  const [text, setText] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [confirming, setConfirming] = React.useState<string | null>(null)
  const [page, setPage] = React.useState(0)

  React.useEffect(() => {
    let live = true
    void api.load().then((result) => {
      if (!live) return
      if (result.ok) setNotes(result.notes)
      else setError(result.message)
    })
    return () => {
      live = false
    }
  }, [api])

  const length = [...text].length
  const full = notes !== null && notes.length >= api.max
  const perPage = size === "gaze" ? 2 : 50
  const pages = Math.max(1, Math.ceil((notes?.length ?? 0) / perPage))
  const current = Math.min(page, pages - 1)
  const visible = notes?.slice(current * perPage, current * perPage + perPage) ?? []

  async function save(event: React.FormEvent) {
    event.preventDefault()
    const value = text.trim()
    if (!value || length > api.maxLength || busy || full) return
    setBusy(true)
    setError(null)
    const result = await api.add(value)
    setBusy(false)
    if (result.ok) {
      setNotes((list) => [result.note, ...(list ?? [])])
      setText("")
      setPage(0)
    } else {
      setError(result.message)
    }
  }

  async function remove(id: string) {
    setBusy(true)
    setError(null)
    const result = await api.remove(id)
    setBusy(false)
    setConfirming(null)
    if (result.ok) setNotes((list) => (list ?? []).filter((note) => note.id !== id))
    else setError(result.message)
  }

  return (
    <div className="flex flex-col gap-tg">
      <form noValidate onSubmit={save} className="flex flex-col gap-tg-min">
        <Field
          label="ملاحظةٌ جديدة"
          hint={
            full ? (
              `بلغتَ ${api.max} ملاحظة: احذف واحدةً لتضيف.`
            ) : (
              <>
                <span className="num">{length}</span> من <span className="num">{api.maxLength}</span>
              </>
            )
          }
          error={length > api.maxLength ? `أطول من ${api.maxLength} حرف.` : null}
        >
          <Textarea rows={2} value={text} onChange={(event) => setText(event.target.value)} disabled={full} />
        </Field>
        <Button type="submit" variant="primary" commit icon={Save} busy={busy && confirming === null} disabled={!text.trim() || length > api.maxLength || full}>
          احفظ الملاحظة
        </Button>
      </form>
      {error ? (
        <Alert tone="danger" title="لم يتمّ" live>
          {error}
        </Alert>
      ) : null}
      {notes === null ? (
        <p role="status" className="text-small text-muted-foreground">
          تُقرأ ملاحظاتك…
        </p>
      ) : notes.length === 0 ? (
        <EmptyState icon={Save} title="لا ملاحظات بعد" description="ما تكتبه هنا يبقى في حسابك حتى تحذفه." />
      ) : (
        <ul aria-label="ملاحظاتك" className="flex flex-col gap-tg-min">
          {visible.map((note) => (
            <li key={note.id} className="flex flex-col gap-2 rounded-card border border-border bg-card p-3">
              <p className="whitespace-pre-line text-foreground">{note.text}</p>
              <div className="flex flex-wrap items-center justify-between gap-tg-min">
                <span className="text-small text-muted-foreground">
                  {formatDay(note.created_at)} · {formatTime(note.created_at)}
                </span>
                {confirming === note.id ? (
                  <span className="flex gap-tg-min">
                    <Button onClick={() => setConfirming(null)}>لا</Button>
                    <Button variant="danger" commit icon={Trash2} busy={busy} onClick={() => void remove(note.id)}>
                      احذفها
                    </Button>
                  </span>
                ) : (
                  <Button variant="danger-outline" icon={Trash2} onClick={() => setConfirming(note.id)}>
                    احذف
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {pages > 1 ? (
        <div className="flex items-center justify-between gap-tg">
          <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>
            السابقة
          </Button>
          <span className="num whitespace-nowrap text-small text-muted-foreground">
            {current + 1} / {pages}
          </span>
          <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            التالية
          </Button>
        </div>
      ) : null}
    </div>
  )
}
