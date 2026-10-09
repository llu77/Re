import { describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { BookOpen, UserRound } from "lucide-react"

import { readFileSync } from "node:fs"
import { join } from "node:path"

import { DropdownNavigation, type NavItem } from "@/components/ui/dorpdown-navigation"
import { navItemsFor } from "@/lib/nav"
import { setReducedMotion } from "./setup"

const onSelect = vi.fn()
const ITEMS: NavItem[] = [
  {
    id: 1,
    label: "حسابي",
    subMenus: [
      {
        title: "الحساب",
        items: [
          { label: "المصادر", description: "من أين جاءت المهامّ", icon: BookOpen, href: "#/account/sources" },
          { label: "الاسم", description: "كما يُحيّيك التطبيق", icon: UserRound, onSelect },
        ],
      },
    ],
  },
  { id: 2, label: "عن التطبيق", link: "#/about" },
]

describe("DropdownNavigation", () => {
  it("opens and closes by pressing, never by hovering", async () => {
    setReducedMotion(true)
    const onOpenChange = vi.fn()
    render(<DropdownNavigation navItems={ITEMS} onOpenChange={onOpenChange} />)
    const trigger = screen.getByRole("button", { name: "حسابي" })
    fireEvent.mouseEnter(trigger)
    fireEvent.pointerEnter(trigger)
    fireEvent.mouseOver(trigger)
    expect(screen.queryByRole("region")).toBeNull()
    expect(trigger.getAttribute("aria-expanded")).toBe("false")

    await userEvent.click(trigger)
    expect(trigger.getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByRole("region", { name: "حسابي" })).toBeTruthy()
    expect(onOpenChange).toHaveBeenLastCalledWith(true)

    await userEvent.click(trigger)
    expect(screen.queryByRole("region")).toBeNull()
    expect(onOpenChange).toHaveBeenLastCalledWith(false)
  })

  it("closes when an item is chosen, and runs it", async () => {
    setReducedMotion(true)
    render(<DropdownNavigation navItems={ITEMS} />)
    await userEvent.click(screen.getByRole("button", { name: "حسابي" }))
    await userEvent.click(screen.getByRole("button", { name: /الاسم/ }))
    expect(onSelect).toHaveBeenCalledOnce()
    expect(screen.queryByRole("region")).toBeNull()
  })

  it("closes on Escape, tells the host, and returns focus to its button", async () => {
    setReducedMotion(true)
    const onOpenChange = vi.fn()
    render(<DropdownNavigation navItems={ITEMS} onOpenChange={onOpenChange} />)
    const trigger = screen.getByRole("button", { name: "حسابي" })
    await userEvent.click(trigger)
    // التركيز داخل القائمة أولاً، فلا يمرّ الاختبار لأن التركيز لم يغادر الزرّ.
    screen.getByRole("link", { name: /المصادر/ }).focus()
    expect(document.activeElement).not.toBe(trigger)
    act(() => {
      fireEvent.keyDown(document, { key: "Escape" })
    })
    expect(screen.queryByRole("region")).toBeNull()
    expect(onOpenChange).toHaveBeenLastCalledWith(false)
    expect(document.activeElement).toBe(trigger)
  })

  it("returns focus to the menu's button after an item is chosen", async () => {
    setReducedMotion(true)
    render(<DropdownNavigation navItems={ITEMS} />)
    const trigger = screen.getByRole("button", { name: "حسابي" })
    await userEvent.click(trigger)
    await userEvent.click(screen.getByRole("button", { name: /الاسم/ }))
    expect(document.activeElement).toBe(trigger)
  })

  it("puts an open menu right after its button in the focus order", async () => {
    setReducedMotion(true)
    render(<DropdownNavigation navItems={ITEMS} />)
    const trigger = screen.getByRole("button", { name: "حسابي" })
    await userEvent.click(trigger)
    const panel = screen.getByRole("region", { name: "حسابي" })
    const next = screen.getByRole("link", { name: "عن التطبيق" })
    expect(trigger.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(panel.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("gives every item a label and a description, and a plain link for an item without a menu", async () => {
    setReducedMotion(true)
    render(<DropdownNavigation navItems={ITEMS} />)
    expect(screen.getByRole("link", { name: "عن التطبيق" }).getAttribute("href")).toBe("#/about")
    await userEvent.click(screen.getByRole("button", { name: "حسابي" }))
    const link = screen.getByRole("link", { name: /المصادر/ })
    expect(link.getAttribute("href")).toBe("#/account/sources")
    expect(link.textContent).toContain("من أين جاءت المهامّ")
  })
})

describe("portal navigation", () => {
  it("shows the work tools only to a profession that has one", () => {
    const labels = (tools: string[]) =>
      navItemsFor({ profession: "X", name: "بوابة", tools }).map((item) => item.label)
    expect(labels(["CAMPAIGN"])).toEqual(["بوابتي", "العمل", "حسابي"])
    expect(labels([])).toEqual(["بوابتي", "حسابي"])
  })

  it("signs out through the confirmation screen", () => {
    const account = navItemsFor({ profession: "X", name: "بوابة", tools: [] }).find((item) => item.label === "حسابي")!
    const leaves = account.subMenus!.flatMap((sub) => sub.items)
    expect(leaves.find((leaf) => leaf.label === "تسجيل الخروج")!.href).toBe("/#/account/logout")
  })
})

describe("where the menu items lead", () => {
  const STATIC = join(__dirname, "..", "..", "static")
  const current = ["app.js", "portal.js"].map((name) => readFileSync(join(STATIC, name), "utf8")).join("\n")

  it("leads every item to a route the current app at / handles, from /next/ — a real navigation", () => {
    expect(readFileSync(join(__dirname, "..", "vite.config.ts"), "utf8")).toMatch(/base: "\/next\/"/)
    for (const tools of [["CAMPAIGN"], []]) {
      const leaves = navItemsFor({ profession: "X", name: "بوابة", tools }).flatMap((item) =>
        (item.subMenus ?? []).flatMap((sub) => sub.items),
      )
      for (const leaf of leaves) {
        expect(leaf.href, leaf.label).toMatch(/^\/#\//)
        const hash = leaf.href!.slice(1)
        expect(current.includes(`'${hash}'`), `${leaf.label} → ${hash}`).toBe(true)
      }
    }
  })
})

