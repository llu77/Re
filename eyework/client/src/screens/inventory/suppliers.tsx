/*
 * المورّدون ومندوبوهم
 * ===================
 * المورّد باسمه ورقمه الضريبي (15 رقماً يبدأ وينتهي بـ3) وسجلّه التجاري وهاتفه؛ وله مندوبون
 * («المندوب بحيث يكتب اسم المندوب» في طلب المالك): اسمٌ وجوال، وواحدٌ افتراضي يُقترح في الفاتورة.
 * القائمة تُبحث بالاسم، والبطاقة تعرض المندوبين صفوفاً تُفتح للتعديل.
 */

import * as React from "react"
import { PencilLine, Plus, Save, Truck, UserRound } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Slots } from "@/components/shell/slots"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input, Textarea } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { Tabs } from "@/components/ui/tabs"
import type { Paged, Rep, Supplier } from "@/lib/inventory"
import { LIST_PAGE, useSize } from "@/lib/size"

import { Facts, GazeHost, GazeSlot, type Fact } from "./common"
import type { Fail } from "./setup"

export function SuppliersScreen({ data, query, onQuery, archived, onArchived, page, onPage, onOpen, onNew, onBack }: {
  data: Paged<Supplier> | null
  query: string
  onQuery: (query: string) => void
  /** المؤرشفون في قائمتهم: منها يُفتح المورّد ويُعاد تفعيله. */
  archived: boolean
  onArchived: (archived: boolean) => void
  page: number
  onPage: (page: number) => void
  onOpen: (supplier: Supplier) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  return (
    <Screen
      title="المورّدون"
      back={{ id: "suppliers-back", label: "المخزون", onClick: onBack }}
      end={{ id: "suppliers-new", label: "مورّد جديد", icon: Plus, onClick: onNew }}
    >
      <Field label="ابحث بالاسم">
        <Input id="suppliers-search" type="search" autoComplete="off" value={query} onChange={(event) => onQuery(event.target.value)} />
      </Field>
      <Tabs items={[{ id: "active", label: "النشطون" }, { id: "archived", label: "المؤرشفون" }]} value={archived ? "archived" : "active"}
            onValueChange={(id) => onArchived(id === "archived")} label="التصفية">
      {data === null ? null : (
        <DataTable<Supplier>
          caption="المورّدون"
          rows={data.items}
          rowKey={(row) => row.id}
          columns={[
            { id: "name", header: "المورّد", cell: (row) => row.name },
            { id: "vat", header: "الرقم الضريبي", numeric: true, cell: (row) => row.vat_number ?? "" },
            { id: "phone", header: "الهاتف", numeric: true, cell: (row) => row.phone ?? "" },
          ]}
          primary={(row) => row.name}
          secondary={(row) => (row.vat_number ? `ض ${row.vat_number}` : gaze ? "" : "بلا رقمٍ ضريبي")}
          onOpen={onOpen}
          openLabel={(row) => `افتح ${row.name}`}
          pageSize={LIST_PAGE}
          page={page}
          onPageChange={onPage}
          total={data.total}
          empty={<EmptyState icon={Truck} title={query ? "لا مورّد يطابق" : archived ? "لا مورّدين مؤرشفين" : "لا مورّدين بعد"}
                             description={query || archived ? undefined : "أضف مورّدك الأوّل، أو أنشئه من رأس فاتورة شراء."} />}
        />
      )}
      </Tabs>
    </Screen>
  )
}

export function SupplierScreen({ supplier, onEdit, onAddRep, onEditRep, onBack }: {
  supplier: Supplier
  onEdit: () => void
  onAddRep: () => void
  onEditRep: (rep: Rep) => void
  onBack: () => void
}) {
  const reps = supplier.reps ?? []
  const facts: Fact[] = [
    { label: "الرقم الضريبي", value: supplier.vat_number ? <span className="num" dir="ltr">{supplier.vat_number}</span> : null, key: true },
    { label: "السجلّ التجاري", value: supplier.cr_number ? <span className="num" dir="ltr">{supplier.cr_number}</span> : null },
    { label: "الهاتف", value: supplier.phone ? <span className="num" dir="ltr">{supplier.phone}</span> : null, key: true },
    { label: "ملاحظة", value: supplier.note },
  ]
  return (
    <Screen
      title={supplier.name}
      above={supplier.is_active ? undefined : <Badge className="self-start">مؤرشف</Badge>}
      back={{ id: "supplier-back", label: "المورّدون", onClick: onBack }}
      end={{ id: "supplier-edit", label: "عدّل", icon: PencilLine, onClick: onEdit }}
      actions={
        // في الخانة الأولى: تفتح نموذج المندوب و«رجوع» في موضعها، و«احفظ» في الثانية.
        <Slots
          actions
          start={
            <Button id="supplier-add-rep" variant="secondary" icon={Plus} onClick={onAddRep}>
              أضف مندوباً
            </Button>
          }
        />
      }
    >
      <Facts facts={facts} columns={2} />
      <section aria-labelledby="supplier-reps" className="flex flex-col gap-tg">
        <h2 id="supplier-reps" className="text-lead font-semibold">المندوبون</h2>
        <DataTable<Rep>
          caption="مندوبو المورّد"
          rows={reps}
          rowKey={(rep) => rep.id}
          columns={[
            { id: "name", header: "المندوب", cell: (rep) => rep.name },
            { id: "mobile", header: "الجوال", numeric: true, cell: (rep) => rep.mobile ?? "" },
            { id: "default", header: "", cell: (rep) => (rep.is_default ? <Badge tone="info">الافتراضي</Badge> : rep.is_active ? "" : <Badge>مؤرشف</Badge>) },
          ]}
          primary={(rep) => rep.name}
          secondary={(rep) => rep.mobile ?? "بلا جوال"}
          trailing={(rep) => (rep.is_default ? <Badge tone="info">الافتراضي</Badge> : rep.is_active ? null : <Badge>مؤرشف</Badge>)}
          onOpen={onEditRep}
          openLabel={(rep) => `عدّل المندوب ${rep.name}`}
          pageSize={{ compact: 20, gaze: 3, gazeShort: 2 }}
          empty={<p className="text-small text-muted-foreground">لا مندوبين بعد: أضف اسم من يورّد لك ليظهر في الفاتورة.</p>}
        />
      </section>
    </Screen>
  )
}

export interface SupplierBody {
  name: string
  vat_number: string | null
  cr_number: string | null
  phone: string | null
  note: string | null
  is_active?: boolean
}

export function SupplierForm({ supplier, initialName = "", onSave, onBack }: {
  supplier: Supplier | null
  initialName?: string
  onSave: (body: SupplierBody) => Promise<Fail>
  onBack: () => void
}) {
  const [name, setName] = React.useState(supplier?.name ?? initialName)
  const [vat, setVat] = React.useState(supplier?.vat_number ?? "")
  const [cr, setCr] = React.useState(supplier?.cr_number ?? "")
  const [phone, setPhone] = React.useState(supplier?.phone ?? "")
  const [note, setNote] = React.useState(supplier?.note ?? "")
  const [active, setActive] = React.useState<"yes" | "no">(supplier?.is_active === false ? "no" : "yes")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const error = (field: string) => (fail?.field === field ? fail.message : null)

  async function save() {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) {
      setFail({ message: "اكتب اسم المورّد (حرفان على الأقل).", field: "name" })
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onSave({
      name: trimmed, vat_number: vat.trim() || null, cr_number: cr.trim() || null, phone: phone.trim() || null, note: note.trim() || null,
      ...(supplier ? { is_active: active === "yes" } : {}),
    })
    setBusy(false)
    if (result) setFail(result)
  }

  return (
    <Screen
      title={supplier ? `تعديل ${supplier.name}` : "مورّد جديد"}
      actions={
        <Slots
          actions
          start={
            <Button id="supplier-form-back" icon={BackIcon} onClick={onBack}>
              رجوع
            </Button>
          }
          end={
            <Button id="supplier-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
              {supplier ? "احفظ التعديل" : "أنشئ المورّد"}
            </Button>
          }
        />
      }
    >
      {fail && !fail.field ? (
        <Alert tone="danger" title="لم يُحفظ" live>
          {fail.message}
        </Alert>
      ) : null}
      <GazeHost>
        <GazeSlot id="supplier-name">
          <Field label="اسم المورّد" error={error("name")} required>
            <Input id="supplier-name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="supplier-vat">
          <Field label="الرقم الضريبي" hint="15 رقماً يبدأ بـ3 وينتهي بـ3، كما في فاتورته." error={error("vat_number")}>
            <Input id="supplier-vat" numeric inputMode="numeric" value={vat} maxLength={15} onChange={(event) => setVat(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="supplier-cr">
          <Field label="السجلّ التجاري" hint="10 أرقام، اختياري." error={error("cr_number")} className="gaze:short:hidden">
            <Input id="supplier-cr" numeric inputMode="numeric" value={cr} maxLength={10} onChange={(event) => setCr(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="supplier-phone">
          <Field label="الهاتف" hint="05xxxxxxxx أو 01xxxxxxxx." error={error("phone")}>
            <Input id="supplier-phone" numeric inputMode="tel" value={phone} maxLength={13} onChange={(event) => setPhone(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="supplier-note">
          <Field label="ملاحظة" error={error("note")} className="gaze:hidden">
            <Textarea id="supplier-note" rows={2} maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
        </GazeSlot>
        {supplier ? (
          <GazeSlot id="supplier-active">
            <RadioCards<"yes" | "no">
              label="الحالة"
              value={active}
              onValueChange={setActive}
              options={[
                { value: "yes", title: "نشط" },
                { value: "no", title: "مؤرشف", description: "لا يظهر في الفواتير الجديدة." },
              ]}
            />
          </GazeSlot>
        ) : null}
      </GazeHost>
    </Screen>
  )
}

export interface RepBody {
  name: string
  mobile: string | null
  is_default: boolean
  is_active?: boolean
}

export function RepForm({ supplier, rep, onSave, onBack }: {
  supplier: Supplier
  rep: Rep | null
  onSave: (body: RepBody) => Promise<Fail>
  onBack: () => void
}) {
  const [name, setName] = React.useState(rep?.name ?? "")
  const [mobile, setMobile] = React.useState(rep?.mobile ?? "")
  const [isDefault, setIsDefault] = React.useState<"yes" | "no">(rep?.is_default || (!rep && !(supplier.reps ?? []).length) ? "yes" : "no")
  const [active, setActive] = React.useState<"yes" | "no">(rep?.is_active === false ? "no" : "yes")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const error = (field: string) => (fail?.field === field ? fail.message : null)

  async function save() {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) {
      setFail({ message: "اكتب اسم المندوب.", field: "name" })
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onSave({ name: trimmed, mobile: mobile.trim() || null, is_default: isDefault === "yes", ...(rep ? { is_active: active === "yes" } : {}) })
    setBusy(false)
    if (result) setFail(result)
  }

  return (
    <Screen
      title={rep ? `المندوب ${rep.name}` : "مندوبٌ جديد"}
      description={supplier.name}
      actions={
        <Slots
          actions
          start={
            <Button id="rep-back" icon={BackIcon} onClick={onBack}>
              المورّد
            </Button>
          }
          end={
            <Button id="rep-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
              احفظ
            </Button>
          }
        />
      }
    >
      {fail && !fail.field ? (
        <Alert tone="danger" title="لم يُحفظ" live>
          {fail.message}
        </Alert>
      ) : null}
      <GazeHost>
        <GazeSlot id="rep-name">
          <Field label="اسم المندوب" error={error("name")} required>
            <Input id="rep-name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="rep-mobile">
          <Field label="الجوال" hint="05xxxxxxxx" error={error("mobile")}>
            <Input id="rep-mobile" numeric inputMode="tel" value={mobile} maxLength={13} onChange={(event) => setMobile(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="rep-default">
          <RadioCards<"yes" | "no">
            label="الافتراضي في الفاتورة"
            value={isDefault}
            onValueChange={setIsDefault}
            options={[
              { value: "yes", title: "نعم", icon: UserRound },
              { value: "no", title: "لا" },
            ]}
          />
        </GazeSlot>
        {rep ? (
          <GazeSlot id="rep-active">
            <RadioCards<"yes" | "no">
              label="الحالة"
              value={active}
              onValueChange={setActive}
              options={[
                { value: "yes", title: "نشط" },
                { value: "no", title: "مؤرشف" },
              ]}
            />
          </GazeSlot>
        ) : null}
      </GazeHost>
    </Screen>
  )
}
