import { act, fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { setViewportWidth } from "./setup"
import { SidebarDemo } from "./sidebar-demo"

/** حالة الغلاف الذي يحمل `data-state` على سطح المكتب. */
const desktopState = (container: HTMLElement) =>
  container.querySelector<HTMLElement>("[data-state][data-side]")?.dataset.state

describe("المكوّن كما ورد، بعرضه التوضيحي", () => {
  afterEach(() => vi.restoreAllMocks())

  it("يرسم بنود القائمة الخمسة وتذييل المستخدم", () => {
    render(<SidebarDemo />)
    for (const title of ["Home", "Inbox", "Calendar", "Search", "Settings"]) {
      expect(screen.getByRole("link", { name: title })).toBeTruthy()
    }
    expect(screen.getByText("john@example.com")).toBeTruthy()
  })

  it("زرّ الإظهار يطوي الشريط ويفتحه ويحفظ الحالة في ملفّ ارتباط", async () => {
    const user = userEvent.setup()
    const { container } = render(<SidebarDemo />)
    expect(desktopState(container)).toBe("expanded")

    await user.click(screen.getByRole("button", { name: "Toggle Sidebar" }))
    expect(desktopState(container)).toBe("collapsed")
    expect(document.cookie).toContain("sidebar_state=false")

    await user.click(screen.getByRole("button", { name: "Toggle Sidebar" }))
    expect(desktopState(container)).toBe("expanded")
  })

  it("Ctrl+B يطوي الشريط من أيّ مكان", () => {
    const { container } = render(<SidebarDemo />)
    act(() => {
      fireEvent.keyDown(window, { key: "b", ctrlKey: true })
    })
    expect(desktopState(container)).toBe("collapsed")
  })

  it("على الهاتف يصير نافذةً مسمّاة تُفتح بالزرّ", async () => {
    setViewportWidth(390)
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined)
    const user = userEvent.setup()
    render(<SidebarDemo />)
    expect(screen.queryByRole("link", { name: "Home" })).toBeNull()

    await user.click(screen.getByRole("button", { name: "Toggle Sidebar" }))
    const dialog = screen.getByRole("dialog")
    expect(within(dialog).getByRole("link", { name: "Home" })).toBeTruthy()
    // نافذةٌ بلا عنوان يعلنها قارئ الشاشة «حوار» فقط، وRadix يعدّها خطأً.
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy()
    const titleId = dialog.getAttribute("aria-labelledby")!
    expect(document.getElementById(titleId)?.textContent?.trim()).toBeTruthy()
    expect(errors.mock.calls.flat().join(" ")).not.toMatch(/DialogTitle/)
  })
})
