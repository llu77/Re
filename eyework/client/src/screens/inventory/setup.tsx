/*
 * إعداد المخزن وإعداداته وتصنيفاته
 * ===============================
 * أوّل مرة: سؤال ضريبة المشتريات (أسعار الشراء قبل الضريبة أم شاملة؛ يُقفل بعد أوّل فاتورة
 * مسجّلة) واسم المخزن (الافتراضي «المخزن الرئيسي») وموقعه. والإعدادات نفسها بعد ذلك، ومنها
 * التصنيفات: تُضاف بالاسم وتُؤرشف ولا تُحذف (المنتجات تشير إليها).
 */

import * as React from "react"
import { Archive, ArchiveRestore, Plus, Save, Tags } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import type { Category, Settings } from "@/lib/inventory"
import { useSize } from "@/lib/size"

export type Fail = { message: string; field: string | null } | null

export interface SettingsBody {
  cost_includes_vat: boolean
  store_name: string | null
  store_location: string | null
  expected_row_version?: number
}

export function SettingsScreen({ settings, onSave, onBack, onCategories }: {
  /** null في الإعداد الأوّل. */
  settings: Settings | null
  onSave: (body: SettingsBody) => Promise<Fail>
  onBack: () => void
  onCategories: (() => void) | null
}) {
  const first = settings === null
  const [basis, setBasis] = React.useState<"net" | "gross">(settings?.cost_includes_vat ? "gross" : "net")
  const [name, setName] = React.useState(settings?.store_name ?? "المخزن الرئيسي")
  const [location, setLocation] = React.useState(settings?.store_location ?? "")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const [saved, setSaved] = React.useState(false)
  const locked = Boolean(settings?.cost_basis_locked)

  async function save() {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) {
      setFail({ message: "اكتب اسم المخزن (حرفان على الأقل).", field: "store_name" })
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onSave({
      cost_includes_vat: basis === "gross",
      store_name: trimmed,
      store_location: location.trim() || null,
      ...(settings ? { expected_row_version: settings.row_version } : {}),
    })
    setBusy(false)
    if (result) setFail(result)
    else setSaved(true)
  }

  return (
    <Screen
      title={first ? "قبل أوّل فاتورة" : "إعدادات المخزن"}
      description={first ? "سؤالٌ واحد عن الضريبة، واسم مخزنك." : undefined}
      back={{ id: "settings-back", label: first ? "الرئيسية" : "رجوع", onClick: onBack }}
      end={onCategories && !first ? { id: "settings-categories", label: "التصنيفات", icon: Tags, onClick: onCategories } : undefined}
      actions={
        <Button id="settings-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
          {first ? "احفظ وابدأ" : "احفظ"}
        </Button>
      }
    >
      {locked ? (
        <p className="text-flow text-muted-foreground">
          أسعار الشراء تُكتب <span className="font-semibold text-foreground">{basis === "gross" ? "شاملةً الضريبة" : "قبل الضريبة"}</span>؛ وقد قُفل هذا بعد أوّل فاتورةٍ مسجّلة.
        </p>
      ) : (
        <RadioCards<"net" | "gross">
          label="كيف تُكتب أسعار الشراء في فواتير مورّديك؟"
          value={basis}
          onValueChange={setBasis}
          ids={{ net: "settings-basis-net", gross: "settings-basis-gross" }}
          options={[
            { value: "net", title: "قبل الضريبة", description: "تُضاف الضريبة 15% على السعر." },
            { value: "gross", title: "شاملةً الضريبة", description: "السعر يحوي الضريبة، وتُفصل منه." },
          ]}
        />
      )}
      <Field label="اسم المخزن" error={fail?.field === "store_name" ? fail.message : null} required>
        <Input id="settings-store-name" value={name} maxLength={80} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="الموقع" hint="اختياري: المدينة أو الحيّ أو رقم المستودع." className="gaze:short:hidden">
        <Input id="settings-store-location" value={location} maxLength={120} onChange={(event) => setLocation(event.target.value)} />
      </Field>
      {fail && fail.field !== "store_name" ? (
        <Alert tone="danger" title="لم يُحفظ" live>
          {fail.message}
        </Alert>
      ) : null}
      {saved ? (
        <p role="status" className="text-small font-semibold text-success">
          حُفظت الإعدادات.
        </p>
      ) : null}
    </Screen>
  )
}

/* ── التصنيفات ───────────────────────────────────────────────────── */

export function CategoriesScreen({ categories, onAdd, onToggle, onBack }: {
  categories: Category[]
  onAdd: (name: string) => Promise<Fail>
  onToggle: (category: Category) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [name, setName] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const [page, setPage] = React.useState(0)
  const perPage = gaze ? 3 : 50
  const pages = Math.max(1, Math.ceil(categories.length / perPage))
  const current = Math.min(page, pages - 1)
  const visible = categories.slice(current * perPage, current * perPage + perPage)

  async function add() {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) {
      setFail({ message: "اكتب اسم التصنيف (حرفان على الأقل).", field: "name" })
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onAdd(trimmed)
    setBusy(false)
    if (result) setFail(result)
    else setName("")
  }

  return (
    <Screen
      title="التصنيفات"
      description={gaze ? undefined : "تجمع المنتجات في المخزون والجرد. تُؤرشف ولا تُحذف."}
      back={{ id: "categories-back", label: "الإعدادات", onClick: onBack }}
    >
      <div className="flex items-end gap-tg">
        <Field label="تصنيفٌ جديد" error={fail?.field === "name" ? fail.message : null} className="flex-1">
          <Input id="category-name" value={name} maxLength={40} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Button id="category-add" variant="secondary" commit icon={Plus} busy={busy} onClick={() => void add()}>
          أضف
        </Button>
      </div>
      {fail && fail.field !== "name" ? (
        <Alert tone="danger" title="لم يتمّ" live>
          {fail.message}
        </Alert>
      ) : null}
      {categories.length === 0 ? (
        <EmptyState icon={Tags} title="لا تصنيفات بعد" description="اكتب اسماً وأضفه؛ ثم اختره في بطاقة المنتج." />
      ) : (
        <ul id="categories-list" aria-label="التصنيفات" className="flex flex-col gap-tg-min">
          {visible.map((category) => (
            <li key={category.id} className="flex min-h-ctl items-center justify-between gap-tg rounded-card border border-border bg-card px-3 py-1">
              <span className="flex min-w-0 flex-col">
                <span className="truncate font-semibold">{category.name}</span>
                <span className="text-small text-muted-foreground">
                  <span className="num">{category.items ?? 0}</span> منتج{category.is_active ? "" : " · مؤرشف"}
                </span>
              </span>
              {gaze ? null : (
                <Button
                  variant={category.is_active ? "danger-outline" : "outline"}
                  commit
                  icon={category.is_active ? Archive : ArchiveRestore}
                  onClick={() => void onToggle(category).then((result) => setFail(result))}
                >
                  {category.is_active ? "أرشف" : "أعد"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {pages > 1 ? (
        <div className="grid grid-cols-2 gap-tg">
          <Button disabled={current === 0} onClick={() => setPage(current - 1)}>
            السابقة
          </Button>
          <Button disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            التالية
          </Button>
        </div>
      ) : null}
    </Screen>
  )
}
