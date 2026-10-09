import { describe, expect, it } from "vitest"

import { fromServer, sizeFromUrl, toServer } from "@/lib/size"

describe("the size", () => {
  it("maps the server's value and never guesses for null", () => {
    expect(toServer("gaze")).toBe("GAZE")
    expect(toServer("compact")).toBe("COMPACT")
    expect(fromServer("GAZE")).toBe("gaze")
    expect(fromServer("COMPACT")).toBe("compact")
    expect(fromServer(null)).toBeNull()
  })

  it("reads the large size from the address without naming the eyes", () => {
    expect(sizeFromUrl("?size=large")).toBe("gaze")
    expect(sizeFromUrl("?size=gaze")).toBeNull()
    expect(sizeFromUrl("")).toBeNull()
  })
})
