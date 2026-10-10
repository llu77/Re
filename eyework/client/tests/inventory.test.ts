/*
 * بوابة المخزون: ما يُحسب في الواجهة وحدها — الكميات بالألف كما تُكتب وتُقرأ، والأشهر، والمسارات،
 * وقسم كل شاشة، وبنود «يحتاج انتباهك». الأرقام والكلمات من الخادم كما هي.
 */
import { describe, expect, it } from "vitest"

import { sectionOf } from "@/app/inventory-flow"
import { countRoute, formatMilli, milliInput, monthLabel, monthRange, parseMilli, purchaseRoute, quantityText, shiftMonth, type Summary } from "@/lib/inventory"
import { attentionItems } from "@/screens/inventory/home"

const summary: Summary = {
  today: "2026-10-09", month: "2026-10",
  month_totals: { purchases: { net: 0, vat: 0, gross: 0 }, returns: { net: 0, vat: 0, gross: 0 }, reversals: { net: 0, vat: 0, gross: 0 }, net: { net: 0, vat: 0, gross: 0 } },
  stock_value: 0, settings: null,
  attention: { drafts: 3, purchase_drafts: 2, return_drafts: 1, low_stock: 1, awaiting_credit_note: 1, credit_note_overdue: 0, uncounted: 0, short_delivery: 1, open_count: { id: "c1", label: "ج-0003" } },
  counts: { items: 3, suppliers: 1, movements: 4 },
}

describe("quantities in thousandths", () => {
  it("parses whole and fractional quantities as the storekeeper writes them", () => {
    expect(parseMilli("12", false)).toBe(12000)
    expect(parseMilli("١٢", false)).toBe(12000)
    expect(parseMilli("2.5", true)).toBe(2500)
    expect(parseMilli("2٫250", true)).toBe(2250)
    expect(parseMilli("2.5", false)).toBeNull()
    expect(parseMilli("0", true)).toBeNull()
    expect(parseMilli("1.2345", true)).toBeNull()
    expect(parseMilli("3", true, 2500)).toBeNull()
  })

  it("accepts zero only where it is asked for, in either digits, and a comma only as a thousands separator", () => {
    expect(parseMilli("٠", false, undefined, { zero: true })).toBe(0)
    expect(parseMilli("0.0", true, undefined, { zero: true })).toBe(0)
    expect(parseMilli("", false, undefined, { zero: true })).toBeNull()
    expect(parseMilli("٠", false)).toBeNull()
    expect(parseMilli("1,250", false)).toBe(1250000)
    expect(parseMilli("١٬٢٥٠", false)).toBe(1250000)
    expect(parseMilli("2,5", true)).toBeNull()
    expect(parseMilli("10,5", true)).toBeNull()
  })

  it("formats thousandths without trailing zeros and with grouping", () => {
    expect(formatMilli(12000)).toBe("12")
    expect(formatMilli(2500)).toBe("2.5")
    expect(formatMilli(1250000)).toBe("1,250")
    expect(milliInput(1250500)).toBe("1250.5")
    expect(milliInput(null)).toBe("")
    expect(quantityText(2500, "كيلوغرام")).toBe("2.5 كيلوغرام")
  })
})

describe("months", () => {
  it("names a month in Arabic with Latin digits and bounds it", () => {
    expect(monthLabel("2026-10")).toBe("أكتوبر 2026")
    expect(monthRange("2026-02")).toEqual({ from: "2026-02-01", to: "2026-02-28" })
    expect(monthRange("2028-02")).toEqual({ from: "2028-02-01", to: "2028-02-29" })
    expect(shiftMonth("2026-01", -1)).toBe("2025-12")
    expect(shiftMonth("2026-12", 1)).toBe("2027-01")
  })
})

describe("routes and sections", () => {
  it("builds document routes and maps every screen to its home entry", () => {
    expect(purchaseRoute("x", "/review")).toBe("#/inventory/p/x/review")
    expect(countRoute("y")).toBe("#/inventory/c/y")
    expect(sectionOf("")).toBe("home")
    expect(sectionOf("/purchases/new")).toBe("purchase")
    expect(sectionOf("/p/abc/review")).toBe("purchase")
    expect(sectionOf("/returns?awaiting=1")).toBe("return")
    expect(sectionOf("/items/new")).toBe("item")
    expect(sectionOf("/i/abc/edit")).toBe("stock")
    expect(sectionOf("/suppliers/new")).toBe("stock")
    expect(sectionOf("/c/abc/l/def")).toBe("count")
    expect(sectionOf("/expenses")).toBe("expenses")
    expect(sectionOf("/totals")).toBe("totals")
    expect(sectionOf("/settings")).toBe("home")
  })

  it("lists what needs attention, the open count first, and an overdue note replaces the waiting one", () => {
    expect(attentionItems(summary).map((item) => item.id)).toEqual(["open-count", "drafts", "return-drafts", "short", "awaiting", "low"])
    expect(attentionItems({ ...summary, attention: { ...summary.attention, credit_note_overdue: 1, open_count: null } }).map((item) => item.id)).toEqual(["drafts", "return-drafts", "short", "overdue", "low"])
    expect(attentionItems(summary)[0].href).toBe("#/inventory/c/c1")
  })
})
