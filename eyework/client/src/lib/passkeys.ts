/*
 * مفاتيح المرور — منقولةٌ من static/portal.js كما هي
 * ================================================
 * «ادخل بمفتاح المرور» زرّ دخولٍ وحده (قرار المالك): الخيارات (وفيها التحدّي) تُجلب
 * حين تُعرض شاشة الدخول لا داخل الضغطة — WebKit يشترط تفعيلاً من المستخدم ومهلته قصيرة —
 * وتُجدَّد بعد كل محاولةٍ وبعد أربع دقائق وعند العودة إلى الصفحة. ولا زرّ لإضافة مفتاح:
 * بعد الدخول بكلمة المرور يحاول المتصفّح حفظ مفتاحٍ بالإنشاء الشرطي حيث يدعمه، بلا
 * شاشةٍ ولا سؤال.
 */

import { api, detail } from "./api"
import { reload } from "./router"
import { getState, setState } from "./store"

const OPTIONS = "/api/auth/passkey/options"
const OPTIONS_MAX_AGE_MS = 4 * 60 * 1000
export const PASSKEY_NOT_READY = "لم يجهز مفتاح المرور بعد. حاول مرة أخرى."
export const PASSKEY_NOT_SIGNED_IN = "لم يكتمل الدخول بمفتاح المرور. ادخل بكلمة المرور؛ يحفظ المتصفّح مفتاحاً بعدها حيث يدعم ذلك."

interface Ticket {
  options: PublicKeyCredentialRequestOptions | null
  error: string | null
  fetchedAt: number
}

let ticket: Ticket | null = null

type Json = Record<string, unknown>

export function passkeysAvailable(): boolean {
  return Boolean(window.PublicKeyCredential && navigator.credentials)
}

function fromBase64url(text: string): Uint8Array {
  const base64 = text.replace(/-/g, "+").replace(/_/g, "/")
  const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4))
  return Uint8Array.from(binary, (c) => c.charCodeAt(0))
}

function toBase64url(buffer: ArrayBuffer): string {
  let binary = ""
  new Uint8Array(buffer).forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

/** خيارات الخادم بالشكل الذي يقبله المتصفّح: التحدّي والمعرّفات بايتات. */
function publicKeyOptions(json: Json): Json {
  const options: Json = { ...json, challenge: fromBase64url(json.challenge as string) }
  const user = json.user as Json | undefined
  if (user) options.user = { ...user, id: fromBase64url(user.id as string) }
  for (const key of ["allowCredentials", "excludeCredentials"]) {
    const list = json[key] as Json[] | undefined
    if (list) options[key] = list.map((credential) => ({ ...credential, id: fromBase64url(credential.id as string) }))
  }
  return options
}

function credentialJson(credential: PublicKeyCredential, response: Json): Json {
  const json: Json = { id: credential.id, rawId: toBase64url(credential.rawId), type: credential.type, response }
  if (credential.authenticatorAttachment) json.authenticatorAttachment = credential.authenticatorAttachment
  return json
}

function assertionJson(credential: PublicKeyCredential): Json {
  const r = credential.response as AuthenticatorAssertionResponse
  const response: Json = {
    clientDataJSON: toBase64url(r.clientDataJSON),
    authenticatorData: toBase64url(r.authenticatorData),
    signature: toBase64url(r.signature),
  }
  if (r.userHandle) response.userHandle = toBase64url(r.userHandle)
  return credentialJson(credential, response)
}

function attestationJson(credential: PublicKeyCredential): Json {
  const r = credential.response as AuthenticatorAttestationResponse
  return credentialJson(credential, {
    clientDataJSON: toBase64url(r.clientDataJSON),
    attestationObject: toBase64url(r.attestationObject),
    transports: typeof r.getTransports === "function" ? r.getTransports() : [],
  })
}

/** يجلب خياراتٍ جديدة؛ ما يصل لطلبٍ أقدم يُترك. */
export function preparePasskey() {
  if (!passkeysAvailable()) {
    ticket = null
    return
  }
  const fresh: Ticket = { options: null, error: null, fetchedAt: Date.now() }
  ticket = fresh
  void api<Json>("POST", OPTIONS).then((result) => {
    if (result.status === 200 && result.data) fresh.options = publicKeyOptions(result.data) as unknown as PublicKeyCredentialRequestOptions
    else fresh.error = detail(result)
  })
}

/** عودةٌ إلى الصفحة (pageshow أو visibilitychange) وشاشة الدخول ظاهرة: التحدّي قد يكون انتهى. */
export function refreshPasskeyOnReturn(loginShown: boolean) {
  if (passkeysAvailable() && !getState().busy && loginShown) preparePasskey()
}

/** خيارات الضغطة لمرةٍ واحدة؛ وإن لم تصل بعد أو قدُمت يُقال ذلك، فلا ضغطةٌ بلا أثر. */
function takeOptions(): { options: PublicKeyCredentialRequestOptions | null; message: string | null } {
  const current = ticket
  if (!current) return { options: null, message: PASSKEY_NOT_READY }
  if (current.error) {
    preparePasskey()
    return { options: null, message: current.error }
  }
  if (!current.options) return { options: null, message: PASSKEY_NOT_READY }
  if (Date.now() - current.fetchedAt > OPTIONS_MAX_AGE_MS) {
    preparePasskey()
    return { options: null, message: PASSKEY_NOT_READY }
  }
  ticket = null
  return { options: current.options, message: null }
}

/** يُرجع رسالة الفشل، أو ينتقل انتقالاً كاملاً عند النجاح. */
export async function passkeyLogin(): Promise<string | null> {
  if (getState().busy) return null
  const taken = takeOptions()
  if (!taken.options) return taken.message
  setState({ busy: true })
  const credential = (await navigator.credentials.get({ publicKey: taken.options }).catch(() => null)) as PublicKeyCredential | null
  const result = credential ? await api("POST", "/api/auth/passkey", { json: assertionJson(credential) }) : null
  setState({ busy: false })
  if (result && result.status === 204) {
    reload()
    return null
  }
  preparePasskey()
  return result ? detail(result) : PASSKEY_NOT_SIGNED_IN
}

async function conditionalCreateAvailable(): Promise<boolean> {
  const key = window.PublicKeyCredential as unknown as { getClientCapabilities?: () => Promise<Record<string, boolean>> } | undefined
  if (!key || typeof key.getClientCapabilities !== "function") return false
  try {
    const capabilities = await key.getClientCapabilities()
    return Boolean(capabilities.conditionalCreate)
  } catch {
    return false
  }
}

/** بعد دخولٍ بكلمة المرور: المتصفّح يحفظ مفتاحاً بالإنشاء الشرطي حيث يدعمه، وإلا لا شيء. */
export async function upgradeToPasskey(username: string): Promise<void> {
  if (!passkeysAvailable() || !(await conditionalCreateAvailable())) return
  const result = await api<Json>("POST", "/api/me/passkeys/options", { json: { username } })
  if (result.status !== 200 || !result.data) return
  const credential = (await navigator.credentials
    .create({ publicKey: publicKeyOptions(result.data) as unknown as PublicKeyCredentialCreationOptions, mediation: "conditional" } as CredentialCreationOptions)
    .catch(() => null)) as PublicKeyCredential | null
  if (credential) await api("POST", "/api/me/passkeys", { json: attestationJson(credential) })
}
