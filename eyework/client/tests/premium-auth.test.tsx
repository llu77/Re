import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { AuthForm, passwordStrength, PasswordStrengthIndicator } from "@/components/ui/premium-auth"

function respond(status: number, body?: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
    }),
  )
}

function setup() {
  const onSignedIn = vi.fn()
  const onStartSignup = vi.fn()
  render(<AuthForm onSignedIn={onSignedIn} onStartSignup={onStartSignup} />)
  return { onSignedIn, onStartSignup, user: userEvent.setup() }
}

describe("AuthForm", () => {
  it("signs in with a real request and hands over on 204", async () => {
    const fetch = respond(204)
    const { onSignedIn, user } = setup()
    await user.type(screen.getByLabelText("اسم الدخول"), "  ali@example.sa ")
    await user.type(screen.getByLabelText("كلمة المرور"), "Strong-Password-2026")
    await user.click(screen.getByRole("button", { name: "ادخل" }))
    await waitFor(() => expect(onSignedIn).toHaveBeenCalledOnce())
    const [path, init] = fetch.mock.calls[0]
    expect(path).toBe("/api/auth/login")
    expect(init).toMatchObject({ method: "POST", credentials: "same-origin", cache: "no-store" })
    expect((init!.headers as Record<string, string>)["X-Eyework"]).toBe("1")
    expect(JSON.parse(init!.body as string)).toEqual({ username: "ali@example.sa", password: "Strong-Password-2026" })
  })

  it("shows the server's own refusal and stays", async () => {
    respond(401, { code: "LOGIN", detail: "بيانات الدخول غير صحيحة." })
    const { onSignedIn, user } = setup()
    await user.type(screen.getByLabelText("اسم الدخول"), "ali@example.sa")
    await user.type(screen.getByLabelText("كلمة المرور"), "wrong")
    await user.click(screen.getByRole("button", { name: "ادخل" }))
    expect(await screen.findByText("بيانات الدخول غير صحيحة.")).toBeTruthy()
    expect(onSignedIn).not.toHaveBeenCalled()
  })

  it("says so when the network is down", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"))
    const { user } = setup()
    await user.type(screen.getByLabelText("اسم الدخول"), "ali@example.sa")
    await user.type(screen.getByLabelText("كلمة المرور"), "x")
    await user.click(screen.getByRole("button", { name: "ادخل" }))
    expect(await screen.findByText("تعذّر الاتصال. تحقّق من الشبكة وحاول مرة أخرى.")).toBeTruthy()
  })

  it("sends nothing while a field is empty", async () => {
    const fetch = respond(204)
    const { user } = setup()
    await user.type(screen.getByLabelText("اسم الدخول"), "ali@example.sa")
    await user.click(screen.getByRole("button", { name: "ادخل" }))
    expect(screen.getByRole("alert").textContent).toContain("اكتب اسم الدخول وكلمة المرور.")
    expect(fetch).not.toHaveBeenCalled()
  })

  it("reveals the password with its own labelled button", async () => {
    const { user } = setup()
    const field = screen.getByLabelText("كلمة المرور") as HTMLInputElement
    expect(field.type).toBe("password")
    expect(field.autocomplete).toBe("current-password")
    const reveal = screen.getByRole("button", { name: "أظهر" })
    await user.click(reveal)
    expect(field.type).toBe("text")
    expect(screen.getByRole("button", { name: "أخفِ" }).getAttribute("aria-pressed")).toBe("true")
  })

  it("starts the step-by-step sign-up instead of a long form", async () => {
    const fetch = respond(204)
    const { onStartSignup, user } = setup()
    await user.click(screen.getByRole("button", { name: "حساب جديد" }))
    expect(screen.queryByLabelText("كلمة المرور")).toBeNull()
    await user.click(screen.getByRole("button", { name: "ابدأ التسجيل" }))
    expect(onStartSignup).toHaveBeenCalledOnce()
    expect(fetch).not.toHaveBeenCalled()
  })

  it("offers no email recovery, phone or remember-me: the app sends no email and stores nothing", () => {
    setup()
    expect(screen.queryByText(/نسيت|تذكّرني|الهاتف/)).toBeNull()
    expect(document.querySelector("input[type=checkbox], input[type=tel]")).toBeNull()
  })
})

describe("password strength", () => {
  it("measures the one rule the server enforces, in characters", () => {
    expect(passwordStrength("a".repeat(11)).enough).toBe(false)
    expect(passwordStrength("a".repeat(12)).enough).toBe(true)
    // اثنا عشر حرفاً خارج BMP: الخادم يعدّها 12 لا 24.
    expect(passwordStrength("😀".repeat(12)).length).toBe(12)
    expect(passwordStrength("a".repeat(257)).tooLong).toBe(true)
  })

  it("says how far it is in words, not colour alone", () => {
    render(<PasswordStrengthIndicator password="abcdef" />)
    expect(screen.getByText("6 من 12 حرفاً على الأقل.")).toBeTruthy()
  })
})
