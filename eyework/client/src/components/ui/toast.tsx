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
 *   • في الحجم الكبير لا تطفو فوق الشاشة: كلّ موضعٍ فوقها يغطّي هدفاً يُنظر إليه. تُكتب سطراً تحت
 *     عنوان الشاشة (Screen، بـuseToastMessage) بلا «إغلاق»، وتُغلق بالانتقال؛ والمنطقة الحيّة تبقى
 *     لقارئ الشاشة وحده.
 */

import * as React from "react"
import { CheckCircle2, Info, OctagonAlert, X } from "lucide-react"

import { useSize } from "@/lib/size"
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
const ToastMessageContext = React.createContext<ToastMessage | null>(null)

/** الرسالة الحالية: في الحجم الكبير يكتبها إطار الشاشة سطراً تحت عنوانها. */
export function useToastMessage(): ToastMessage | null {
  return React.useContext(ToastMessageContext)
}

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
      <ToastMessageContext.Provider value={current?.message ?? null}>
        {children}
        <Toaster current={current} onDismiss={value.dismiss} />
      </ToastMessageContext.Provider>
    </ToastContext.Provider>
  )
}

function Toaster({ current, onDismiss }: { current: { key: number; message: ToastMessage } | null; onDismiss: () => void }) {
  const { size } = useSize()
  const tone = current?.message.tone ?? "success"
  const Icon = ICONS[tone]
  if (size === "gaze") {
    // المنطقة الحيّة لقارئ الشاشة وحده؛ والسطر المرئيّ في إطار الشاشة.
    return (
      <div role={tone === "danger" ? "alert" : "status"} aria-live={tone === "danger" ? "assertive" : "polite"} className="sr-only">
        {current ? <p key={current.key}>{current.message.title}{current.message.description ? `. ${current.message.description}` : ""}</p> : null}
      </div>
    )
  }
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
            "pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-card border border-transparent bg-card p-pad shadow-pop",
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
            className="-my-1 inline-flex min-h-ctl min-w-ctl shrink-0 items-center justify-center gap-1.5 rounded-ctl bg-muted px-2.5 text-small font-semibold hov:bg-secondary"
          >
            <X aria-hidden="true" className="size-4 gaze:size-5" />
            إغلاق
          </button>
        </div>
      ) : null}
    </div>
  )
}

/** سطر الرسالة تحت عنوان الشاشة في الحجم الكبير: بلا زرّ، ولا يغطّي شيئاً. */
export function ToastLine({ message }: { message: ToastMessage }) {
  const tone = message.tone ?? "success"
  const Icon = ICONS[tone]
  return (
    <p aria-hidden="true" data-toast-line="" className="flex items-start gap-2 text-small font-semibold">
      <Icon
        className={cn("mt-0.5 size-icon shrink-0", tone === "danger" ? "text-destructive" : tone === "info" ? "text-primary" : "text-success")}
      />
      <span className="line-clamp-2 min-w-0">
        {message.title}
        {message.description ? <span className="font-normal text-muted-foreground"> — {message.description}</span> : null}
      </span>
    </p>
  )
}
