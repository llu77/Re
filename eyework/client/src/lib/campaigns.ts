/*
 * أداة الحملة: ما يردّه الخادم وما يُطلب منه
 * ==========================================
 * منقولٌ من static/app.js. كل كتابةٍ مشروطةٌ بما رآه صاحبها (`expected_row_version`)؛ والخادم
 * مصدر كل كلمة ورقم: الميزانية والمدّة بكلماتها من /api/choices، والحالة بتسميتها هنا.
 */

import { api, type ApiResult } from "./api"

export const PERSONA = "سيمبول"

export const STATUS_LABELS: Record<string, string> = {
  DRAFT: "مسودة",
  COPY_PROPOSED: "نصٌّ بانتظار موافقتك",
  COPY_APPROVED: "نصٌّ موافَقٌ عليه",
  READY: "جاهزة للتسليم",
}

export const PRESET_LABELS: Record<string, string> = {
  SHORTER: "أقصر",
  SIMPLER: "لغة أبسط",
  MORE_FORMAL: "أكثر رسمية",
  MORE_LIVELY: "أكثر حيوية",
  NEW_TITLE: "عنوانٌ آخر فقط",
  NEW_DESCRIPTION: "وصفٌ آخر فقط",
}

export const WARNING_LABELS: Record<string, string> = { PRICE: "سعر", HEALTH_CLAIM: "ادّعاءٌ صحي", SUPERLATIVE: "مبالغة" }

export const BUSY_ELSEWHERE = "يكتب سيمبول نصّ حملةٍ أخرى الآن. حين ينتهي يمكن البدء هنا."

export type CampaignStatus = "DRAFT" | "COPY_PROPOSED" | "COPY_APPROVED" | "READY" | "CANCELLED"

export interface Copy {
  version_id: string
  version: number
  title: string
  description: string
  warnings: string[]
  assistant_note: string | null
  can_restore_previous: boolean
  can_restore_newest: boolean
}

export interface Campaign {
  id: string
  status: CampaignStatus
  row_version: number
  image: { width: number; height: number; tag: string } | null
  copy: Copy | null
  approved_version_id: string | null
  generating: boolean
  budget: { sar: number; short: string; words: string } | null
  days: { n: number; short: string; words: string } | null
  daily: { amount: string; exact: boolean } | null
  versions_left: number
  created_at: string
  updated_at: string
  ready_at: string | null
}

export interface CampaignListItem {
  id: string
  status: CampaignStatus
  title: string | null
  updated_at: string
}

export interface CampaignPage {
  items: CampaignListItem[]
  has_more: boolean
}

/** ردّ الكتابة: الحملة بعدها، أو صورةٌ لا تصلح مع كلمة سيمبول عنها. */
export interface GenerationResult {
  result: "OK" | "UNUSABLE_PHOTO"
  message: string | null
  assistant_note?: string | null
  campaign: Campaign
}

export interface BudgetTable {
  values: { sar: number; short: string; words: string }[]
  presets: number[]
}

export interface DaysTable {
  values: { n: number; short: string; words: string }[]
  presets: number[]
}

export function imageUrl(campaign: Campaign): string {
  return `/api/campaigns/${campaign.id}/image?v=${campaign.image ? campaign.image.tag : ""}`
}

export function campaignRoute(id: string, suffix = ""): string {
  return `#/marketing/c/${id}${suffix}`
}

export function dailyText(campaign: Campaign): string {
  if (!campaign.daily) return ""
  const amount = `${campaign.daily.amount} ر.س`
  return campaign.daily.exact ? `في اليوم: ${amount}` : `في اليوم نحو: ${amount}`
}

/** ملخّص الحملة كما يُنسخ أو يُشارك. */
export function brief(campaign: Campaign): string {
  const copy = campaign.copy
  return [
    copy?.title ?? "", "", copy?.description ?? "", "",
    `الميزانية الإجمالية: ${campaign.budget?.words ?? ""} (${campaign.budget?.short ?? ""})`,
    `المدة: ${campaign.days?.words ?? ""} (${campaign.days?.short ?? ""})`,
    dailyText(campaign),
  ].join("\n")
}

/** القيمة التالية أو السابقة في جدول الخادم، أو null في الطرف؛ وبلا قيمةٍ «أكثر» تبدأ من أوّله. */
export function neighbour<T>(values: T[], current: T | null, delta: 1 | -1): T | null {
  if (current === null) return delta > 0 ? values[0] : null
  const index = values.indexOf(current) + delta
  return index >= 0 && index < values.length ? values[index] : null
}

