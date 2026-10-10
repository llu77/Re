/*
 * «قبل أن تبدأ»: ما يُحفظ، وما يُرسَل
 * ===================================
 * شاشتان من نصّ الخادم (terms.notice()) حرفياً، لا من الواجهة: ما يُحفظ في التطبيق، ثم ما
 * يُرسَل إلى مزوّد النموذج (سطرٌ لكل بوابة، أو للكلّ). «أوافق وأتابع» في آخر الثانية وحدها،
 * والنسخة التي عُرضت هي ما يحمله التسجيل والموافقة. في التسجيل تُعرض سطور البوابات كلّها
 * لأن المهنة لم تُختر بعد؛ وفي تسلسل البدء سطر مهنة صاحب الحساب وسطر الكلّ.
 */

import { Check } from "lucide-react"

import { PageTitle } from "@/components/brand/page-title"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { PagedText } from "@/components/ui/paged-text"
import { useSize } from "@/lib/size"
import type { Notice } from "@/lib/store"
import { AuthFrame } from "@/screens/auth"

function Lines({ lines, label }: { lines: string[]; label: string }) {
  const { size } = useSize()
  if (size === "gaze") return <PagedText text={lines.join(" ")} label={label} className="min-h-0 flex-1" />
  return (
    <ul aria-label={label} className="flex list-disc flex-col gap-2 ps-5 text-flow">
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  )
}

export function NoticeKeptScreen({ notice, onNext, onBack }: { notice: Notice; onNext: () => void; onBack: () => void }) {
  return (
    <AuthFrame
      toggle={false}
      end={
        <Button id="notice-back" icon={BackIcon} onClick={onBack}>
          رجوع
        </Button>
      }
    >
      <main className="flex min-h-0 flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex flex-col gap-1">
          <p className="text-small font-semibold text-muted-foreground">قبل أن تبدأ · 1 من 2</p>
          <PageTitle>ما يُحفظ في هذا التطبيق</PageTitle>
        </div>
        <Lines lines={notice.kept} label="ما يُحفظ" />
        <div className="mt-auto">
          <Button id="notice-next" variant="secondary" size="lg" width="full" iconEnd={NextIcon} onClick={onNext}>
            التالي
          </Button>
        </div>
      </main>
    </AuthFrame>
  )
}

export function NoticeSentScreen({ notice, scope, onAgree, onBack }: {
  notice: Notice
  /** مهنة صاحب الحساب، أو null في التسجيل: كل السطور. */
  scope: string | null
  onAgree: () => void
  onBack: () => void
}) {
  const items = notice.sent.items.filter((item) => item.scope === "ALL" || scope === null || item.scope === scope)
  return (
    <AuthFrame
      toggle={false}
      end={
        <Button id="notice-back" icon={BackIcon} onClick={onBack}>
          رجوع
        </Button>
      }
    >
      <main className="flex min-h-0 flex-1 flex-col gap-sec pt-sec gaze:gap-tg gaze:pt-tg">
        <div className="flex flex-col gap-1">
          <p className="text-small font-semibold text-muted-foreground">قبل أن تبدأ · 2 من 2</p>
          <PageTitle>ما يُرسَل إلى مزوّد النموذج</PageTitle>
        </div>
        <Lines lines={[notice.sent.intro, ...items.map((item) => item.text), notice.sent.outro]} label="ما يُرسَل" />
        <div className="mt-auto">
          <Button id="signup-agree" variant="primary" size="lg" width="full" icon={Check} onClick={onAgree}>
            أوافق وأتابع
          </Button>
        </div>
      </main>
    </AuthFrame>
  )
}
