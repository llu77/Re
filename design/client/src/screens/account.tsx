/*
 * حسابي. أعلى النهاية فارغ: تحته في الرئيسية «حسابي»، فلا يقع تحت نظرٍ باقٍ زرٌّ ينقل
 * أو يعتمد. الخروج والحذف كلاهما بخطوتين: هنا يفتحان شاشة التأكيد ولا يفعلان شيئاً.
 */
import * as React from "react"
import { BookOpen, ChevronRight, KeyRound, LogOut, Trash2 } from "lucide-react"

import { BottomBar, Content, Screen, TopBar } from "@/components/frame/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { api, detail } from "@/lib/api"
import { passkeyAdd, passkeysAvailable, preparePasskey } from "@/lib/passkeys"
import { loadPortal } from "@/lib/portal"
import { go } from "@/lib/router"
import { getState, nextNav, setState, showAlert, useStore } from "@/lib/store"

export function Account() {
  const name = useStore((s) => s.displayName)
  const portal = useStore((s) => s.portal)
  const [status, setStatus] = React.useState("")
  const passkeys = passkeysAvailable()

  React.useEffect(() => {
    nextNav()
    preparePasskey("add")
    void loadPortal({ fresh: true })
  }, [])

  return (
    <Screen name="account">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/")}>
            رجوع
          </Button>
        }
        step="حسابي"
      />
      <Content>
        <Card className="flex-row items-center gap-4">
          <span
            aria-hidden="true"
            className="flex size-14 shrink-0 items-center justify-center rounded-full bg-secondary font-display text-[1.5rem] font-bold text-secondary-foreground"
          >
            {name ? name.slice(0, 1) : ""}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <h2 tabIndex={-1} id="account-name" className="text-title">
              {name ?? "بلا اسم"}
            </h2>
            {/* سطر المهنة يحجز مكانه قبل قراءة البوابة: لا يتحرّك تحته زرٌّ حين تصل. */}
            <p id="account-profession" className="min-h-[1.75rem]">
              {portal ? <Badge variant="brand">المهنة: {portal.name}</Badge> : " "}
            </p>
          </div>
        </Card>
        <div className="spaced grid flex-none grid-cols-2 gap-gap">
          <Button
            id="account-passkey"
            icon={KeyRound}
            reserved={!passkeys}
            onClick={async () => {
              setStatus("")
              const saved = await passkeyAdd()
              if (saved) setStatus(saved)
            }}
          >
            أضف مفتاح مرور
          </Button>
          <Button id="account-sources" icon={BookOpen} onClick={() => go("#/account/sources")}>
            المصادر
          </Button>
        </div>
        <p id="account-passkey-help" className="text-small text-muted-foreground" hidden={!passkeys}>
          مفتاح المرور دخولٌ بلا كتابة: ضغطةٌ، ثم يؤكّد الجهاز بـFace ID أو Touch ID أو رمزه.
        </p>
        <p id="account-passkey-status" role="status" className="text-small font-semibold text-success">
          {status}
        </p>
      </Content>
      <BottomBar
        start={
          <Button id="account-delete" variant="danger-quiet" icon={Trash2} onClick={() => go("#/account/delete")}>
            احذف حسابي
          </Button>
        }
        end={
          <Button id="account-logout" icon={LogOut} onClick={() => go("#/account/logout")}>
            تسجيل الخروج
          </Button>
        }
      />
    </Screen>
  )
}

/* الخروج بخطوتين: «نعم، اخرج» في المحتوى، و«رجوع» موضعَ الضغطة السابقة. */
export function AccountLogout() {
  async function onYes() {
    const { busy, alert } = getState()
    if (busy || alert) return
    setState({ busy: true })
    const result = await api("POST", "/api/auth/logout")
    setState({ busy: false })
    if (result.status === 204 || result.status === 401) {
      location.replace("/")
      return
    }
    showAlert("account-logout", `لم يتمّ تسجيل الخروج. ${detail(result)}`)
  }
  return (
    <Screen name="account-logout" onAck={() => go("#/account")}>
      <TopBar step="تسجيل الخروج" />
      <Content>
        <h2 tabIndex={-1} className="text-title">
          تسجيل الخروج؟
        </h2>
        <p className="line">للدخول من جديد تُكتب كلمة المرور، أو يُستعمل مفتاح المرور إن أُضيف.</p>
        <Button id="account-logout-yes" commit variant="primary" icon={LogOut} className="spaced w-full" onClick={onYes}>
          نعم، اخرج
        </Button>
      </Content>
      <BottomBar
        end={
          <Button id="account-logout-back" icon={ChevronRight} onClick={() => go("#/account")}>
            رجوع
          </Button>
        }
      />
    </Screen>
  )
}
