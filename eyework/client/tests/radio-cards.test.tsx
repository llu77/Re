/*
 * RadioCards والانتقال بالاختيار (طلب المالك 2026-10-11): الضغطة تختار وتنتقل (`onPress`)، والأسهم تختار ولا تنتقل.
 */

import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers"
import { RadioCards } from "@/components/ui/radio-cards"

function cards(size: "compact" | "gaze", onValueChange: (value: string) => void, onPress?: (value: string) => void) {
  return render(
    <AppProviders size={size}>
      <RadioCards<string>
        label="المهن"
        value="A"
        onValueChange={onValueChange}
        onPress={onPress}
        columns={1}
        ids={{ A: "card-a", B: "card-b" }}
        options={[{ value: "A", title: "الأول" }, { value: "B", title: "الثاني" }]}
      />
    </AppProviders>,
  )
}

describe("RadioCards onPress", () => {
  it("chooses and moves on with the same press in both sizes", () => {
    for (const size of ["compact", "gaze"] as const) {
      const change = vi.fn()
      const press = vi.fn()
      const view = cards(size, change, press)
      fireEvent.click(screen.getByText("الثاني"))
      expect(change).toHaveBeenCalledWith("B")
      expect(press).toHaveBeenCalledWith("B")
      view.unmount()
    }
  })

  it("lets the arrow keys choose without moving on", () => {
    const change = vi.fn()
    const press = vi.fn()
    const view = cards("compact", change, press)
    fireEvent.keyDown(document.querySelector("#card-a") as HTMLElement, { key: "ArrowDown" })
    expect(change).toHaveBeenCalledWith("B")
    expect(press).not.toHaveBeenCalled()
    view.unmount()
  })

  it("only chooses when no step follows", () => {
    const change = vi.fn()
    const view = cards("compact", change)
    fireEvent.click(screen.getByText("الثاني"))
    expect(change).toHaveBeenCalledWith("B")
    view.unmount()
  })
})
