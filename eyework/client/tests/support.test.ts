/*
 * مكتب الدعم: ما يُحسب في الواجهة وحدها — شارة زمن الخدمة، وعنوان التذكرة، وسطر ما حُذف، وقسم كل شاشة،
 * وملخّص التصعيد، وأزرار الرئيسية الستة. الحالات والأولويات والنصوص من الخادم كما هي.
 */
import { describe, expect, it } from "vitest"

import { sectionOf } from "@/app/support-flow"
import { duration, slaText, ticketTitle, withDecision, type Ticket } from "@/lib/support"
import { WORKSPACES } from "@/lib/workspace"
import { escalationNote } from "@/screens/support/actions"
import { maskedSummary } from "@/screens/support/common"

describe("the service-level badge", () => {
  it("says what is left, what is late, and when the clock is paused", () => {
    expect(slaText({ kind: "FIRST_REPLY", state: "ON_TRACK", minutes: 35 })).toEqual({ text: "متبقٍّ للردّ 35 د", tone: "info" })
    expect(slaText({ kind: "RESOLVE", state: "DUE_SOON", minutes: 300 })).toEqual({ text: "متبقٍّ للحلّ 5 س", tone: "warning" })
    expect(slaText({ kind: "FIRST_REPLY", state: "BREACHED", minutes: 61 })).toEqual({ text: "تأخّر الردّ 1 س", tone: "danger" })
    expect(slaText({ kind: "RESOLVE", state: "PAUSED", minutes: null })).toEqual({ text: "الوقت متوقّف", tone: "neutral" })
    expect(slaText({ kind: "RESOLVE", state: "MET", minutes: null })).toBeNull()
    expect(duration(3 * 1440)).toBe("3 يوم")
  })
})

describe("the ticket's name", () => {
  it("is the number and the subject, or the start of the customer's message", () => {
    expect(ticketTitle({ number: 12, subject: "الطابعة", preview: "نص" })).toBe("#12 · الطابعة")
    expect(ticketTitle({ number: 3, subject: null, preview: "أ".repeat(80) })).toBe(`#3 · ${"أ".repeat(60)}`)
    expect(ticketTitle({ number: 4, subject: null, preview: null })).toBe("#4")
  })

  it("says what the app removed before saving", () => {
    expect(maskedSummary({ email: 1, link: 0, number: 1 })).toBe("حُذف: بريدٌ واحد، ورقمٌ واحد.")
    expect(maskedSummary({ email: 0, link: 2, number: 3 })).toBe("حُذف: 3 أرقام، ورابطان.")
    expect(maskedSummary({ email: 0, link: 0, number: 0 })).toBeNull()
  })
})

describe("the desk's routes", () => {
  it("belong to the home button they start from", () => {
    expect(sectionOf("")).toBe("home")
    expect(sectionOf("/settings")).toBe("home")
    expect(sectionOf("/decide")).toBe("decide")
    expect(sectionOf("/t/0d9a2c3e-0000-4000-8000-000000000000/reply")).toBe("open")
    expect(sectionOf("/kb/a/0d9a2c3e-0000-4000-8000-000000000000/publish")).toBe("knowledge")
  })

  it("start from six buttons, each with its help", () => {
    const desk = WORKSPACES.SUPPORT
    expect(desk.home.map((entry) => entry.label)).toEqual(["تذكرة جديدة", "بانتظار قراري", "التذاكر المفتوحة", "بانتظار العميل", "المُصعَّدة", "قاعدة المعرفة"])
    expect(desk.home.filter((entry) => entry.primary).map((entry) => entry.id)).toEqual(["new"])
    for (const entry of desk.home) {
      expect(entry.route.startsWith(`${desk.base}/`)).toBe(true)
      expect(desk.help[entry.id]?.lines.length).toBeGreaterThan(0)
    }
  })
})

describe("the escalation note", () => {
  it("summarises the ticket and the last customer message for the other team", () => {
    const ticket = {
      number: 7, category: "PRINTING", priority: "HIGH",
      messages: [
        { id: "1", author: "CUSTOMER", body: "أوّل", masked_count: 0, at: null },
        { id: "2", author: "AGENT", body: "ردّ", masked_count: 0, at: null },
        { id: "3", author: "CUSTOMER", body: "الطابعة\nلا تطبع", masked_count: 0, at: null },
      ],
    } as unknown as Ticket
    expect(escalationNote(ticket)).toBe("التذكرة #7 · الطباعة · أولوية عالية\nالمشكلة: الطابعة لا تطبع\nما جُرّب: ")
  })
})

describe("a decision on one of Symbol's flags", () => {
  it("is merged into that flag by its id, the others untouched", () => {
    const flag = { id: "f1", check: "TONE", severity: "MEDIUM", field: "reply", line: 1, headline: "h", suggestion: null, evidence: [], decision: null }
    const other = { ...flag, id: "f2" }
    const merged = withDecision([flag, other], { flag_id: "f1", decision: "PROCEED", decided_at: "2026-10-10T00:00:00Z" })
    expect(merged?.map((f) => [f.id, f.decision])).toEqual([["f1", "PROCEED"], ["f2", null]])
    expect(withDecision(null, { flag_id: "f1", decision: "UNDO", decided_at: "" })).toBeNull()
  })
})
