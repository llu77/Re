export interface PortalItem {
  text: string
  note: string
  mode?: "IN_APP" | "EMPLOYER_SYSTEM" | "ON_SITE" | "VOICE"
}

export interface Portal {
  profession: string
  name: string
  summary: string
  tools: string[]
  tasks: PortalItem[]
  skills: PortalItem[]
  sources: { tasks: string; skills: string; summary: string }
  attribution: string
  related: string[]
}

export interface Choices {
  registration_open: boolean
  registration: { name_max: number; password_min: number; earliest_year: number; terms_version: string }
  professions: { code: string; name: string; tagline: string }[]
  limits: { note_max: number; presets_max: number; versions_max: number; page_size: number }
}
