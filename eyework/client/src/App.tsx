/*
 * الواجهة
 * =======
 * من لا جلسة له يرى AuthForm؛ ومن له جلسةٌ يرى شريط التنقّل ببنود بوابته. الحالة
 * من الخادم وحده (/api/me ثم /api/portal)، لا من المتصفّح. ولا طريق إلى التسجيل هنا
 * بعد (يحتاج اليوم رابطاً من المشغّل)، فلا يُمرَّر `onStartSignup` ويقول النموذج ذلك.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"

import { DropdownNavigation } from "@/components/ui/dorpdown-navigation"
import { AuthForm, BrandMark } from "@/components/ui/premium-auth"
import { Button } from "@/components/ui/button"
import { api, detail } from "@/lib/api"
import { navItemsFor, type Portal } from "@/lib/nav"
import { cn } from "@/lib/utils"

interface Me {
  display_name: string | null
  profession: string | null
}

type View =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "signed-in"; me: Me; portal: Portal }
  | { kind: "error"; message: string }

export default function App() {
  const [view, setView] = useState<View>({ kind: "loading" })
  const [menuOpen, setMenuOpen] = useState(false)
  const content = useRef<HTMLElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)

  // React 18 لا يعرف الخاصيّة `inert`، فتُكتب على العنصر نفسه.
  useEffect(() => {
    if (content.current) content.current.inert = menuOpen
  }, [menuOpen, view])

  const load = useCallback(async () => {
    setView({ kind: "loading" })
    const me = await api<Me>("GET", "/api/me")
    if (me.status === 401) {
      setView({ kind: "signed-out" })
      return
    }
    if (me.status !== 200 || !me.data) {
      setView({ kind: "error", message: detail(me) })
      return
    }
    const portal = await api<Portal>("GET", "/api/portal")
    if (portal.status === 401) {
      setView({ kind: "signed-out" })
      return
    }
    if (portal.status !== 200 || !portal.data) {
      setView({ kind: "error", message: detail(portal) })
      return
    }
    setView({ kind: "signed-in", me: me.data, portal: portal.data })
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // بعد الدخول يُنقل التركيز إلى العنوان، فيُعلَن ما تغيّر ولا يسقط التركيز إلى <body>.
  useEffect(() => {
    if (view.kind === "signed-in") heading.current?.focus({ preventScroll: true })
  }, [view.kind])

  return (
    <div className="min-h-dvh px-edge pb-edge pt-[max(1rem,env(safe-area-inset-top))]">
      {view.kind === "loading" && (
        <p role="status" className="flex items-center gap-3 pt-target text-muted-foreground">
          <Loader2 className="size-6 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          يُحمَّل…
        </p>
      )}

      {view.kind === "signed-out" && (
        <main className="pt-6">
          <AuthForm onSignedIn={() => void load()} />
        </main>
      )}

      {view.kind === "error" && (
        <main className="mx-auto flex max-w-md flex-col gap-target-gap pt-target">
          <p role="alert" className="text-lg">{view.message}</p>
          <Button onClick={() => void load()}>حاول مرة أخرى</Button>
        </main>
      )}

      {view.kind === "signed-in" && (
        <>
          <header className="mx-auto flex max-w-2xl flex-col gap-target-gap">
            <div className="flex items-center gap-4">
              <BrandMark />
              <div>
                <p className="text-base text-muted-foreground">بوابة {view.portal.name}</p>
                <h1 ref={heading} tabIndex={-1} className="text-2xl font-bold leading-tight">
                  {view.me.display_name ? `أهلاً، ${view.me.display_name}` : "أهلاً"}
                </h1>
              </div>
            </div>
            <DropdownNavigation navItems={navItemsFor(view.portal)} label="أقسام البوابة" onOpenChange={setMenuOpen} />
          </header>
          {/* ما تحت القائمة المفتوحة خاملٌ ومخفيّ: لا يُصاب ولا يُقرأ ولا يطلّ من حوافّها حتى تُغلق. */}
          <main ref={content} className={cn("mx-auto max-w-2xl pt-target-gap", menuOpen && "invisible")}>
            <p className="text-lg leading-relaxed text-muted-foreground">
              اختر من «بوابتي» ما تتطلّبه مهنتك، أو من «حسابي» ما يخصّ حسابك.
            </p>
          </main>
        </>
      )}
    </div>
  )
}
