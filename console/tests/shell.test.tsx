import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ConsoleShell } from "@/components/console/console-shell"
import type { Proposal, RedFlag } from "@/lib/types"

/**
 * اللوحة كاملةً على خادمٍ مصطنع يجيب كما يجيب `api/practitioner/routes.py`:
 * `limit` افتراضيّه 50 وسقفه 200، والبلاغات الأقدم أولاً، والاستلام يُخرج
 * البلاغ من القائمة.
 */
const SESSION = { token: "t", role: "PRACTITIONER", email: "practitioner@example.test" }

function uuid(index: number): string {
  return `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`
}

function proposal(index: number): Proposal {
  return {
    id: uuid(index),
    patient_id: uuid(10_000 + index),
    kind: "DOCUMENTATION",
    status: "PENDING",
    payload: { summary: `ملخّص ${index}` },
    provenance: {},
    affected_side: null,
    priority: 5,
    is_red_flag: false,
    version: 1,
    created_at: "2026-10-07T10:00:00Z",
    queued_at: "2026-10-07T10:00:00Z",
    expires_at: "2026-10-10T10:00:00Z",
    reviewer_id: null,
    decision_at: null,
    rejection_reason: null,
  }
}

function flag(index: number): RedFlag {
  return {
    id: uuid(20_000 + index),
    patient_id: uuid(30_000 + index),
    body: `بلاغ رقم ${index}`,
    reported_at: new Date(Date.UTC(2026, 9, 7, 8, index)).toISOString(),
    acknowledged_at: null,
    escalation_seconds: null,
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

function serve({ proposals = 0, flags = 0 }: { proposals?: number; flags?: number }) {
  const queue = Array.from({ length: proposals }, (_, index) => proposal(index))
  let open = Array.from({ length: flags }, (_, index) => flag(index))
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(input, "http://console.test")
      const limit = Math.min(Number(url.searchParams.get("limit") ?? 50), 200)
      if (url.pathname === "/practitioner/queue") return json(queue.slice(0, limit))
      if (url.pathname === "/practitioner/red-flags") return json(open.slice(0, limit))
      const acknowledged = url.pathname.match(/^\/practitioner\/red-flags\/([^/]+)\/acknowledge$/)
      if (acknowledged && init?.method === "POST") {
        const found = open.find((item) => item.id === acknowledged[1])
        if (!found) return json({ detail: "البلاغ مُستلَم بالفعل" }, 409)
        open = open.filter((item) => item !== found)
        return json({ ...found, acknowledged_at: "2026-10-07T09:00:00Z", escalation_seconds: 60 })
      }
      return json({ detail: "غير موجود" }, 404)
    }),
  )
}

function shell() {
  return render(<ConsoleShell session={SESSION} onSignedOut={() => undefined} />)
}

describe("الإعلان عن نجاح الإجراء", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("الاستلام الثاني بالنصّ نفسه يُعلَن أيضاً", async () => {
    window.location.hash = "#/red-flags"
    serve({ flags: 2 })
    const user = userEvent.setup()
    shell()
    const status = screen.getByRole("status")

    async function acknowledgeFirst() {
      const [first] = await screen.findAllByRole("button", { name: "استلام البلاغ" })
      await user.click(first)
      await user.click(screen.getByRole("button", { name: "تأكيد الاستلام" }))
    }

    await acknowledgeFirst()
    await within(status).findByText("سُجّل استلام البلاغ.")
    await waitFor(() => expect(screen.getAllByRole("button", { name: "استلام البلاغ" })).toHaveLength(1))

    // ما تُعلنه المنطقة الحيّة هو ما يُضاف إليها؛ نصٌّ لم يتغيّر في عقدةٍ باقية لا يُقرأ.
    const added: Node[] = []
    const observer = new MutationObserver((records) => {
      for (const record of records) added.push(...Array.from(record.addedNodes))
    })
    observer.observe(status, { childList: true, subtree: true, characterData: true })

    await acknowledgeFirst()
    await screen.findByText("لا بلاغات عاجلة غير مستلَمة.")
    for (const record of observer.takeRecords()) added.push(...Array.from(record.addedNodes))
    observer.disconnect()

    expect(added.some((node) => node.textContent?.includes("سُجّل استلام البلاغ."))).toBe(true)
  })
})
