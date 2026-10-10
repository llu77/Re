/*
 * الترحيب — أول ما يراه من لا جلسة له. سطرٌ واحد عمّا يفعله التطبيق، وبابان.
 * «ادخل» أسفل البداية: في شاشة الدخول تحت موضعه زرّ مفتاح المرور (آمن)، لا «ادخل»
 * الذي يرسل. و«أنشئ حساباً» أسفل النهاية: تحته «أوافق وأتابع» (آمن، لا يرسل شيئاً).
 */
import { LogIn, ScanEye, UserPlus } from "lucide-react"

import { GazeMark } from "@/components/brand/gaze-mark"
import { SymbolMark } from "@/components/brand/symbol-mark"
import { BottomBar, Content, Screen, TopBar } from "@/components/frame/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { go } from "@/lib/router"

export function Welcome() {
  return (
    <Screen name="welcome">
      <TopBar
        step={
          <span className="flex items-center gap-2 font-display text-[1.25rem] font-bold text-heading">
            <SymbolMark className="size-7" />
            صياغة
          </span>
        }
      />
      <Content className="gap-3">
        <div className="welcome-stage flex min-h-0 flex-1 items-center justify-center rounded-card">
          <GazeMark />
        </div>
        <Badge variant="brand" icon={ScanEye} className="flex-none">
          بتتبّع العين أو باللمس
        </Badge>
        <h1 tabIndex={-1} className="flex-none text-display">
          كل زرٍّ هنا يُضغط بنظرة
        </h1>
        <p className="flex-none text-muted-foreground">
          بوابة مهنتك: مهامّها ومهاراتها بمصادرها، ومساعدٌ يقترح عليك وأنت تقرّر.
        </p>
      </Content>
      <BottomBar
        start={
          <Button id="welcome-login" variant="secondary" icon={LogIn} onClick={() => go("#/login")}>
            ادخل
          </Button>
        }
        end={
          <Button id="welcome-signup" icon={UserPlus} onClick={() => go("#/signup")}>
            أنشئ حساباً
          </Button>
        }
      />
    </Screen>
  )
}
