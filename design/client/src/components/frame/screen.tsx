/*
 * الإطار — كل شاشةٍ بأربع خاناتٍ ثابتة الموضع: أعلى البداية (يمين) وأعلى النهاية
 * (يسار) وأسفل البداية وأسفل النهاية، وبين العلويّتين سطر الخطوة. الخانة الفارغة
 * منطقةٌ ميتة مقصودة: ما يقع تحت النظر بعد تغيّر الشاشة لا يُعتمد.
 *
 * الأسماء التي تقرؤها الاختبارات باقية: section.screen[data-screen]، و.bar--top
 * بثلاثة أبناء أوسطهم p.step، و.bar--bottom، و.content، و.alert و[data-ack].
 */
import * as React from "react"
import { TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { clearAlert, useStore } from "@/lib/store"
import { cn } from "@/lib/utils"

import { BarLock } from "./bar-lock"

interface ScreenProps {
  name: string
  children: React.ReactNode
  /* ما بعد «حسناً» في هذه الشاشة (إعادة قراءة، أو انتقالٌ آمن). */
  onAck?: () => void
}

export function Screen({ name, children, onAck }: ScreenProps) {
  const heading = React.useRef<HTMLElement>(null)
  React.useLayoutEffect(() => {
    // التركيز على عنوان الشاشة لا على زرّ: يعلن الشاشة لقارئ الشاشة ولا يفعّل شيئاً.
    const section = heading.current
    const title = section?.querySelector<HTMLElement>("h1:not([hidden]), h2:not([hidden])")
    title?.focus({ preventScroll: true })
  }, [name])
  return (
    <section ref={heading} className="screen" data-screen={name}>
      <ScreenContext.Provider value={{ name, onAck }}>{children}</ScreenContext.Provider>
    </section>
  )
}

const ScreenContext = React.createContext<{ name: string; onAck?: () => void }>({ name: "" })

function useLocked() {
  const { name } = React.useContext(ScreenContext)
  return useStore((s) => s.alert !== null && s.alert.screen === name)
}

export function TopBar({
  start,
  step,
  stepId,
  end,
}: {
  start?: React.ReactNode
  step?: React.ReactNode
  stepId?: string
  end?: React.ReactNode
}) {
  const locked = useLocked()
  return (
    <BarLock.Provider value={locked}>
      <header className="bar bar--top">
        <div className="slot">{start}</div>
        <p className="step" id={stepId}>
          {step}
        </p>
        <div className="slot">{end}</div>
      </header>
    </BarLock.Provider>
  )
}

export function BottomBar({ start, end }: { start?: React.ReactNode; end?: React.ReactNode }) {
  const locked = useLocked()
  return (
    <BarLock.Provider value={locked}>
      <footer className="bar bar--bottom">
        <div className="slot">{start}</div>
        <div className="slot">{end}</div>
      </footer>
    </BarLock.Provider>
  )
}

/* سطر الموضع في الشريط العلوي: قوس المكوث ونصّه، أو نصٌّ وحده. */
export function Step({ children, arc }: { children: React.ReactNode; arc?: React.ReactNode }) {
  return (
    <>
      {arc}
      <span className="min-w-0">{children}</span>
    </>
  )
}

type ContentProps = React.ComponentProps<"div"> & { as?: "div" | "form"; onSubmit?: React.FormEventHandler }

export function Content({ as = "div", className, children, ...props }: ContentProps) {
  const Comp = as as "div"
  return (
    <Comp className={cn("content", className)} {...(as === "form" ? { noValidate: true } : {})} {...props}>
      {children}
      <AlertOverlay />
    </Comp>
  )
}

function AlertOverlay() {
  const { name, onAck } = React.useContext(ScreenContext)
  const message = useStore((s) => (s.alert && s.alert.screen === name ? s.alert.message : null))
  return (
    <div className="alert" role="alert" hidden={message === null}>
      <span className="flex size-12 items-center justify-center rounded-full bg-destructive-tint text-destructive">
        <TriangleAlert aria-hidden="true" className="size-7" strokeWidth={2.25} />
      </span>
      <p className="alert__text">{message}</p>
      <p className="text-small text-muted-foreground">«حسناً» في أعلى الشاشة تغلق التنبيه.</p>
      <Button
        data-ack=""
        onClick={() => {
          clearAlert()
          onAck?.()
        }}
      >
        حسناً
      </Button>
    </div>
  )
}
