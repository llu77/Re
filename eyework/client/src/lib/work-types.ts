/*
 * أنواع بيانات الشاشات
 * ====================
 * كما يردّها الخادم (المبالغ بالهللة، والتواريخ ISO) للوحة التسويق التي لم تُوصل بعد؛
 * وبيانات المخزون في lib/inventory.ts، والدعم في lib/support.ts. هذه ما تحتاجه المكوّنات لتعرض، ولا تحسب شيئاً يعتمده الخادم.
 */

export interface CampaignCard {
  id: string
  title: string | null
  status: "DRAFT" | "COPY_PROPOSED" | "COPY_APPROVED" | "READY"
  budget: number | null
  days: number | null
  updated: string
  imageAlt: string
  tone: number
}
