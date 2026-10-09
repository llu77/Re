/*
 * أداة الحملة: ما يُحسب في الواجهة وحدها — أسماء صفوف «حملاتي»، والقيمة المجاورة في جدول
 * الخادم، وتعارض الخيارات، وملخّص الحملة، والمسارات. الكلمات والأرقام من الخادم كما هي.
 */
import { describe, expect, it } from "vitest"

import { brief, campaignRoute, conflictOf, dailyText, imageUrl, neighbour, rowNames, type Campaign } from "@/lib/campaigns"

const campaign: Campaign = {
  id: "c1", status: "COPY_APPROVED", row_version: 3, image: { width: 400, height: 400, tag: "t9" },
  copy: { version_id: "v2", version: 2, title: "حقيبة جلدية", description: "وصفٌ قصير.", warnings: [], assistant_note: null, can_restore_previous: true, can_restore_newest: false },
  approved_version_id: "v2", generating: false,
  budget: { sar: 2750, short: "2,750 ر.س", words: "ألفان وسبعمئة وخمسون ريالاً" },
  days: { n: 14, short: "14 يوماً", words: "أربعة عشر يوماً" },
  daily: { amount: "196.43", exact: false }, versions_left: 8, created_at: "", updated_at: "", ready_at: null,
}

describe("the campaign tool", () => {
  it("names every list row uniquely: untitled by position, repeated titles by position", () => {
    const names = rowNames(
      [
        { id: "a", status: "DRAFT", title: null, updated_at: "" },
        { id: "b", status: "COPY_PROPOSED", title: "حقيبة", updated_at: "" },
        { id: "c", status: "READY", title: "حقيبة", updated_at: "" },
        { id: "d", status: "READY", title: "ساعة", updated_at: "" },
      ],
      2,
    )
    expect(names).toEqual(["حملة بلا عنوان 3", "حقيبة 4", "حقيبة 5", "ساعة"])
  })

  it("steps through the server's table and stops at its ends", () => {
    const values = [50, 100, 150]
    expect(neighbour(values, null, 1)).toBe(50)
    expect(neighbour(values, null, -1)).toBeNull()
    expect(neighbour(values, 100, 1)).toBe(150)
    expect(neighbour(values, 150, 1)).toBeNull()
    expect(neighbour(values, 50, -1)).toBeNull()
  })

  it("finds the conflicting preset from the server's pairs", () => {
    const pairs = [["MORE_FORMAL", "MORE_LIVELY"], ["NEW_DESCRIPTION", "NEW_TITLE"]]
    expect(conflictOf(pairs, "MORE_LIVELY")).toBe("MORE_FORMAL")
    expect(conflictOf(pairs, "SHORTER")).toBeNull()
  })

  it("writes the brief with the words before the digits and the daily line as the server says", () => {
    expect(dailyText(campaign)).toBe("في اليوم نحو: 196.43 ر.س")
    expect(dailyText({ ...campaign, daily: { amount: "100.00", exact: true } })).toBe("في اليوم: 100.00 ر.س")
    expect(brief(campaign).split("\n")).toEqual([
      "حقيبة جلدية", "", "وصفٌ قصير.", "",
      "الميزانية الإجمالية: ألفان وسبعمئة وخمسون ريالاً (2,750 ر.س)",
      "المدة: أربعة عشر يوماً (14 يوماً)",
      "في اليوم نحو: 196.43 ر.س",
    ])
  })

  it("routes campaigns under the marketing workspace and images by their tag", () => {
    expect(campaignRoute("c1")).toBe("#/marketing/c/c1")
    expect(campaignRoute("c1", "/edit")).toBe("#/marketing/c/c1/edit")
    expect(imageUrl(campaign)).toBe("/api/campaigns/c1/image?v=t9")
    expect(imageUrl({ ...campaign, image: null })).toBe("/api/campaigns/c1/image?v=")
  })
})
