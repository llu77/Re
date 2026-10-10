/*
 * العلامتان
 * =========
 * BrandMark: علامة «صياغة» الهندسية (كما في eyework/client): الاسم والعنوان والأيقونة لا
 * تذكر النظر ولا العين ولا الإعاقة (tests/architecture/test_separation.py)، فقائمة
 * مستخدمي التطبيق ليست معلومةً صحّية.
 * SymbolMark: علامة المساعد «سيمبول» (لوحة الممارس): أربعة مستطيلاتٍ على شبكة 3×3.
 * كلتاهما زخرفيةٌ بجانب نصٍّ يسمّيها.
 */

import { cn } from "@/lib/utils"

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false" className={cn("size-8 shrink-0", className)}>
      <rect width="48" height="48" rx="12" className="fill-primary" />
      <rect x="13" y="13" width="14" height="14" rx="3" className="fill-primary-foreground" />
      <rect x="21" y="21" width="14" height="14" rx="3" className="fill-primary-foreground opacity-60" />
    </svg>
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
