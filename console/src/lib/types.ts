/**
 * عقود بوابة الممارس كما يعلنها `api/practitioner/routes.py`. أيّ حقلٍ هنا
 * له نظيرٌ هناك بالاسم نفسه؛ التواريخ نصوص ISO كما يرسلها الخادم.
 */

export type ProposalKind = "PLAN" | "PLAN_UPDATE" | "ILLUSTRATION_SET" | "READINESS" | "DOCUMENTATION"

export type ProposalStatus =
  | "DRAFT"
  | "PENDING"
  | "APPROVED"
  | "EDITED_APPROVED"
  | "REJECTED"
  | "EXPIRED"

export type AffectedSide = "LEFT" | "RIGHT" | "BILATERAL"

export type Json = string | number | boolean | null | Json[] | { [key: string]: Json }

export interface Proposal {
  id: string
  patient_id: string
  kind: ProposalKind
  status: ProposalStatus
  payload: Record<string, Json>
  provenance: Record<string, Json>
  affected_side: AffectedSide | null
  priority: number
  is_red_flag: boolean
  version: number
  created_at: string
  queued_at: string | null
  expires_at: string | null
  reviewer_id: string | null
  decision_at: string | null
  rejection_reason: string | null
}

export interface Citation {
  source_id: string
  external_id: string
  title: string
  url: string
  published_year: number | null
  locator: string | null
  added_by: string
  added_at: string
}

export interface RedFlag {
  id: string
  patient_id: string
  body: string
  reported_at: string
  acknowledged_at: string | null
  escalation_seconds: number | null
}

export interface Session {
  token: string
  role: string
}
