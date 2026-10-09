/*
 * الشبكة: موضعٌ واحد، كما `api()` في app.js. كل طلبٍ إلى الأصل نفسه بترويسة
 * X-Eyework، وبلا ذاكرة، وبملفّ الجلسة. 401 خارج /api/auth/ يعني انتهاء الجلسة:
 * إلى شاشة الدخول.
 */
import { go } from "./router"
import { setState } from "./store"

export const OFFLINE = "تعذّر الاتصال. تحقّق من الشبكة وحاول مرة أخرى."
export const GENERIC = "حدث خطأ. حاول مرة أخرى."

export interface Result<T = unknown> {
  status: number
  data: T | null
}

export async function api<T = unknown>(
  method: string,
  path: string,
  { json }: { json?: unknown } = {},
): Promise<Result<T>> {
  const headers: Record<string, string> = { "X-Eyework": "1" }
  let body: string | undefined
  if (json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(json)
  }
  let response: Response
  try {
    response = await fetch(path, { method, headers, body, credentials: "same-origin", cache: "no-store" })
  } catch {
    return { status: 0, data: { detail: OFFLINE } as T }
  }
  if (response.status === 401 && !path.startsWith("/api/auth/")) {
    setState({ portal: null })
    go("#/login")
    return { status: 401, data: null }
  }
  let data: T | null = null
  if (response.status !== 204) {
    try {
      data = (await response.json()) as T
    } catch {
      data = null
    }
  }
  return { status: response.status, data }
}

export function detail(result: Result): string {
  const data = result.data as { detail?: string } | null
  return (data && data.detail) || GENERIC
}
