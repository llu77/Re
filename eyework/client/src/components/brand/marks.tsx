/*
 * الاسم والعلامة
 * ===============
 * Wordmark: الاسم «Symbol Work» بدل علامة «صياغة» (طلب المالك): بجانب عنوان كل شاشةٍ وورقةٍ ونافذة، وفي الترحيب
 * ورأس الشريط الجانبي. «Symbol» بالأزرق و«Work» بلون النصّ الهادئ، بخطٍّ لاتيني من اليسار إلى اليمين. الاسم لا يذكر
 * النظر ولا العين ولا الإعاقة (tests/architecture/test_separation.py)، فقائمة مستخدمي التطبيق ليست معلومةً صحّية.
 * SymbolMark: علامة المساعد «سيمبول» (لوحة الممارس): أربعة مستطيلاتٍ على شبكة 3×3.
 * كلاهما زخرفيٌّ بجانب نصٍّ يسمّي الصفحة، إلا الاسم في الترحيب فهو العنوان نفسه (`decorative={false}`).
 */

import { cn } from "@/lib/utils"

export function Wordmark({ className, decorative = true }: { className?: string; decorative?: boolean }) {
  return (
    // مسافةٌ حقيقية بين الكلمتين (لا فجوة flex) فيُقرأ الاسم «Symbol Work» لا «SymbolWork».
    <span
      aria-hidden={decorative ? "true" : undefined}
      dir="ltr"
      translate="no"
      className={cn("inline-block shrink-0 whitespace-nowrap font-num leading-none tracking-tight", className)}
    >
      <span className="font-bold text-primary">Symbol</span> <span className="font-semibold text-muted-foreground">Work</span>
    </span>
  )
}

export function SymbolMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 3 3" aria-hidden="true" focusable="false" className={cn("size-5 shrink-0", className)}>
      <rect x="1" y="0" width="2" height="2" fill="#306BF5" />
      <rect x="0" y="1" width="2" height="1" fill="#63D7EE" />
      <rect x="1" y="2" width="1" height="1" fill="#63D7EE" />
      <rect x="1" y="1" width="1" height="1" fill="#061840" />
    </svg>
  )
}
