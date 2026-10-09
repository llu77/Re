/*
 * هيكل البوابة في jsdom: شريط التبويب في الهاتف، والشريط الجانبي من 744px، وسكّة الحجم الكبير.
 * المعرّفات والمسارات هي التي تقرؤها اختبارات Chromium (test_shell.py)؛ هنا تُثبَّت بلا متصفّح.
 */

import { render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { AppProviders } from "@/app/providers"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import { WORKSPACES } from "@/lib/workspace"

const NAV = ["nav-home", "nav-sections", "nav-tools", "nav-account"]

/** استعلامات الوسائط بعرض الإطار: `(min-width: …rem)` وحدها تصدق فوقه. */
function viewport(width: number) {
  window.matchMedia = (query: string): MediaQueryList => {
    const min = /min-width:\s*([\d.]+)rem/.exec(query)
    const matches = min ? width >= parseFloat(min[1]) * 16 : false
    return {
      matches, media: query, onchange: null,
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
    }
  }
}

const tools = { userName: "علي", assistant: { remaining: 3, ask: async () => ({ ok: false as const, message: "" }) }, supportContact: null }

function shell(size: "compact" | "gaze", current: string | null = "home") {
  return render(
    <AppProviders size={size}>
      <WorkspaceShell workspace={WORKSPACES.MARKETING} current={current} userName="علي" onNavigate={() => {}} tools={tools}>
        <p>المحتوى</p>
      </WorkspaceShell>
    </AppProviders>,
  )
}

const ids = (root: HTMLElement) => [...root.querySelectorAll("a, button")].map((e) => e.id)

afterEach(() => {
  document.body.innerHTML = ""
})

describe("the workspace shell", () => {
  it("gives a phone the four tab-bar entries, all safe, and no sidebar", () => {
    viewport(390)
    shell("compact")
    const nav = screen.getByRole("navigation", { name: "أقسام البوابة" })
    expect(ids(nav)).toEqual(NAV)
    expect(within(nav).getByText("الرئيسية").closest("a")?.getAttribute("href")).toBe("#/marketing")
    expect(within(nav).getByText("حسابي").closest("a")?.getAttribute("href")).toBe("#/account")
    expect([...nav.querySelectorAll("a, button")].every((e) => e.hasAttribute("data-safe"))).toBe(true)
    expect(nav.querySelector("#nav-home")?.getAttribute("aria-current")).toBe("page")
    expect(document.querySelector("#sidebar")).toBeNull()
  })

  it("gives a tablet the sidebar with the entries and the two tools, and no tab bar", () => {
    viewport(744)
    shell("compact", "new")
    const sidebar = document.querySelector("#sidebar") as HTMLElement
    expect(ids(sidebar)).toEqual(["nav-home", "nav-entry-new", "nav-entry-campaigns", "nav-assistant", "nav-help", "nav-account"])
    expect(sidebar.querySelector("#nav-entry-new")?.getAttribute("aria-current")).toBe("page")
    expect(sidebar.querySelector("#nav-entry-new")?.getAttribute("href")).toBe("#/marketing/new")
    expect(document.querySelector("#nav-sections")).toBeNull()
    expect(document.querySelectorAll("nav[aria-label='أقسام البوابة']")).toHaveLength(1)
  })

  it("keeps the gaze-size rail to the four entries of the tab bar", () => {
    viewport(1024)
    shell("gaze", null)
    const sidebar = document.querySelector("#sidebar") as HTMLElement
    expect(ids(sidebar)).toEqual(NAV)
    expect(sidebar.querySelector("#nav-account")?.getAttribute("aria-current")).toBe("page")
  })

  it("renders the list pane beside the screen only on a wide touch frame", () => {
    viewport(1280)
    const wide = render(
      <AppProviders size="compact">
        <WorkspaceShell workspace={WORKSPACES.MARKETING} current="campaigns" userName="علي" onNavigate={() => {}} tools={tools} pane={<p>القائمة</p>}>
          <p>الحملة</p>
        </WorkspaceShell>
      </AppProviders>,
    )
    expect(wide.getByText("القائمة")).toBeTruthy()
    wide.unmount()
    const gaze = render(
      <AppProviders size="gaze">
        <WorkspaceShell workspace={WORKSPACES.MARKETING} current="campaigns" userName="علي" onNavigate={() => {}} tools={tools} pane={<p>القائمة</p>}>
          <p>الحملة</p>
        </WorkspaceShell>
      </AppProviders>,
    )
    expect(gaze.queryByText("القائمة")).toBeNull()
  })
})
