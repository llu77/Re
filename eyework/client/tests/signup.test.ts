/*
 * التسجيل: الفحص كما يفحصه الخادم، وترتيب الشاشات.
 */
import { describe, expect, it } from "vitest"

import {
  FIELD_SCREENS, SCREEN_ORDER, birthDate, birthInFuture, birthWords, daysIn, dropImpossibleDay, emailIsValid, firstMissing,
  nameIsValid, newSignup, normalizeEmail, normalizeName, parentRoute, screenFromRoute, screenRoute, stepNumber,
} from "@/lib/signup"

describe("the name and the email", () => {
  it("normalizes like auth.check_name and auth.normalize_login", () => {
    expect(normalizeName("  سارة   العتيبي ")).toBe("سارة العتيبي")
    expect(normalizeName("علی کریم")).toBe("علي كريم")
    expect(normalizeEmail(" Sara.Worker@Example.SA ")).toBe("sara.worker@example.sa")
    expect(normalizeEmail("straße@example.de")).toBe("strasse@example.de")
  })

  it("accepts letters only, up to the server's limit", () => {
    expect(nameIsValid("سارة العتيبي", 30)).toBe(true)
    expect(nameIsValid("Sara", 30)).toBe(true)
    expect(nameIsValid("سارة 2", 30)).toBe(false)
    expect(nameIsValid("", 30)).toBe(false)
    expect(nameIsValid("س".repeat(31), 30)).toBe(false)
  })

  it("accepts a latin email only", () => {
    expect(emailIsValid("sara.worker@example.sa")).toBe(true)
    expect(emailIsValid("not-an-email")).toBe(false)
    expect(emailIsValid("سارة@example.sa")).toBe(false)
  })
})

describe("the birth date", () => {
  it("knows the month's days and drops an impossible day", () => {
    expect(daysIn(2024, 2)).toBe(29)
    expect(daysIn(2023, 2)).toBe(28)
    const s = { ...newSignup(null), year: 2023, month: 2, day: 31 }
    expect(dropImpossibleDay(s).day).toBeNull()
    expect(dropImpossibleDay({ ...s, day: 28 }).day).toBe(28)
  })

  it("formats what the server reads and what the user sees", () => {
    const s = { ...newSignup(null), year: 1991, month: 3, day: 21 }
    expect(birthDate(s)).toBe("1991-03-21")
    expect(birthWords(s)).toBe("21 مارس 1991")
    expect(birthInFuture(s, new Date(2026, 9, 9))).toBe(false)
    expect(birthInFuture({ ...s, year: 2027 }, new Date(2026, 9, 9))).toBe(true)
  })
})

describe("the screens", () => {
  it("opens no screen before the ones it needs", () => {
    const s = newSignup(null)
    expect(firstMissing(s, 30)).toBe("sent")
    expect(firstMissing({ ...s, agreed: true }, 30)).toBe("use")
    expect(firstMissing({ ...s, agreed: true, use: "compact" }, 30)).toBe("name")
    const filled = { ...s, agreed: true, use: "gaze" as const, name: "سارة", year: 1991, month: 3, day: 21, profession: "MARKETING", email: "s@example.sa" }
    expect(firstMissing(filled, 30)).toBeNull()
    expect(firstMissing({ ...filled, email: "bad" }, 30)).toBe("email")
  })

  it("maps routes, parents and step numbers", () => {
    expect(screenRoute("kept")).toBe("#/signup")
    expect(screenRoute("name")).toBe("#/signup/name")
    expect(screenFromRoute("#/signup")).toBe("kept")
    expect(screenFromRoute("#/signup/day")).toBe("day")
    expect(screenFromRoute("#/signup/nothing")).toBe("kept")
    expect(parentRoute("kept")).toBe("#/login")
    expect(parentRoute("sent")).toBe("#/signup")
    expect(parentRoute("name")).toBe("#/signup/use")
    expect(stepNumber("use")).toBe(1)
    expect(stepNumber("password")).toBe(9)
    expect(SCREEN_ORDER).toHaveLength(11)
    expect(FIELD_SCREENS.TAKEN).toBe("email")
  })
})
