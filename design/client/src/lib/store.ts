/*
 * حالة التطبيق — `state` في app.js نفسها، في مخزنٍ يقرؤه React بـuseSyncExternalStore.
 * المنطق كما هو: الخادم مصدر كل قيمة، و`nav` يزيد مع كل انتقال فلا يرسم ردٌّ متأخّر
 * شاشةً غادرها صاحبها.
 */
import * as React from "react"

import type { Choices, Portal } from "./types"

export interface AlertState {
  screen: string
  message: string
}

export interface SignupState {
  agreed: boolean
  name: string
  year: number | null
  month: number | null
  day: number | null
  profession: string | null
  email: string
}

export interface AssistantAnswer {
  question: string
  parts: string[]
  sources: string[]
}

export interface State {
  choices: Choices | null
  displayName: string | null
  portal: Portal | null
  alert: AlertState | null
  busy: boolean
  nav: number
  signup: SignupState | null
  assistant: { picked: string | null; draft: string; answer: AssistantAnswer | null; part: number; waiting: boolean }
}

let state: State = {
  choices: null,
  displayName: null,
  portal: null,
  alert: null,
  busy: false,
  nav: 0,
  signup: null,
  assistant: { picked: null, draft: "", answer: null, part: 0, waiting: false },
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

/* انتقالٌ جديد: ما يصل بعده لطلبٍ أقدم لا يرسم شيئاً. */
export function nextNav(): number {
  setState((current) => ({ nav: current.nav + 1, alert: null }))
  return state.nav
}

/* تنبيهٌ يبقى حتى «حسناً»، وأزرار الشريطين مقفلةٌ ما دام ظاهراً (Screen). */
export function showAlert(screen: string, message: string) {
  setState({ alert: { screen, message } })
}

export function clearAlert() {
  setState({ alert: null })
}
