import type { Citation, Proposal, RedFlag, Session } from "@/lib/types"

/**
 * عميل بوابة الممارس
 * ==================
 * الطلبات كلها إلى `/practitioner` من الأصل نفسه، بترويسة `Authorization`.
 * الرمز يُحفظ في `sessionStorage`: يبقى مع إعادة تحميل التبويب، ويزول بإغلاقه،
 * ولا يُرسل تلقائياً مع أيّ طلبٍ كما يُرسل ملفّ الارتباط.
 *
 * رسالة الخطأ هي رسالة الخادم حين تكون نصّاً؛ الخادم يكتبها بالعربية ويختار
 * ما يُقال (لا تفاصيل تساعد مهاجماً). وأخطاء التحقّق — مصفوفة لا نصّ — تُعرض
 * برسالةٍ عامة واحدة، فلا تصل الواجهةَ قيمٌ أرسلها المستخدم.
 */

const BASE = "/practitioner"
const TOKEN_KEY = "symbol.practitioner.session"

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

const FALLBACK: Record<number, string> = {
  401: "انتهت الجلسة. سجّل الدخول من جديد.",
  403: "لا تملك صلاحية هذا الإجراء.",
  404: "العنصر غير موجود.",
  409: "حالة العنصر لا تسمح بذلك.",
  422: "قيمةٌ غير صالحة في الطلب.",
  429: "محاولات كثيرة. أعد المحاولة بعد قليل.",
}

const UNREACHABLE = "تعذّر الوصول إلى الخادم. تحقّق من الاتصال ثم أعد المحاولة."
const SERVER_FAILED = "حدث خطأ في الخادم. أعد المحاولة."

async function failure(response: Response): Promise<ApiError> {
  let detail: unknown
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail
  } catch {
    detail = undefined
  }
  const message =
    typeof detail === "string" && detail.trim()
      ? detail
      : FALLBACK[response.status] ?? SERVER_FAILED
  return new ApiError(response.status, message)
}

async function send<T>(
  path: string,
  init: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" }
  if (init.token) headers.Authorization = `Bearer ${init.token}`
  if (init.body !== undefined) headers["Content-Type"] = "application/json"

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      credentials: "omit",
      cache: "no-store",
    })
  } catch {
    throw new ApiError(0, UNREACHABLE)
  }
  if (!response.ok) throw await failure(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// ── الجلسة ─────────────────────────────────────────────────────────────

export function loadSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(TOKEN_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<Session>
    return typeof parsed.token === "string" && typeof parsed.role === "string"
      ? { token: parsed.token, role: parsed.role }
      : null
  } catch {
    return null
  }
}

function storeSession(session: Session | null): void {
  try {
    if (session) window.sessionStorage.setItem(TOKEN_KEY, JSON.stringify(session))
    else window.sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // تخزينٌ معطّل (تصفّح خاص مثلاً): الجلسة تبقى في الذاكرة لهذا التحميل وحده.
  }
}

export async function login(email: string, password: string): Promise<Session> {
  const session = await send<Session>("/login", { method: "POST", body: { email, password } })
  storeSession(session)
  return session
}

export function forgetSession(): void {
  storeSession(null)
}

// ── الإجراءات ──────────────────────────────────────────────────────────

export interface PractitionerApi {
  queue(): Promise<Proposal[]>
  proposal(id: string): Promise<Proposal>
  citations(id: string): Promise<Citation[]>
  approve(id: string): Promise<Proposal>
  reject(id: string, reason: string): Promise<Proposal>
  redFlags(): Promise<RedFlag[]>
  acknowledge(id: string, note: string | null): Promise<RedFlag>
  logout(): Promise<void>
}

/**
 * عميلٌ مرتبط بجلسة. `onExpired` يُستدعى عند أول 401: الجلسة انتهت أو أُلغيت،
 * فلا معنى لإبقاء الواجهة كأنها داخلة.
 *
 * والجلسة تنتهي لهذا العميل مرةً واحدة، بـ401 أو بخروجٍ مقصود. طلبٌ أُرسل قبلها
 * ويعود بـ401 بعدها لا يمسّ شيئاً: لو مسّ لمحا رمز جلسةٍ دخل بها الممارس بعدها
 * وأعاده إلى شاشة الدخول، أو حوّل خروجه المقصود إلى «انتهت الجلسة».
 */
export function practitionerApi(session: Session, onExpired: () => void): PractitionerApi {
  let ended = false

  async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    try {
      return await send<T>(path, { method, body, token: session.token })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401 && !ended) {
        ended = true
        forgetSession()
        onExpired()
      }
      throw error
    }
  }

  const id = (value: string) => encodeURIComponent(value)

  return {
    queue: () => call<Proposal[]>("/queue"),
    proposal: (value) => call<Proposal>(`/proposals/${id(value)}`),
    citations: (value) => call<Citation[]>(`/proposals/${id(value)}/citations`),
    approve: (value) => call<Proposal>(`/proposals/${id(value)}/approve`, "POST"),
    reject: (value, reason) => call<Proposal>(`/proposals/${id(value)}/reject`, "POST", { reason }),
    redFlags: () => call<RedFlag[]>("/red-flags"),
    acknowledge: (value, note) =>
      call<RedFlag>(`/red-flags/${id(value)}/acknowledge`, "POST", { note }),
    logout: async () => {
      ended = true
      try {
        await call<void>("/logout", "POST")
      } finally {
        forgetSession()
      }
    },
  }
}
