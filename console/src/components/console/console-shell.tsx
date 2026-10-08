import * as React from "react"
import { RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar"
import { ApiError, practitionerApi } from "@/lib/api"
import type { Proposal, RedFlag } from "@/lib/types"

import { AppSidebar } from "./app-sidebar"
import { PageHeading, SuccessNotice } from "./feedback"
import type { SignedIn } from "./login-screen"
import { ProposalPage } from "./proposal-page"
import { QueuePage } from "./queue-page"
import { RedFlagsPage } from "./red-flags-page"
import { type Route, useRoute } from "./route"

const TITLES = {
  queue: "طابور المراجعة",
  proposal: "مراجعة مقترح",
  "red-flags": "البلاغات العاجلة",
} as const

const DESCRIPTIONS = {
  queue: "العلامات الحمراء أولاً، ثم الأولوية، ثم زمن الانتظار. كل قرارٍ لمقترحٍ واحد.",
  proposal: "المحتوى كاملاً وأدلّته بجانبه. لا يصل المريضَ شيءٌ قبل قرارك.",
  "red-flags": "بلاغات المرضى غير المستلَمة، الأقدم أولاً.",
} as const

/**
 * على الهاتف الشريط نافذةٌ فوق الصفحة؛ رابطٌ فيها يغيّر الصفحة تحتها ويتركها
 * مغطّاة. تُغلق النافذة مع كل انتقال.
 */
function CloseSheetOnNavigate({ routeKey }: { routeKey: string }) {
  const { isMobile, setOpenMobile } = useSidebar()
  React.useEffect(() => {
    if (isMobile) setOpenMobile(false)
  }, [routeKey, isMobile, setOpenMobile])
  return null
}

/** عنوان الصفحة يتبعها، فيُعرف التبويب والسجلّ في المتصفّح وفي قارئ الشاشة. */
const DOCUMENT_TITLE = "لوحة الممارس — Symbol AI"

function focusHeading() {
  document.querySelector<HTMLElement>("main h1[tabindex]")?.focus({ preventScroll: true })
}

export function ConsoleShell({
  session,
  onSignedOut,
}: {
  session: SignedIn
  onSignedOut: (reason: "signed-out" | "expired") => void
}) {
  const api = React.useMemo(
    () => practitionerApi(session, () => onSignedOut("expired")),
    [session, onSignedOut],
  )
  const [route, navigate] = useRoute()
  const [queue, setQueue] = React.useState<Proposal[] | null>(null)
  const [flags, setFlags] = React.useState<RedFlag[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [refreshing, setRefreshing] = React.useState(false)
  // رسالة النجاح تخصّ صفحةً بعينها: تُضبط قبل الانتقال إليها، فتُربط بها لا
  // بلحظة ظهورها.
  const [notice, setNotice] = React.useState<{ text: string; on: Route["name"] } | null>(null)
  const [signingOut, setSigningOut] = React.useState(false)

  const refresh = React.useCallback(async () => {
    setRefreshing(true)
    try {
      const [nextQueue, nextFlags] = await Promise.all([api.queue(), api.redFlags()])
      setQueue(nextQueue)
      setFlags(nextFlags)
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التحديث.")
    } finally {
      setRefreshing(false)
    }
  }, [api])

  // يُحدَّث عند الفتح وعند العودة إلى التبويب — لا مؤقّت يعمل في الخلفية.
  React.useEffect(() => {
    void refresh()
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [refresh])

  React.useEffect(() => {
    setNotice((current) => (current && current.on !== route.name ? null : current))
  }, [route])

  const routeKey = route.name === "proposal" ? `proposal:${route.id}` : route.name

  // كل صفحةٍ تبدأ من أعلاها: بعد قرارٍ في أسفل المقترح كان الطابور يُفتح في
  // منتصفه، ورسالة النجاح فوق ما يُرى.
  React.useEffect(() => {
    window.scrollTo({ top: 0 })
    document.title = `${TITLES[route.name]} — ${DOCUMENT_TITLE}`
  }, [routeKey, route.name])

  const done = React.useCallback(
    (text: string, on: Route["name"]) => {
      setNotice({ text, on })
      if (on === "queue") {
        navigate({ name: "queue" })
      } else {
        // الصفحة نفسها: البطاقة التي كان فيها التركيز زالت. يعود إلى العنوان،
        // وتظهر الرسالة تحته.
        window.scrollTo({ top: 0 })
        focusHeading()
      }
      void refresh()
    },
    [navigate, refresh],
  )

  async function signOut() {
    setSigningOut(true)
    try {
      await api.logout()
    } catch {
      // الجلسة تُنسى محلياً في كل حال؛ الخادم يُبطلها بانتهاء مدّتها إن تعذّر.
    } finally {
      onSignedOut("signed-out")
    }
  }

  return (
    // العرض بـrem يتضاعف مع تكبير النصّ: 16rem تصير 512px من نافذةٍ عرضها 768،
    // فلا يبقى للمحتوى إلا ثلثها. السقف نسبةٌ من النافذة؛ بالنصّ العادي لا يتغيّر شيء.
    <SidebarProvider
      style={{ "--sidebar-width": "min(16rem, 40vw)", "--sidebar-width-icon": "4rem" } as React.CSSProperties}
    >
      <CloseSheetOnNavigate routeKey={routeKey} />
      <AppSidebar
        route={route}
        queueCount={queue?.length ?? null}
        redFlagCount={flags?.length ?? null}
        email={session.email}
        onSignOut={signOut}
        signingOut={signingOut}
      />
      {/* min-w-0: بلا هذا لا ينكمش العمود دون عرض محتواه، فيفيض أفقياً عند تكبير النصّ. */}
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-10 flex min-h-16 items-center gap-3 border-b bg-background/95 px-4 py-2">
          <SidebarTrigger
            className="size-12 [&_svg]:size-5"
            aria-label="إظهار الشريط الجانبي أو طيّه"
          />
          <Separator orientation="vertical" className="h-8" />
          <div key={routeKey} className="min-w-0 flex-1">
            <PageHeading>{TITLES[route.name]}</PageHeading>
          </div>
          {/* aria-disabled لا disabled: الزرّ المعطَّل يُسقط التركيز إلى الصفحة. */}
          <Button
            variant="outline"
            className="h-12 gap-2 text-base"
            onClick={() => {
              if (!refreshing) void refresh()
            }}
            aria-disabled={refreshing}
          >
            <RefreshCw className="size-5" aria-hidden="true" />
            <span className="max-sm:sr-only">{refreshing ? "جارٍ التحديث…" : "تحديث"}</span>
          </Button>
        </header>

        <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-6 sm:px-6">
          <p className="text-muted-foreground">{DESCRIPTIONS[route.name]}</p>
          <SuccessNotice message={notice?.on === route.name ? notice.text : null} />
          {error && (queue || flags) ? (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          ) : null}

          {route.name === "queue" ? (
            <QueuePage items={queue} error={error} />
          ) : route.name === "proposal" ? (
            <ProposalPage
              key={route.id}
              api={api}
              id={route.id}
              onDecided={(message) => done(message, "queue")}
            />
          ) : (
            <RedFlagsPage
              api={api}
              items={flags}
              error={error}
              onAcknowledged={(message) => done(message, "red-flags")}
            />
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
