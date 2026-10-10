/*
 * حالة التطبيق
 * ============
 * `state` في static/app.js نفسها، في مخزنٍ يقرؤه React بـuseSyncExternalStore. الخادم مصدر
 * كل قيمة: الخيارات من /api/choices، وصاحب الجلسة من /api/me، ولا يُحفظ في الجهاز شيء.
 * و`nav` يزيد مع كل انتقال فلا يرسم ردٌّ متأخّر شاشةً غادرها صاحبها.
 */

import * as React from "react"

import type { BudgetTable, Campaign, DaysTable } from "./campaigns"
import type { ChatTurn } from "./chat"
import type { InventoryChoices } from "./inventory"
import type { SignupState } from "./signup"

export type ServerSize = "COMPACT" | "GAZE"

/** GET /api/me كما يردّه الخادم: لا بريد ولا تاريخ ميلاد. */
export interface Me {
  generations_left: number
  generation_limit: number
  display_name: string | null
  profession: "STOREKEEPER" | "MARKETING" | "SUPPORT" | null
  ui_size: ServerSize | null
  terms_current: boolean
  ai: { assistant: { per_day: number; used_today: number } }
}

/** نصّ «قبل أن تبدأ» من terms.notice(): ما يُحفظ، وما يُرسَل (سطرٌ لكل بوابة أو للكلّ). */
export interface Notice {
  version: string
  kept: string[]
  sent: { intro: string; items: { scope: "STOREKEEPER" | "MARKETING" | "SUPPORT" | "ALL"; text: string }[]; outro: string }
}

/** GET /api/choices: ما تعرضه الواجهة للاختيار، من الخادم وحده. */
export interface Choices {
  registration_open: boolean
  registration: {
    mode: "open" | "code" | "closed"
    name_max: number
    password_min: number
    earliest_year: number
    terms_version: string
  }
  support_contact: string | null
  ui_sizes: { code: ServerSize; name: string; detail: string }[]
  notice: Notice
  assistant: { question_max: number; ready: Record<string, string[]> }
  professions: { code: "STOREKEEPER" | "MARKETING" | "SUPPORT"; name: string; tagline: string }[]
  limits: { note_max: number; presets_max: number; versions_max: number; page_size: number }
  /** جدولا الميزانية والمدّة بكلماتهما، وخيارات التعديل وتعارضاتها: من الخادم لا من الواجهة. */
  budget: BudgetTable
  days: DaysTable
  edit_presets: string[]
  preset_conflicts: string[][]
  /** مفردات بوابة المخزون: الوحدات وفئات الضريبة والأسباب والحدود (inventory_rules.choices). */
  inventory: InventoryChoices
}

export interface State {
  choices: Choices | null
  /** صاحب الجلسة، أو null قبل الدخول. */
  me: Me | null
  /** الخيارات أو الجلسة لم تُقرأ بعد: لا شاشة تفاعلية قبلها. */
  booted: boolean
  /** رسالة إقلاعٍ فشل («حسناً» تعيده). */
  startupError: string | null
  busy: boolean
  nav: number
  signup: SignupState | null
  activation: { token: string; username: string } | null
  /** رسالةٌ تعرضها الشاشة التالية مرةً واحدة (رابط تسجيلٍ رُفض يُقال على شاشة الدخول). */
  flash: string | null
  /** أداة الحملة (lib/campaigns): الحملة المفتوحة، وصفحة «حملاتي»، وطلب التعديل قيد الإعداد. */
  campaign: Campaign | null
  page: number
  edit: EditState
  /** حملةٌ يُكتب نصّها الآن في هذه الصفحة، وقفل الشاشة ما دام قائماً. */
  waitingFor: string | null
  wakeLock: WakeLockSentinel | null
  /** حملةٌ انقطع طلب كتابتها في الطريق ولم تُقرأ بعده: الانتظار باقٍ و«تحقّق الآن» فيه هو المخرج. */
  waitUnknown: string | null
  /** المحادثة مع سيمبول (lib/chat.ts): في الصفحة وحدها، تذهب بتحديثها. */
  chat: ChatTurn[]
  /** حصّة أسئلة اليوم كما قالها آخر جواب، أو null قبل أوّل سؤال. */
  chatUsage: { per_day: number; used_today: number } | null
}

/** طلب التعديل قيد الإعداد، مربوطٌ بالنسخة التي يُبنى عليها. */
export interface EditState {
  versionId: string | null
  presets: string[]
  note: string | null
  draft: string
  /** اختار المستخدم شيئاً في شاشة التعديل: قبلها «اطلب نسخة جديدة» معطّل. */
  armed: boolean
}

export const EMPTY_EDIT: EditState = { versionId: null, presets: [], note: null, draft: "", armed: false }

let state: State = {
  choices: null,
  me: null,
  booted: false,
  startupError: null,
  busy: false,
  nav: 0,
  signup: null,
  activation: null,
  flash: null,
  campaign: null,
  page: 1,
  edit: EMPTY_EDIT,
  waitingFor: null,
  wakeLock: null,
  waitUnknown: null,
  chat: [],
  chatUsage: null,
}

const listeners = new Set<() => void>()

export function getState(): State {
  return state
}

export function setState(patch: Partial<State> | ((current: State) => Partial<State>)) {
  const next = typeof patch === "function" ? patch(state) : patch
  state = { ...state, ...next }
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useStore<T>(select: (current: State) => T): T {
  return React.useSyncExternalStore(subscribe, () => select(state))
}

/** انتقالٌ جديد: ما يصل بعده لطلبٍ أقدم لا يرسم شيئاً. */
export function nextNav(): number {
  setState((current) => ({ nav: current.nav + 1 }))
  return state.nav
}

/** للاختبارات: حالةٌ أولى من جديد. */
export function resetState(patch: Partial<State> = {}) {
  state = {
    choices: null, me: null, booted: false, startupError: null, busy: false, nav: 0, signup: null, activation: null,
    flash: null, campaign: null, page: 1, edit: EMPTY_EDIT, waitingFor: null, wakeLock: null, waitUnknown: null,
    chat: [], chatUsage: null,
    ...patch,
  }
  listeners.forEach((listener) => listener())
}
