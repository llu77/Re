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

/*
 * سطر الموضع في الشريط العلوي: قوس المكوث، وتحته «1 من 8». اسم السلسلة («الخطوة»،
 * «المهمة»، «الجزء») لقارئ الشاشة وحده — العنوان في المحتوى يسمّيها — فيتّسع السطر
 * في 72px بين زرّين في إطار 320.
 */
export function Step({ arc, noun, n, total }: { arc: React.ReactNode; noun: string; n: number; total: number }) {
  return (
    <span className="flex flex-col items-center gap-0.5">
      {arc}
      <span className="whitespace-nowrap tabular-nums">
        <span className="visually-hidden">{noun} </span>
        {n} من {total}
      </span>
    </span>
  )
}

type ContentProps = React.ComponentProps<"div"> & { as?: "div" | "form"; onSubmit?: React.FormEventHandler }

export const Content = React.forwardRef<HTMLDivElement, ContentProps>(
  ({ as = "div", className, children, ...props }, ref) => {
    const Comp = as as "div"
    return (
      <Comp ref={ref} className={cn("content", className)} {...(as === "form" ? { noValidate: true } : {})} {...props}>
        {children}
        <AlertOverlay />
      </Comp>
    )
  },
)
Content.displayName = "Content"

/*
 * قياسٌ بعد الرسم لا مؤقّت (كما في شاشة النصّ المقترح): إن فاض المحتوى عن مساحته
 * يُعرض مضغوطاً — بطاقةٌ بلا إطار ولا حشو — ولا يُقصّ حرف.
 */
export function useCompactWhenOverflowing(deps: React.DependencyList) {
  const ref = React.useRef<HTMLDivElement>(null)
  const [compact, setCompact] = React.useState(false)
  React.useLayoutEffect(() => {
    setCompact(false)
  }, deps)
  React.useLayoutEffect(() => {
    const box = ref.current
    if (!compact && box && box.scrollHeight > box.clientHeight) setCompact(true)
  })
  return { ref, compact }
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
