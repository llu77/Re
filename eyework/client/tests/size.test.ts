import { describe, expect, it } from "vitest"

import { SHORT_QUERY, TABLET_QUERY, WIDE_QUERY, fromServer, sizeFromUrl, toServer } from "@/lib/size"

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

describe("the media queries", () => {
  it("call a screen short at 480px, a tablet from 744px and wide from 1024px", () => {
    expect(SHORT_QUERY).toBe("(max-height: 30rem)")
    expect(TABLET_QUERY).toBe("(min-width: 46.5rem)")
    expect(WIDE_QUERY).toBe("(min-width: 64rem)")
  })
})
