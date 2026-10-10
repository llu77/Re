/*
 * الشعار والعلامة
 * ===============
 * Logo: شعار «Symbol Work» كما سلّمه المالك، بتصميمه وخطّه نفسيهما (الكلمتان بحدٍّ أسود والمكبّرة وفيها الشخص):
 * الصورة نفسها، قُصّت إلى حدودها وصار ما حولها من البياض شفّافاً، وبقي بياض الحروف والعدسة كما هو. مكانه كما في
 * المواقع الاحترافية (طلب المالك): رأس الصفحة (`AppHeader`)، شريطٌ أبيض بعرض الشاشة بخطٍّ رفيعٍ تحته والشعار في أوّله
 * (40، و32 في الحجم الكبير)، في كل صفحةٍ على الهاتف وفي ما قبل الدخول؛ وفي الآيباد والحاسوب رأس الشريط الجانبي
 * (rail)؛ وفي الترحيب عنوانه في وسطه (hero). لا في سطر العنوان ولا في الأوراق. صورتان بحجمين (96 و240 بكسل
 * ارتفاعاً)، يختار المتصفّح منهما ما يكفي كثافة الشاشة. الاسم لا يذكر النظر ولا العين ولا الإعاقة
 * (tests/architecture/test_separation.py)، فقائمة مستخدمي التطبيق ليست معلومةً صحّية.
 * SymbolMark: علامة المساعد «سيمبول» (لوحة الممارس): أربعة مستطيلاتٍ على شبكة 3×3.
 * الشعار زخرفيٌّ بجانب نصٍّ يسمّي الصفحة، إلا في الترحيب فهو العنوان نفسه (`decorative={false}`).
 */

import type * as React from "react"

import logo96 from "@/assets/brand/symbol-work-logo-96.png"
import logo240 from "@/assets/brand/symbol-work-logo-240.png"
import { cn } from "@/lib/utils"

/** نسبة عرض الشعار إلى ارتفاعه (1306×394 بعد القصّ). */
const RATIO = 1306 / 394
const HEIGHT = { header: 40, rail: 44, hero: 72 } as const
const HEIGHT_CLASS = { header: "h-10 gaze:h-8", rail: "h-11", hero: "h-[4.5rem]" } as const

export function Logo({ size = "header", className, decorative = true }: { size?: keyof typeof HEIGHT; className?: string; decorative?: boolean }) {
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
 * رأس الصفحة: شريطٌ أبيض بعرض الشاشة بخطٍّ رفيعٍ تحته، والشعار في أوّله؛ وفي آخره فعل الصفحة الوحيد إن كان
 * («رجوع» في خطوات التسجيل). يمرّ مع الصفحة، فيلتصق صفّها العلوي («رجوع» والفعل الآخر) بأعلى الشاشة وحده.
 * والرأس الذي يحمل فعلاً هو في الحجم الكبير بارتفاع الهدف ومساحة إصابته الخفيّة فوقه وتحته (72)، فلا يقصّها أعلى
 * الشاشة؛ وبلا فعلٍ 48.
 */
export function AppHeader({ end, className }: { end?: React.ReactNode; className?: string }) {
  return (
    <header data-app-header="" className={cn("shrink-0 border-b border-border bg-card pt-[env(safe-area-inset-top)]", className)}>
      <div className={cn("mx-auto flex h-header max-w-content items-center justify-between gap-tg px-edge", end && "gaze:h-[calc(var(--tg)+2*var(--hit-pad))]")}>
        <Logo />
        {end ?? null}
      </div>
    </header>
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
