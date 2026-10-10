/*
 * بوابة صاحب الحساب (loadPortal في portal.js). `fresh` يقرؤها من جديد (الرئيسية
 * والحساب): المهنة قد تتغيّر والتطبيق مفتوح. وإن تعذّرت القراءة بقي ما عُرف.
 */
import { api } from "./api"
import { getState, setState } from "./store"
import type { Portal } from "./types"

export async function loadPortal({ fresh = false }: { fresh?: boolean } = {}): Promise<Portal | null> {
  const known = getState().portal
  if (known && !fresh) return known
  const result = await api<Portal>("GET", "/api/portal")
  if (result.status !== 200 || !result.data) return getState().portal
  setState({ portal: result.data })
  return result.data
}
