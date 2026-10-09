/*
 * Toast — رسالةٌ بعد فعل
 * =====================
 * الأصل: نمط sonner/shadcn toast، بقاعدة الواجهة: لا شيء يتغيّر وحده.
 *   • لا تختفي الرسالة بمؤقّت: تبقى حتى «إغلاق»، أو حتى تحلّ محلّها رسالةٌ أحدث، أو
 *     ينتقل المستخدم إلى قسمٍ آخر. رسالةٌ تختفي قبل أن تُقرأ بالنظر لم تُقل.
 *   • رسالةٌ واحدة في وقتٍ واحد، في أعلى المحتوى تحت الرأس، فوقه لا داخله: ظهورها لا
 *     يحرّك هدفاً تحت نظرٍ باقٍ.
 *   • «إغلاق» وحده فيها، ولا زرّ يعتمد: ما يُعتمد يُعتمد في الشاشة لا في رسالة.
 *   • تُعلَن بمنطقةٍ حيّة مهذّبة (role="status")؛ والخطأ بـrole="alert".
 */

import * as React from "react"
import { CheckCircle2, Info, OctagonAlert, X } from "lucide-react"

import { cn } from "@/lib/utils"

export type ToastTone = "success" | "info" | "danger"

export interface ToastMessage {
  title: string
  description?: string
  tone?: ToastTone
}

interface ToastContextValue {
  show: (message: ToastMessage) => void
  dismiss: () => void
}

const ToastContext = React.createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const value = React.useContext(ToastContext)
  if (!value) throw new Error("useToast خارج ToastProvider")
  return value
}

const ICONS = { success: CheckCircle2, info: Info, danger: OctagonAlert }

export function ToastProvider({ children, initial = null }: { children: React.ReactNode; initial?: ToastMessage | null }) {
  // المفتاح يتغيّر مع كل رسالة: قارئ الشاشة يعلن الجديدة وإن تكرّر نصّها.
  const [current, setCurrent] = React.useState<{ key: number; message: ToastMessage } | null>(
    initial ? { key: 1, message: initial } : null,
  )
  const value = React.useMemo<ToastContextValue>(
    () => ({
      show: (message) => setCurrent((previous) => ({ key: (previous?.key ?? 0) + 1, message })),
      dismiss: () => setCurrent(null),
    }),
    [],
  )
  return (
    <ToastContext.Provider value={value}>
      {children}
      <Toaster current={current} onDismiss={value.dismiss} />
    </ToastContext.Provider>
  )
}

function Toaster({ current, onDismiss }: { current: { key: number; message: ToastMessage } | null; onDismiss: () => void }) {
  const tone = current?.message.tone ?? "success"
  const Icon = ICONS[tone]
  return (
    // المنطقة الحيّة موجودةٌ دائماً (فارغة)، فيُعلَن ما يُكتب فيها.
    <div
      role={tone === "danger" ? "alert" : "status"}
      aria-live={tone === "danger" ? "assertive" : "polite"}
      className="pointer-events-none fixed inset-x-0 top-[calc(var(--bar)+var(--edge)+env(safe-area-inset-top))] z-40 flex justify-center px-edge"
    >
      {current ? (
        <div
          key={current.key}
          className={cn(
            "pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-card border bg-card p-pad shadow-pop",
            tone === "danger" ? "border-destructive" : tone === "info" ? "border-primary" : "border-success",
          )}
        >
          <Icon
            aria-hidden="true"
            className={cn("mt-0.5 size-icon shrink-0", tone === "danger" ? "text-destructive" : tone === "info" ? "text-primary" : "text-success")}
          />
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <p className="font-semibold leading-snug">{current.message.title}</p>
            {current.message.description ? <p className="text-small text-muted-foreground">{current.message.description}</p> : null}
          </div>
          <button
            type="button"
            data-safe=""
            onClick={onDismiss}
            className="-my-1 inline-flex min-h-ctl min-w-ctl shrink-0 items-center justify-center gap-1.5 rounded-ctl border border-control px-2.5 text-small font-semibold hov:bg-muted"
          >
            <X aria-hidden="true" className="size-4 gaze:size-5" />
            إغلاق
          </button>
        </div>
      ) : null}
    </div>
  )
}
