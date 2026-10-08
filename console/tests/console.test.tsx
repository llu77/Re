import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { PayloadView } from "@/components/console/payload-view"
import { ProposalPage } from "@/components/console/proposal-page"
import { parseRoute } from "@/components/console/route"
import type { PractitionerApi } from "@/lib/api"
import type { Proposal } from "@/lib/types"

const ID = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"

/** رسمٌ بشكل ما يُنتجه `tools/visual_exercises.py`: علامة الجانب عند حافة اليمين. */
const SVG =
  '<svg width="500" height="380" viewBox="0 0 500 380" xmlns="http://www.w3.org/2000/svg">' +
  '<rect x="468" y="40" width="26" height="300" rx="8" fill="#E8A020" opacity="0.3"/>' +
  '<polygon points="490,190 454,160 454,220" fill="#E8A020"/></svg>'

function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: ID,
    patient_id: "11111111-2222-4333-8444-555555555555",
    kind: "PLAN",
    status: "PENDING",
    payload: { module: "DRESSING", steps: [{ title: "أدخِل الذراع المصابة", side: "AFFECTED" }] },
    provenance: { model: "x" },
    affected_side: "RIGHT",
    priority: 2,
    is_red_flag: true,
    version: 1,
    created_at: "2026-10-07T10:00:00Z",
    queued_at: "2026-10-07T10:00:00Z",
    expires_at: "2026-10-10T10:00:00Z",
    reviewer_id: null,
    decision_at: null,
    rejection_reason: null,
    ...overrides,
  }
}

function fakeApi(overrides: Partial<PractitionerApi> = {}): PractitionerApi {
  return {
    queue: vi.fn(async () => ({ items: [], more: false })),
    proposal: vi.fn(async () => proposal()),
    citations: vi.fn(async () => [
      {
        source_id: "s1",
        external_id: "10000001",
        title: "Evidence-based rehabilitation",
        url: "https://pubmed.ncbi.nlm.nih.gov/10000001/",
        published_year: 2024,
        locator: null,
        added_by: "u",
        added_at: "2026-10-07T10:00:00Z",
      },
    ]),
    approve: vi.fn(async () => proposal({ status: "APPROVED" })),
    reject: vi.fn(async () => proposal({ status: "REJECTED" })),
    redFlags: vi.fn(async () => ({ items: [], more: false })),
    acknowledge: vi.fn(),
    logout: vi.fn(async () => undefined),
    ...overrides,
  } as PractitionerApi
}

