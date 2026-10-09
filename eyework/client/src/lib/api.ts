/*
 * الطلبات إلى خادم eyework
 * ========================
 * كما في static/app.js: موضعٌ واحد. كل طلبٍ يحمل `X-Eyework: 1` (والمتصفّح يرسل `Origin`
 * من نفسه)، والجلسة ملفّ تعريفٍ من الأصل نفسه، ولا تخزين مؤقّت، ولا مهلة في الواجهة: الطلب
 * ينتهي بردّ الخادم أو بانقطاع الشبكة، والمستخدم يعيد بضغطة. وما يردّه الخادم من رسالةٍ
 * يُعرض كما هو: هو مصدر الكلمة لا الواجهة.
 *
 * 401 خارج /api/auth/ يعني انتهاء الجلسة: إلى شاشة الدخول. و403 برمز PROFESSION يعني أن
 * المهنة تغيّرت عند الخادم: ما حُفظ عن صاحب الجلسة لم يعد صحيحاً.
 */

import { go } from "./router"
import { setState } from "./store"

export const OFFLINE = "تعذّر الاتصال. تحقّق من الشبكة وحاول مرة أخرى."
export const GENERIC = "حدث خطأ. حاول مرة أخرى."

export type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"

export interface ApiResult<T = unknown> {
  status: number
  data: T | null
}

export interface ApiError {
  code?: string
  detail?: string
  field?: string
}

export interface ApiOptions {
  json?: unknown
  /** جسمٌ خام (صورة) بنوعه. */
  raw?: BodyInit
  type?: string
  /** الردّ ملفٌّ (صورة) لا JSON. */
  as?: "json" | "blob"
  /** 401 جوابٌ متوقَّع (سؤال الإقلاع «هل من جلسة؟»): لا انتقال إلى شاشة الدخول. */
  quiet?: boolean
}

export async function api<T = unknown>(method: Method, path: string, options: ApiOptions = {}): Promise<ApiResult<T>> {
  const headers: Record<string, string> = { "X-Eyework": "1" }
  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(options.json)
  } else if (options.raw !== undefined) {
    headers["Content-Type"] = options.type ?? "application/octet-stream"
    body = options.raw
  }
  let response: Response
  try {
    response = await fetch(path, { method, headers, body, credentials: "same-origin", cache: "no-store" })
  } catch {
    return { status: 0, data: { detail: OFFLINE } as T }
  }
  if (response.status === 401 && !path.startsWith("/api/auth/") && !options.quiet) {
    setState({ me: null })
    go("#/login")
    return { status: 401, data: null }
  }
  let data: T | null = null
  if (response.status !== 204) {
    try {
      data = (options.as === "blob" && response.ok ? await response.blob() : await response.json()) as T
    } catch {
      data = null
    }
  }
  if (response.status === 403 && data && (data as ApiError).code === "PROFESSION") {
    setState({ me: null })
  }
  return { status: response.status, data }
}

/** رسالة الخادم إن وُجدت، وإلا الرسالة العامة. */
export function detail(result: ApiResult): string {
  const data = result.data as ApiError | null
  return (data && typeof data.detail === "string" && data.detail) || GENERIC
}

export function errorCode(result: ApiResult): string | null {
  const data = result.data as ApiError | null
  return (data && typeof data.code === "string" && data.code) || null
}

export function errorField(result: ApiResult): string | null {
  const data = result.data as ApiError | null
  return (data && typeof data.field === "string" && data.field) || null
}
