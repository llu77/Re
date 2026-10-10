/*
 * ChatLauncher — زرّ سيمبول العائم في الآيباد والحاسوب
 * ==================================================
 * في الحجم العادي من 744px فأوسع (بلا شريط تبويب): زرّ سيمبول نفسه (`SymbolButton` في tab-bar.tsx: دائرةٌ
 * بالتعبئة الملوّنة وفقاعة محادثةٍ بيضاء) عائمٌ في الركن السفلي من طرف النهاية. وفي الهاتف بجانب شريط التبويب، وفي
 * الحجم الكبير بندٌ في السكّة. آمن (`data-safe`): يفتح ورقة المحادثة ولا يعتمد شيئاً، والمحتوى ينتهي فوقه
 * (`--launcher`)، ويختفي ما دام حقلٌ مركَّزاً (`kb:hidden`). التخطيط من «Floating Action Button» (serafimcloud،
 * 21st.dev: https://21st.dev/serafimcloud/components/floating-action-button، بشروط 21st.dev ورخصة صفحة المكوّن)
 * بلا framer-motion ولا قائمةٍ تنفتح منه.
 */

import { SymbolButton } from "@/components/shell/tab-bar"

export function ChatLauncher({ onOpen }: { onOpen: () => void }) {
  return (
    <SymbolButton
      id="nav-chat"
      onClick={onOpen}
      className="fixed bottom-[max(var(--edge),env(safe-area-inset-bottom))] end-edge z-30 kb:hidden"
    />
  )
}