describe("صفحة المقترح", () => {
  it("تعرض الحمولة كاملةً والأدلّة بجانبها", async () => {
    render(<ProposalPage api={fakeApi()} id={ID} onDecided={() => undefined} />)
    expect(await screen.findByText("أدخِل الذراع المصابة")).toBeTruthy()
    const citations = screen.getByRole("complementary", { name: /الأدلّة/ })
    const link = within(citations).getByRole("link", { name: /Evidence-based rehabilitation/ })
    expect(link.getAttribute("rel")).toContain("noopener")
  })

  it("الاعتماد خطوتان: الضغطة الأولى لا تعتمد شيئاً", async () => {
    const user = userEvent.setup()
    const api = fakeApi()
    const decided = vi.fn()
    render(<ProposalPage api={api} id={ID} onDecided={decided} />)
    await user.click(await screen.findByRole("button", { name: "اعتماد" }))
    expect(api.approve).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "تأكيد الاعتماد" }))
    expect(api.approve).toHaveBeenCalledWith(ID)
    await waitFor(() => expect(decided).toHaveBeenCalledWith("اعتُمد المقترح."))
  })

  it("الرفض لا يُرسل بلا سبب، ويُرسل السبب منقّحاً", async () => {
    const user = userEvent.setup()
    const api = fakeApi()
    render(<ProposalPage api={api} id={ID} onDecided={() => undefined} />)
    await user.click(await screen.findByRole("button", { name: "رفض" }))
    const confirm = screen.getByRole("button", { name: "تأكيد الرفض" }) as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    await user.type(screen.getByLabelText("سبب الرفض (إلزامي)"), "   ")
    expect(confirm.disabled).toBe(true)
    await user.type(screen.getByLabelText("سبب الرفض (إلزامي)"), "الخطوة الثانية غير آمنة  ")
    await user.click(confirm)
    expect(api.reject).toHaveBeenCalledWith(ID, "الخطوة الثانية غير آمنة")
  })

  it("رفض الخادم يُعرض ويبقى المقترح مفتوحاً", async () => {
    const user = userEvent.setup()
    const { ApiError } = await import("@/lib/api")
    const api = fakeApi({
      approve: vi.fn(async () => {
        throw new ApiError(409, "حالة المقترح لا تسمح بذلك")
      }),
    })
    const decided = vi.fn()
    render(<ProposalPage api={api} id={ID} onDecided={decided} />)
    await user.click(await screen.findByRole("button", { name: "اعتماد" }))
    await user.click(screen.getByRole("button", { name: "تأكيد الاعتماد" }))
    expect((await screen.findByRole("alert")).textContent).toContain("حالة المقترح لا تسمح بذلك")
    expect(decided).not.toHaveBeenCalled()
  })

  it("مجموعة الرسوم تُعرض صوراً كما سيراها المريض، والترميز ثانويٌّ مطويّ", async () => {
    const api = fakeApi({
      proposal: vi.fn(async () =>
        proposal({ kind: "ILLUSTRATION_SET", payload: { illustrations: [{ exercise_type: "scanning_grid", svg: SVG }] } }),
      ),
    })
    const { container } = render(<ProposalPage api={api} id={ID} onDecided={() => undefined} />)
    const image = (await screen.findByRole("img", { name: /تمرين مسح الشبكة البصرية/ })) as HTMLImageElement
    expect(image.src.startsWith("data:image/svg+xml")).toBe(true)
    expect(decodeURIComponent(image.src)).toContain('fill="#E8A020"')
    const figure = image.closest("figure") as HTMLElement
    expect(within(figure).getByText("الجانب الأيمن")).toBeTruthy()
    expect(within(figure).getByText("scanning_grid")).toBeTruthy()
    // لا ترميز يُحقن في الصفحة: الرسم صورةٌ لا عناصر.
    expect(container.querySelector('polygon[points="490,190 454,160 454,220"]')).toBeNull()
    // المصدر موجودٌ للمراجعة، مطويٌّ تحت الصورة لا بدلها.
    const source = screen.getByText("مصدر الرسوم (SVG)").closest("details") as HTMLDetailsElement
    expect(source.open).toBe(false)
    expect(source.textContent).toContain("<svg")
    expect(screen.getByRole("button", { name: "اعتماد" })).toBeTruthy()
  })

  it.each([
    ["سكربت", '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'],
    ["معالج حدث", '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="1" height="1"/></svg>'],
    ["مرجع خارجي", '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://x.test/p.png"/></svg>'],
    ["بلا فضاء أسماء SVG", '<svg><rect width="1" height="1"/></svg>'],
    ["ترميز معطوب", '<svg xmlns="http://www.w3.org/2000/svg"><rect'],
  ])("رسمٌ لا يُعرض (%s) لا يُرسم ولا يُعرض اعتماده", async (_, svg) => {
    const api = fakeApi({
      proposal: vi.fn(async () =>
        proposal({ kind: "ILLUSTRATION_SET", payload: { illustrations: [{ exercise_type: "scanning_grid", svg }] } }),
      ),
    })
    render(<ProposalPage api={api} id={ID} onDecided={() => undefined} />)
    expect(await screen.findByText(/لا يمكن عرض هذا الرسم/)).toBeTruthy()
    expect(screen.queryByRole("img")).toBeNull()
    expect(screen.queryByRole("button", { name: "اعتماد" })).toBeNull()
    expect(screen.getByRole("button", { name: "رفض" })).toBeTruthy()
  })

  it("مقترحٌ قُرِّر لا يعرض أزرار القرار", async () => {
    const api = fakeApi({ proposal: vi.fn(async () => proposal({ status: "REJECTED", rejection_reason: "سبب" })) })
    render(<ProposalPage api={api} id={ID} onDecided={() => undefined} />)
    expect(await screen.findByText(/قُرِّر هذا المقترح/)).toBeTruthy()
    expect(screen.queryByRole("button", { name: "اعتماد" })).toBeNull()
  })
})

describe("عرض الحمولة", () => {
  it("يعرض النصّ نصّاً ولا يفسّره", () => {
    const { container } = render(<PayloadView value={{ note: "<img src=x onerror=alert(1)>" }} />)
    expect(container.querySelector("img")).toBeNull()
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>")
  })

  it("يعرض كل مستوى من البنية", () => {
    render(<PayloadView value={{ a: { b: [1, true, null, ""] } }} />)
    expect(screen.getByText("نعم")).toBeTruthy()
    expect(screen.getByText("(نصّ فارغ)")).toBeTruthy()
  })
})

describe("التوجيه", () => {
  it("يقبل معرّف UUID وحده، وغيره يعود إلى الطابور", () => {
    expect(parseRoute(`#/queue/${ID}`)).toEqual({ name: "proposal", id: ID })
    expect(parseRoute("#/queue/../../practitioner/logout")).toEqual({ name: "queue" })
    expect(parseRoute("#/red-flags")).toEqual({ name: "red-flags" })
    expect(parseRoute("")).toEqual({ name: "queue" })
  })
})
