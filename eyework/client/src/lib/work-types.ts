/*
 * أنواع بيانات الشاشات
 * ====================
 * كما يردّها الخادم (المبالغ بالهللة، والتواريخ ISO) لشاشات التسويق والدعم التي لم تُوصل بعد؛
 * وبيانات المخزون في lib/inventory.ts. هذه ما تحتاجه المكوّنات لتعرض، ولا تحسب شيئاً يعتمده الخادم.
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

export interface TicketRow {
  id: string
  number: number
  customer: string
  subject: string
  channel: "EMAIL" | "WHATSAPP" | "WEB"
  received: string
  status: "NEW" | "DRAFT_READY" | "WAITING_CUSTOMER" | "ESCALATED" | "CLOSED"
  priority: "NORMAL" | "HIGH"
}

export interface TicketMessage {
  id: string
  from: "CUSTOMER" | "EMPLOYEE"
  text: string
  at: string
}

export interface TicketDraft {
  text: string
  /** لماذا كتب سيمبول ما كتب. */
  basis: string
  /** الردود الجاهزة التي استند إليها. */
  sources: { id: string; title: string }[]
  /** ما لا يعرفه سيمبول ويحتاج الموظف أن يتحقّق منه. */
  check: string[]
}
