/*
 * مفاتيح المرور — منقولةٌ من portal.js كما هي. الخيارات (وفيها التحدّي) تُجلب حين
 * تُعرض الشاشة لا داخل الضغطة: WebKit يشترط تفعيلاً من المستخدم، ومهلته قصيرة.
 * والتحدّي لمرةٍ واحدة: بعد كل محاولةٍ — نجحت أو فشلت — تُجلب خياراتٌ جديدة.
 */
import { api, detail } from "./api"
import { getState, setState, showAlert } from "./store"

type Kind = "login" | "add"

const OPTIONS: Record<Kind, string> = { login: "/api/auth/passkey/options", add: "/api/me/passkeys/options" }
export const PASSKEY_NOT_READY = "لم يجهز مفتاح المرور بعد. حاول مرة أخرى."
export const PASSKEY_NOT_SIGNED_IN =
  "لم يكتمل الدخول بمفتاح المرور. إن لم يُضَف لحسابك مفتاحٌ بعد، فادخل بكلمة المرور، ثم أضفه من «حسابي»."
export const PASSKEY_NOT_SAVED =
  "لم يُحفظ مفتاح المرور. يحتاج سلسلة مفاتيح iCloud والمصادقة بخطوتين مفعّلتين، ثم تأكيداً بـFace ID أو Touch ID أو رمز الجهاز."
export const PASSKEY_ALREADY_HERE = "في هذا الجهاز مفتاح مرورٍ لهذا الحساب من قبل."
export const PASSKEY_SAVED = "حُفظ مفتاح المرور. ادخل به في المرة القادمة من شاشة الدخول."

interface Ticket {
  options: PublicKeyCredentialRequestOptions | PublicKeyCredentialCreationOptions | null
  error: string | null
}

const tickets: Record<Kind, Ticket | null> = { login: null, add: null }

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

type Json = Record<string, unknown>

/* خيارات الخادم بالشكل الذي يقبله المتصفّح: التحدّي والمعرّفات بايتات. */
function publicKeyOptions(json: Json) {
  const options: Json = { ...json, challenge: fromBase64url(json.challenge as string) }
  const user = json.user as Json | undefined
  if (user) options.user = { ...user, id: fromBase64url(user.id as string) }
  for (const key of ["allowCredentials", "excludeCredentials"]) {
    const list = json[key] as Json[] | undefined
    if (list) options[key] = list.map((credential) => ({ ...credential, id: fromBase64url(credential.id as string) }))
  }
  return options as unknown as Ticket["options"]
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

/* يجلب خياراتٍ جديدة؛ ما يصل لطلبٍ أقدم يُترك. */
export function preparePasskey(kind: Kind) {
  if (!passkeysAvailable()) {
    tickets[kind] = null
    return
  }
  const ticket: Ticket = { options: null, error: null }
  tickets[kind] = ticket
  api<Json>("POST", OPTIONS[kind]).then((result) => {
    if (result.status === 200 && result.data) ticket.options = publicKeyOptions(result.data)
    else ticket.error = detail(result)
  })
}

/* خيارات الضغطة لمرةٍ واحدة؛ وإن لم تصل بعد يُقال ذلك، فلا ضغطةٌ بلا أثر. */
function take(kind: Kind, screen: string) {
  const ticket = tickets[kind]
  const { busy, alert } = getState()
  if (!ticket || busy || alert) return null
  if (!ticket.options) {
    showAlert(screen, ticket.error || PASSKEY_NOT_READY)
    if (ticket.error) preparePasskey(kind)
    return null
  }
  tickets[kind] = null
  return ticket.options
}

export async function passkeyLogin() {
  const options = take("login", "login")
  if (!options) return
  setState({ busy: true })
  const credential = (await navigator.credentials
    .get({ publicKey: options as PublicKeyCredentialRequestOptions })
    .catch(() => null)) as PublicKeyCredential | null
  const result = credential ? await api("POST", "/api/auth/passkey", { json: assertionJson(credential) }) : null
  setState({ busy: false })
  if (result && result.status === 204) {
    location.replace("/")
    return
  }
  preparePasskey("login")
  showAlert("login", result ? detail(result) : PASSKEY_NOT_SIGNED_IN)
}

/* يعيد نصّ الحالة عند النجاح؛ والفشل تنبيهٌ على شاشة الحساب. */
export async function passkeyAdd(): Promise<string | null> {
  const options = take("add", "account")
  if (!options) return null
  setState({ busy: true })
  let failure = PASSKEY_NOT_SAVED
  const credential = (await navigator.credentials
    .create({ publicKey: options as PublicKeyCredentialCreationOptions })
    .catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "InvalidStateError") failure = PASSKEY_ALREADY_HERE
      return null
    })) as PublicKeyCredential | null
  const result = credential ? await api("POST", "/api/me/passkeys", { json: attestationJson(credential) }) : null
  setState({ busy: false })
  if (result && result.status === 401) return null
  preparePasskey("add")
  if (result && result.status === 204) return PASSKEY_SAVED
  showAlert("account", result ? detail(result) : failure)
  return null
}
