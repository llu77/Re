/*
 * المبالغ
 * =======
 * بالهللة، أعداداً صحيحة: لا كسور عشرية في الحساب، فلا يختلف مجموعٌ عن مجموع بنصف
 * هللة. والضريبة بالنقطة الأساسية (1500 = 15%) كما يرسلها الخادم في /api/choices،
 * لا ثابتاً هنا. والتقريب نصفٌ إلى الأعلى على مستوى السطر، كما يحسب الخادم؛ والخادم
 * هو من يعتمد المجموع، وما هنا عرضٌ لما سيحسبه.
 */

/** أكبر مبلغٍ يُقبل في حقل: 99,999,999.99 ر.س. */
export const MAX_HALALAS = 9_999_999_999

const DIGITS: Record<string, string> = {
  "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
  "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}

/** أرقامٌ عربية أو فارسية إلى لاتينية، والفاصلة العشرية العربية إلى نقطة، وحذف فواصل الآلاف. */
export function normaliseDigits(text: string): string {
  return text
    .replace(/[٠-٩۰-۹]/g, (d) => DIGITS[d] ?? d)
    .replace(/٫/g, ".")
    .replace(/[٬,\s]/g, "")
}

/** «1,250.5» → 125050 هللة؛ أو null إن لم يكن مبلغاً صالحاً (سالباً، أو بأكثر من منزلتين). */
export function parseAmount(text: string): number | null {
  const value = normaliseDigits(text.trim())
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(value)) return null
  const [whole, fraction = ""] = value.split(".")
  const halalas = Number(whole) * 100 + Number(fraction.padEnd(2, "0"))
  return halalas <= MAX_HALALAS ? halalas : null
}

/** عددٌ صحيحٌ موجب (كمية): «١٢» → 12؛ أو null. */
export function parseQuantity(text: string, max = 100_000): number | null {
  const value = normaliseDigits(text.trim())
  if (!/^\d{1,6}$/.test(value)) return null
  const n = Number(value)
  return n >= 1 && n <= max ? n : null
}

const grouping = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 })

/** 125050 → «1,250.50». */
export function formatAmount(halalas: number): string {
  const sign = halalas < 0 ? "-" : ""
  return sign + grouping.format(Math.abs(halalas) / 100)
}

/** 125050 → «1,251» للبطاقات: المجموع بلا هللات. */
export function formatWhole(halalas: number): string {
  return whole.format(Math.round(halalas / 100))
}

/** ضريبة مبلغٍ قبلها، مقرّبةً نصفاً إلى الأعلى. */
export function vatOnNet(net: number, rateBp: number): number {
  return Math.floor((net * rateBp + 5000) / 10000)
}

/** مبلغٌ شاملٌ للضريبة ← صافيه وضريبته؛ ومجموعهما الشامل نفسه دائماً. */
export function splitGross(gross: number, rateBp: number): { net: number; vat: number } {
  const net = Math.floor((gross * 10000 + Math.floor((10000 + rateBp) / 2)) / (10000 + rateBp))
  return { net, vat: gross - net }
}

export interface LineInput {
  quantity: number
  unitCost: number
}

/** سطرٌ: الصافي = الكمية × سعر الوحدة، وضريبته مقرّبة على السطر. */
export function lineTotals(line: LineInput, rateBp: number) {
  const net = line.quantity * line.unitCost
  const vat = vatOnNet(net, rateBp)
  return { net, vat, gross: net + vat }
}

export function invoiceTotals(lines: LineInput[], rateBp: number) {
  return lines.reduce(
    (sum, line) => {
      const t = lineTotals(line, rateBp)
      return { net: sum.net + t.net, vat: sum.vat + t.vat, gross: sum.gross + t.gross }
    },
    { net: 0, vat: 0, gross: 0 },
  )
}

/** سعر الوحدة من قيمة سطرٍ وكميته بالألف: 100000 هللة ÷ 10000 ← 10000 (مقرّباً). */
export function unitPrice(valueHalalas: number, quantityMilli: number): number | null {
  if (quantityMilli <= 0) return null
  return Math.round((valueHalalas * 1000) / quantityMilli)
}

/** قيمة سطرٍ بكميةٍ بالألف وسعر وحدة: 2500 × 900 ← 2250 هللة (مقرّباً). */
export function lineValue(quantityMilli: number, unitPriceHalalas: number): number {
  return Math.round((quantityMilli * unitPriceHalalas) / 1000)
}