/** الخيار المتعارض مع هذا الخيار في جدول الخادم، إن وُجد. */
export function conflictOf(conflicts: string[][], preset: string): string | null {
  const pair = conflicts.find((p) => p.includes(preset))
  return pair ? (pair.find((p) => p !== preset) ?? null) : null
}

/** أسماء صفوف «حملاتي»: لكل صفٍّ اسمٌ لا يشاركه فيه غيره («التحكم الصوتي» يضغط بالاسم). الحملة بلا
 *  عنوانٍ تُرقَّم بموضعها، وكذلك عنوانٌ يتكرّر في الصفحة (حملتان لصورةٍ واحدة قد يُقترح لهما العنوان نفسه). */
export function rowNames(items: CampaignListItem[], first: number): string[] {
  const titles = items.map((item) => item.title)
  const repeated = new Set(titles.filter((title, index) => title && titles.indexOf(title) !== index))
  return items.map((item, index) => {
    const position = first + index + 1
    return !item.title ? `حملة بلا عنوان ${position}` : repeated.has(item.title) ? `${item.title} ${position}` : item.title
  })
}

/** التطبيق مفتوحٌ من الشاشة الرئيسية لا من تبويب Safari. */
export function installedApp(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true
}

/* ── الطلبات ─────────────────────────────────────────────────────── */

export const fetchCampaign = (id: string) => api<Campaign>("GET", `/api/campaigns/${id}`)
export const listCampaigns = (page: number) => api<CampaignPage>("GET", `/api/campaigns?page=${page}`)

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"]

export function createCampaign(file: File): Promise<ApiResult<Campaign>> {
  return api<Campaign>("POST", "/api/campaigns", { raw: file, type: IMAGE_TYPES.includes(file.type) ? file.type : "image/jpeg" })
}

export function replaceImage(campaign: Campaign, file: File): Promise<ApiResult<Campaign>> {
  return api<Campaign>("PUT", `/api/campaigns/${campaign.id}/image?expected_row_version=${campaign.row_version}`, {
    raw: file, type: IMAGE_TYPES.includes(file.type) ? file.type : "image/jpeg",
  })
}

export const generate = (campaign: Campaign) =>
  api<GenerationResult>("POST", `/api/campaigns/${campaign.id}/copy`, { json: { expected_row_version: campaign.row_version } })

export const editCopy = (campaign: Campaign, presets: string[], note: string | null) =>
  api<GenerationResult>("POST", `/api/campaigns/${campaign.id}/copy/edit`, {
    json: { expected_row_version: campaign.row_version, expected_version_id: campaign.copy?.version_id, presets, note },
  })

export const approve = (campaign: Campaign) =>
  api<Campaign>("POST", `/api/campaigns/${campaign.id}/copy/approve`, {
    json: { expected_row_version: campaign.row_version, version_id: campaign.copy?.version_id },
  })

export const unapprove = (campaign: Campaign) =>
  api<Campaign>("POST", `/api/campaigns/${campaign.id}/copy/unapprove`, { json: { expected_row_version: campaign.row_version } })

export const restore = (campaign: Campaign, target: "previous" | "newest") =>
  api<Campaign>("POST", `/api/campaigns/${campaign.id}/copy/restore`, {
    json: { expected_row_version: campaign.row_version, expected_version_id: campaign.copy?.version_id, target },
  })

export const setBudget = (campaign: Campaign, sar: number) =>
  api<Campaign>("PUT", `/api/campaigns/${campaign.id}/budget`, { json: { expected_row_version: campaign.row_version, budget_sar: sar } })

export const setDays = (campaign: Campaign, days: number) =>
  api<Campaign>("PUT", `/api/campaigns/${campaign.id}/days`, { json: { expected_row_version: campaign.row_version, days } })

export const confirm = (campaign: Campaign) =>
  api<Campaign>("POST", `/api/campaigns/${campaign.id}/confirm`, {
    json: {
      expected_row_version: campaign.row_version, version_id: campaign.approved_version_id,
      budget_sar: campaign.budget?.sar, days: campaign.days?.n,
    },
  })

export const cancel = (campaign: Campaign) =>
  api<Campaign>("POST", `/api/campaigns/${campaign.id}/cancel`, { json: { expected_row_version: campaign.row_version } })

export const fetchImage = (campaign: Campaign) => api<Blob>("GET", imageUrl(campaign), { as: "blob" })
