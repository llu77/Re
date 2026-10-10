/*
 * الشعار والعلامة
 * ===============
 * Logo: شعار «Symbol Work» كما سلّمه المالك، بتصميمه وخطّه نفسيهما (الكلمتان بحدٍّ أسود والمكبّرة وفيها الشخص):
 * الصورة نفسها، قُصّت إلى حدودها وصار ما حولها من البياض شفّافاً، وبقي بياض الحروف والعدسة كما هو. في الحجم
 * العادي صفٌّ وحده في أعلى كل صفحة، في وسطها، فوق الخطوات والعنوان (`PageBrand`، 40)؛ وفي الحجم الكبير (لا تمرير،
 * ولا مكان لصفٍّ آخر في 320×635) في آخر سطر العنوان (`PageTitle`، 32). وفي رأس الشريط الجانبي في الآيباد (rail)؛
 * وعنوان الترحيب (hero)؛ وفي آخر سطر عنوان الورقة والنافذة (title). صورتان بحجمين (96 و240 بكسل ارتفاعاً)، يختار
 * المتصفّح منهما ما يكفي كثافة الشاشة. الاسم لا يذكر النظر ولا العين ولا
 * الإعاقة (tests/architecture/test_separation.py)، فقائمة مستخدمي التطبيق ليست معلومةً صحّية.
 * SymbolMark: علامة المساعد «سيمبول» (لوحة الممارس): أربعة مستطيلاتٍ على شبكة 3×3.
 * كلاهما زخرفيٌّ بجانب نصٍّ يسمّي الصفحة، إلا الشعار في الترحيب فهو العنوان نفسه (`decorative={false}`).
 */

import logo96 from "@/assets/brand/symbol-work-logo-96.png"
import logo240 from "@/assets/brand/symbol-work-logo-240.png"
import { cn } from "@/lib/utils"

/** نسبة عرض الشعار إلى ارتفاعه (1306×394 بعد القصّ). */
const RATIO = 1306 / 394
const HEIGHT = { title: 32, page: 40, rail: 44, hero: 72 } as const
const HEIGHT_CLASS = { title: "h-8", page: "h-10", rail: "h-11", hero: "h-[4.5rem]" } as const

export function Logo({ size = "title", className, decorative = true }: { size?: keyof typeof HEIGHT; className?: string; decorative?: boolean }) {
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

/**
 * شعار الصفحة في الحجم العادي: صفٌّ وحده في أعلاها، في وسطها. في الآيباد والحاسوب في رأس الشريط الجانبي بدله
 * (`phoneOnly`)، وفي الحجم الكبير في آخر سطر العنوان.
 */
export function PageBrand({ phoneOnly = false, className }: { phoneOnly?: boolean; className?: string }) {
  return (
    <div data-brand="" className={cn("flex justify-center gaze:hidden", phoneOnly && "tablet:hidden", className)}>
      <Logo size="page" />
    </div>
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
