/*
 * ChatLauncher — زرّ «اسأل سيمبول» العائم
 * =======================================
 * في الحجم العادي، في كل شاشةٍ من البوابة: حبّةٌ بالتعبئة الملوّنة وعلامة سيمبول في دائرةٍ بيضاء، في الركن
 * السفلي من طرف النهاية (يسار الصفحة العربية) فوق شريط التبويب في الهاتف، وفي الركن نفسه في الآيباد
 * والحاسوب. نصّها ظاهرٌ بجانب العلامة (لا زرّ بأيقونةٍ وحدها)، وهي آمنة (`data-safe`): تفتح ورقة المحادثة
 * ولا تعتمد شيئاً. والمحتوى ينتهي فوقها (`--launcher`)، وتختفي ما دام حقلٌ مركَّزاً (`kb:hidden`) فلا
 * تركب لوحة المفاتيح. التخطيط مستوحىً من «Floating Action Button» (serafimcloud، 21st.dev:
 * https://21st.dev/serafimcloud/components/floating-action-button، بشروط 21st.dev ورخصة صفحة المكوّن)
 * بلا framer-motion ولا قائمةٍ تنفتح منه: لم تُنقل شيفرته، بل شكله.
 *
 * وفي الحجم الكبير لا شيء يطفو فوق المحتوى (ما يغطّي هدفاً يُضغط بدله): سيمبول بندٌ بالتعبئة نفسها في
 * وسط شريط التبويب أو في السكّة (`accent` في tab-bar.tsx وsidebar.tsx).
 */

import { SymbolMark } from "@/components/brand/marks"
import { cn } from "@/lib/utils"

export function SymbolBadge({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("flex size-8 shrink-0 items-center justify-center rounded-full bg-card", className)}>
      <SymbolMark className="size-[1.125rem]" />
    </span>
  )
}

export function ChatLauncher({ onOpen, tablet }: { onOpen: () => void; tablet: boolean }) {
  return (
    <button
      id="nav-chat"
      type="button"
      data-safe=""
      aria-haspopup="dialog"
      onClick={onOpen}
      className={cn(
        "fixed end-edge z-30 inline-flex min-h-ctl-lg items-center gap-2 rounded-full border border-primary bg-primary py-1 pe-4 ps-1.5",
        "font-semibold text-primary-foreground shadow-pop hov:bg-primary/90 kb:hidden",
        tablet ? "bottom-[max(var(--edge),env(safe-area-inset-bottom))]" : "bottom-[calc(var(--tab)+var(--line)+env(safe-area-inset-bottom)+0.75rem)]",
      )}
    >
      <SymbolBadge />
      <span>اسأل سيمبول</span>
    </button>
  )
}
