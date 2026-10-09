/*
 * الطلبات إلى خادم eyework
 * ========================
 * كما في static/app.js: كل طلبٍ يغيّر شيئاً يحمل `X-Eyework: 1` (والمتصفّح يرسل
 * `Origin` من نفسه)، والجلسة ملفّ تعريفٍ من الأصل نفسه، ولا تخزين مؤقّت. وما يردّه
 * الخادم من رسالةٍ يُعرض كما هو: هو مصدر الكلمة لا الواجهة.
 */

export const OFFLINE = "تعذّر الاتصال. تحقّق من الشبكة وحاول مرة أخرى."
export const GENERIC = "حدث خطأ. حاول مرة أخرى."

export interface ApiResult<T = unknown> {
  status: number
  data: T | null
}

export interface ApiError {
  code?: string
  detail?: string
}

export async function api<T = unknown>(method: "GET" | "POST", path: string, json?: unknown): Promise<ApiResult<T>> {
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
  if (response.status === 204) {
    return { status: 204, data: null }
  }
  try {
    return { status: response.status, data: (await response.json()) as T }
  } catch {
    return { status: response.status, data: null }
  }
}

/** رسالة الخادم إن وُجدت، وإلا الرسالة العامة. */
export function detail(result: ApiResult): string {
  const data = result.data as ApiError | null
  return (data && typeof data.detail === "string" && data.detail) || GENERIC
}
