/*
 * الشعار والعلامة
 * ===============
 * Logo: شعار «Symbol Work» كما سلّمه المالك، بتصميمه وخطّه نفسيهما (الكلمتان بحدٍّ أسود والمكبّرة وفيها الشخص):
 * الصورة نفسها، قُصّت إلى حدودها وصار ما حولها من البياض شفّافاً، وبقي بياض الحروف والعدسة كما هو. بجانب
 * عنوان كل شاشةٍ وورقةٍ ونافذة (sm)، وفي رأس الشريط الجانبي (md)، وعنوان الترحيب (lg). صورتان بحجمين
 * (96 و240 بكسل ارتفاعاً)، يختار المتصفّح منهما ما يكفي كثافة الشاشة. الاسم لا يذكر النظر ولا العين ولا
 * الإعاقة (tests/architecture/test_separation.py)، فقائمة مستخدمي التطبيق ليست معلومةً صحّية.
 * SymbolMark: علامة المساعد «سيمبول» (لوحة الممارس): أربعة مستطيلاتٍ على شبكة 3×3.
 * كلاهما زخرفيٌّ بجانب نصٍّ يسمّي الصفحة، إلا الشعار في الترحيب فهو العنوان نفسه (`decorative={false}`).
 */

import logo96 from "@/assets/brand/symbol-work-logo-96.png"
import logo240 from "@/assets/brand/symbol-work-logo-240.png"
import { cn } from "@/lib/utils"

/** نسبة عرض الشعار إلى ارتفاعه (1306×394 بعد القصّ). */
const RATIO = 1306 / 394
const HEIGHT = { sm: 32, md: 40, lg: 64 } as const
const HEIGHT_CLASS = { sm: "h-8", md: "h-10", lg: "h-16" } as const

export function Logo({ size = "sm", className, decorative = true }: { size?: keyof typeof HEIGHT; className?: string; decorative?: boolean }) {
  const height = HEIGHT[size]
  const width = Math.round(height * RATIO)
  return (
    <img
      src={logo240}
      srcSet={`${logo96} 318w, ${logo240} 796w`}
      sizes={`${width}px`}
      width={width}
      height={height}
      alt={decorative ? "" : "Symbol Work"}
      aria-hidden={decorative ? "true" : undefined}
      draggable={false}
      className={cn("block w-auto max-w-none shrink-0 select-none", HEIGHT_CLASS[size], className)}
    />
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
