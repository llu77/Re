import { act, fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { Sidebar, SidebarProvider, SidebarRail, SidebarTrigger } from "@/components/ui/sidebar"

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

  it("زرّ الإظهار يطوي الشريط ويفتحه ويعلن حالته، ولا يكتب ملفّ ارتباط", async () => {
    const user = userEvent.setup()
    const { container } = render(<SidebarDemo />)
    const trigger = screen.getByRole("button", { name: "Toggle Sidebar" })
    expect(desktopState(container)).toBe("expanded")
    expect(trigger.getAttribute("aria-expanded")).toBe("true")

    await user.click(trigger)
    expect(desktopState(container)).toBe("collapsed")
    expect(trigger.getAttribute("aria-expanded")).toBe("false")
    // كان يُحفظ أسبوعاً على الأصل كلّه، فيُرسَل مع طلبات بوابة المريض.
    expect(document.cookie).not.toContain("sidebar_state")

    await user.click(trigger)
    expect(desktopState(container)).toBe("expanded")
  })

  it("Ctrl+B داخل حقل كتابةٍ لا يطوي الشريط", () => {
    const { container } = render(
      <>
        <SidebarDemo />
        <textarea aria-label="سبب" />
      </>,
    )
    const field = screen.getByLabelText("سبب")
    field.focus()
    act(() => {
      fireEvent.keyDown(field, { key: "b", ctrlKey: true })
    })
    expect(desktopState(container)).toBe("expanded")
  })

  it("حافة الشريط للفأرة وحدها: لا تُعلَن زرّاً ثانياً بالاسم نفسه", () => {
    const { container } = render(
      <SidebarProvider>
        <Sidebar>
          <SidebarRail />
        </Sidebar>
        <SidebarTrigger />
      </SidebarProvider>,
    )
    expect(container.querySelector("[data-sidebar=rail]")).toBeTruthy()
    expect(screen.getAllByRole("button", { name: "Toggle Sidebar" })).toHaveLength(1)
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
