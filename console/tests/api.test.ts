import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError, loadSession, login, practitionerApi } from "@/lib/api"

function reply(status: number, body?: unknown) {
  return vi.fn(async () =>
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  )
}

describe("عميل بوابة الممارس", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("يرسل الرمز في Authorization إلى /practitioner ولا يرسل ملفّات الارتباط", async () => {
    const fetchMock = reply(200, [])
    vi.stubGlobal("fetch", fetchMock)
    await practitionerApi({ token: "t-1", role: "PRACTITIONER" }, () => undefined).queue()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("/practitioner/queue")
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t-1")
    expect(init.credentials).toBe("omit")
  })

  it("الرفض يرسل السبب في الجسم إلى مسار المقترح وحده", async () => {
    const fetchMock = reply(200, {})
    vi.stubGlobal("fetch", fetchMock)
    const id = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"
    await practitionerApi({ token: "t", role: "PRACTITIONER" }, () => undefined).reject(id, "غير مناسب")
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`/practitioner/proposals/${id}/reject`)
    expect(init.method).toBe("POST")
    expect(JSON.parse(String(init.body))).toEqual({ reason: "غير مناسب" })
  })

  it("رسالة الخادم النصّية تُعرض كما هي", async () => {
    vi.stubGlobal("fetch", reply(409, { detail: "حالة المقترح لا تسمح بذلك" }))
    const api = practitionerApi({ token: "t", role: "PRACTITIONER" }, () => undefined)
    await expect(api.approve("x")).rejects.toMatchObject({ status: 409, message: "حالة المقترح لا تسمح بذلك" })
  })

  it("أخطاء التحقّق لا تُعيد ما أرسله المستخدم", async () => {
    vi.stubGlobal("fetch", reply(422, { detail: [{ msg: "x", input: "كلمة-سرية" }] }))
    const error = await login("a@b.test", "كلمة-سرية").catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe("قيمةٌ غير صالحة في الطلب.")
    expect((error as ApiError).message).not.toContain("كلمة-سرية")
  })

  it("401 ينهي الجلسة محلياً ويُبلغ الواجهة", async () => {
    window.sessionStorage.setItem(
      "symbol.practitioner.session",
      JSON.stringify({ token: "old", role: "PRACTITIONER" }),
    )
    vi.stubGlobal("fetch", reply(401, { detail: "جلسة غير صالحة" }))
    const expired = vi.fn()
    await expect(practitionerApi({ token: "old", role: "PRACTITIONER" }, expired).queue()).rejects.toBeInstanceOf(ApiError)
    expect(expired).toHaveBeenCalledOnce()
    expect(loadSession()).toBeNull()
  })

  it("401 لطلبٍ أُرسل بجلسةٍ انتهت لا يُخرج الجلسة التي بعدها", async () => {
    const old = { token: "old", role: "PRACTITIONER" }
    window.sessionStorage.setItem("symbol.practitioner.session", JSON.stringify(old))
    const answers: ((response: Response) => void)[] = []
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => answers.push(resolve))))
    const expired = vi.fn()
    const api = practitionerApi(old, expired)

    // طلبان بالجلسة القديمة؛ الأول يعود 401 فتظهر شاشة الدخول.
    const first = api.queue()
    const late = api.redFlags()
    answers[0](new Response(JSON.stringify({ detail: "جلسة غير صالحة" }), { status: 401 }))
    await expect(first).rejects.toBeInstanceOf(ApiError)
    expect(expired).toHaveBeenCalledOnce()

    // الممارس يدخل من جديد، ثم يعود الطلب الثاني القديم بـ401.
    vi.stubGlobal("fetch", reply(200, { token: "new", role: "PRACTITIONER" }))
    await login("a@b.test", "secret")
    answers[1](new Response(JSON.stringify({ detail: "جلسة غير صالحة" }), { status: 401 }))
    await expect(late).rejects.toBeInstanceOf(ApiError)

    expect(expired).toHaveBeenCalledOnce()
    expect(loadSession()).toEqual({ token: "new", role: "PRACTITIONER" })
  })

  it("الخروج المقصود لا يُعلَن انتهاءَ جلسة حين يعود طلبٌ سابقٌ بـ401", async () => {
    let answer: (response: Response) => void = () => undefined
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.endsWith("/logout")
          ? Promise.resolve(new Response(null, { status: 204 }))
          : new Promise<Response>((resolve) => {
              answer = resolve
            }),
      ),
    )
    const expired = vi.fn()
    const api = practitionerApi({ token: "t", role: "PRACTITIONER" }, expired)
    const refreshing = api.queue()
    await api.logout()
    answer(new Response(JSON.stringify({ detail: "جلسة غير صالحة" }), { status: 401 }))
    await expect(refreshing).rejects.toBeInstanceOf(ApiError)
    expect(expired).not.toHaveBeenCalled()
  })

  it("انقطاع الشبكة رسالةٌ مفهومة لا استثناءٌ خام", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch")
    }))
    const api = practitionerApi({ token: "t", role: "PRACTITIONER" }, () => undefined)
    await expect(api.queue()).rejects.toMatchObject({ status: 0 })
  })

  it("تسجيل الدخول يحفظ الجلسة في هذا التبويب", async () => {
    vi.stubGlobal("fetch", reply(200, { token: "new", role: "PRACTITIONER" }))
    await login("a@b.test", "secret")
    expect(loadSession()).toEqual({ token: "new", role: "PRACTITIONER" })
  })
})
