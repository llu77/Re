/*
 * الطلبات: الترويسة والجلسة، و401 خارج /api/auth/ ينقل إلى الدخول إلا حين يُطلب السكوت.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { api, detail, errorCode, errorField, GENERIC, OFFLINE } from "@/lib/api"
import { getState, resetState } from "@/lib/store"

function reply(status: number, body: unknown = null): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: body === null ? {} : { "Content-Type": "application/json" },
  })
}

describe("api", () => {
  beforeEach(() => {
    resetState({ me: { generations_left: 1, generation_limit: 1, display_name: null, profession: null, ui_size: null, terms_current: true, ai: { assistant: { per_day: 1, used_today: 0 } } } })
    location.hash = "#/account"
  })
  afterEach(() => vi.restoreAllMocks())

  it("sends the header and the session, and reads JSON or nothing", async () => {
    const fetched = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { ok: true }))
    const result = await api<{ ok: boolean }>("POST", "/api/x", { json: { a: 1 } })
    expect(result).toEqual({ status: 200, data: { ok: true } })
    const [, init] = fetched.mock.calls[0]
    expect((init as RequestInit).headers).toMatchObject({ "X-Eyework": "1", "Content-Type": "application/json" })
    expect((init as RequestInit).credentials).toBe("same-origin")
    fetched.mockResolvedValue(reply(204))
    expect(await api("POST", "/api/y")).toEqual({ status: 204, data: null })
  })

  it("answers offline without throwing", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"))
    const result = await api("GET", "/api/me")
    expect(result.status).toBe(0)
    expect(detail(result)).toBe(OFFLINE)
  })

  it("goes to the sign-in screen on a 401 outside /api/auth/, unless asked to keep quiet", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(401, { code: "AUTH", detail: "x" }))
    await api("GET", "/api/me", { quiet: true })
    expect(location.hash).toBe("#/account")
    expect(getState().me).not.toBeNull()
    await api("GET", "/api/me")
    expect(location.hash).toBe("#/login")
    expect(getState().me).toBeNull()
    location.hash = "#/account"
    await api("POST", "/api/auth/login")
    expect(location.hash).toBe("#/account")
  })

  it("reads the server's code, field and detail, with a generic fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(422, { code: "REGISTER_INVALID", field: "NAME", detail: "الاسم" }))
    const result = await api("POST", "/api/auth/register")
    expect([errorCode(result), errorField(result), detail(result)]).toEqual(["REGISTER_INVALID", "NAME", "الاسم"])
    expect(detail({ status: 500, data: null })).toBe(GENERIC)
  })
})
