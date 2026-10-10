/*
 * أمين المخزون: المجاميع والمصاريف
 * ===============================
 * المجاميع («تظهر المجاميع»): بطاقات الشهر كما في inventory_spec §2.1 و§3.2 — المشتريات قبل
 * الضريبة، وضريبة المشتريات، والمرتجعات، وقيمة المخزون — يحسبها الخادم عند الفتح، ثم «يحتاج
 * انتباهك» (أعدادٌ يفتح كلٌّ قائمته)، وآخر الفواتير. في الحجم الكبير البطاقات و«يحتاج انتباهك».
 *
 * المصاريف (inventory_spec §3.13): دفتر المشتريات — كل فاتورةٍ مسجّلة تدخله، والمرتجع والقيد
 * العكسي يخصمان منه. الشهر بزرّين «الشهر السابق» و«الشهر التالي» واسمه نصّاً، ثم المجاميع ثم
 * القيود صفحاتٍ (20 في العادي، و3 في الكبير). لا مصروفٌ يُكتب باليد: لم يطلبه المالك.
 */

import { AlertTriangle, BadgePercent, Boxes, ChevronLeft, ChevronRight, ShoppingCart, Undo2, Wallet } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { StatCard } from "@/components/ui/stat-card"
import { formatDay } from "@/lib/format"
import { formatAmount, formatWhole } from "@/lib/money"
import { useSize } from "@/lib/size"
import type { ExpenseRow, InvoiceRow } from "@/lib/work-types"

/* ── المجاميع ───────────────────────────────────────────────────── */

export interface StoreTotals {
  month: string
  purchasesNet: number
  purchasesVat: number
  returns: number
  stockValue: number
}

export interface Attention {
  id: string
  /** «noun: count» كما في inventory_spec §3.2: لا مطابقة عددٍ في الجملة. */
  label: string
  count: number
  late?: number
}

export interface StoreTotalsProps {
  totals: StoreTotals
  attention: Attention[]
  recent: InvoiceRow[]
  onAttention: (id: string) => void
  onOpenInvoice: (row: InvoiceRow) => void
}

const STATUS: Record<InvoiceRow["status"], { label: string; tone: "success" | "warning" | "neutral" }> = {
  RECORDED: { label: "مسجّلة", tone: "success" },
  PARTLY_RETURNED: { label: "منها مرتجع", tone: "warning" },
  RETURNED: { label: "معكوسة", tone: "neutral" },
}

export function StoreTotalsScreen({ totals, attention, recent, onAttention, onOpenInvoice }: StoreTotalsProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const shown = attention.filter((a) => a.count > 0)
  return (
    <Screen title="المجاميع" quietTitle description={`هذا الشهر: ${totals.month}`}>
      <div className="grid grid-cols-2 gap-tg-min lg:grid-cols-4 lg:gap-tg gaze:gap-tg">
        <StatCard label="المشتريات قبل الضريبة" icon={ShoppingCart} value={formatWhole(totals.purchasesNet)} unit="ر.س" />
        <StatCard label="ضريبة المشتريات" icon={BadgePercent} value={formatWhole(totals.purchasesVat)} unit="ر.س" />
        <StatCard label="المرتجعات" icon={Undo2} value={formatWhole(totals.returns)} unit="ر.س" />
        <StatCard label="قيمة المخزون" icon={Boxes} value={formatWhole(totals.stockValue)} unit="ر.س" />
      </div>
      <section aria-labelledby="attention" className="flex flex-col gap-tg-min gaze:gap-tg">
        <h2 id="attention" className="flex items-center gap-2 text-lead font-bold gaze:sr-only">
          <AlertTriangle aria-hidden="true" className="size-icon text-warning" />
          يحتاج انتباهك
        </h2>
        {shown.length === 0 ? (
          <p className="text-flow text-muted-foreground">لا شيء ينتظرك.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-tg-min md:grid-cols-3 gaze:gap-tg">
            {shown.slice(0, gaze ? 1 : 3).map((a) => (
              <li key={a.id}>
                <StatCard
                  label={a.label}
                  icon={AlertTriangle}
                  tone="warning"
                  value={String(a.count)}
                  hint={a.late ? `متأخر: ${a.late}` : undefined}
                  onSelect={() => onAttention(a.id)}
                  className="w-full"
                />
              </li>
            ))}
          </ul>
        )}
      </section>
      {gaze ? null : (
        <Card>
          <CardHeader>
            <CardTitle>آخر فواتير الشراء</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable<InvoiceRow>
              caption="آخر فواتير الشراء"
              rows={recent}
              rowKey={(row) => row.id}
              columns={[
                { id: "number", header: "الرقم", cell: (row) => <span className="num">{row.number}</span> },
                { id: "supplier", header: "المورّد", cell: (row) => row.supplier },
                { id: "date", header: "التاريخ", cell: (row) => formatDay(row.date) },
                { id: "status", header: "الحالة", cell: (row) => <Badge tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Badge> },
                { id: "gross", header: "الإجمالي (ر.س)", numeric: true, cell: (row) => formatAmount(row.gross) },
              ]}
              primary={(row) => row.supplier}
              secondary={(row) => `${row.number} · ${formatDay(row.date)}`}
              trailing={(row) => (
                <span className="num font-bold" dir="ltr">
                  {formatAmount(row.gross)}
                </span>
              )}
              onOpen={onOpenInvoice}
              openLabel={(row) => `افتح فاتورة الشراء ${row.number}`}
              pageSize={{ compact: 5, gaze: 3 }}
            />
          </CardContent>
        </Card>
      )}
    </Screen>
  )
}

/* ── المصاريف ───────────────────────────────────────────────────── */

export interface ExpensesProps {
  month: string
  onPrevious: () => void
  onNext: (() => void) | null
  rows: ExpenseRow[]
  totals: { purchases: number; returns: number; net: number; vat: number }
  onOpen: (row: ExpenseRow) => void
}

const KIND: Record<ExpenseRow["kind"], { label: string; tone: "info" | "warning" | "neutral" }> = {
  PURCHASE: { label: "شراء", tone: "info" },
  RETURN: { label: "مرتجع", tone: "warning" },
  REVERSAL: { label: "عكسي", tone: "neutral" },
}

export function ExpensesScreen({ month, onPrevious, onNext, rows, totals, onOpen }: ExpensesProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  return (
    <Screen title="المصاريف" quietTitle description={gaze ? undefined : "كل فاتورة شراءٍ مسجّلة تُضاف هنا، والمرتجع يخصم منها."}>
      <nav aria-label="الشهر" className="flex items-center justify-between gap-tg">
        <Button icon={ChevronRight} onClick={onPrevious}>
          <span className="gaze:hidden">الشهر </span>السابق
        </Button>
        <p className="whitespace-nowrap text-lead font-bold" aria-live="polite">
          {month}
        </p>
        <Button iconEnd={ChevronLeft} disabled={!onNext} onClick={() => onNext?.()}>
          <span className="gaze:hidden">الشهر </span>التالي
        </Button>
      </nav>
      {gaze ? (
        <p className="text-flow">
          الصافي{" "}
          <span className="num font-bold" dir="ltr">
            {formatAmount(totals.net)}
          </span>{" "}
          ر.س · الضريبة{" "}
          <span className="num font-bold" dir="ltr">
            {formatAmount(totals.vat)}
          </span>
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-tg-min md:grid-cols-4 md:gap-tg">
          <StatCard label="المشتريات" icon={ShoppingCart} value={formatWhole(totals.purchases)} unit="ر.س" />
          <StatCard label="المرتجعات" icon={Undo2} value={formatWhole(totals.returns)} unit="ر.س" />
          <StatCard label="الصافي قبل الضريبة" icon={Wallet} value={formatWhole(totals.net)} unit="ر.س" />
          <StatCard label="صافي الضريبة" icon={BadgePercent} value={formatWhole(totals.vat)} unit="ر.س" />
        </div>
      )}
      <DataTable<ExpenseRow>
        caption={`قيود ${month}`}
        rows={rows}
        rowKey={(row) => row.id}
        columns={[
          { id: "number", header: "المستند", cell: (row) => <span className="num">{row.number}</span> },
          { id: "date", header: "التاريخ", cell: (row) => formatDay(row.date) },
          { id: "kind", header: "النوع", cell: (row) => <Badge tone={KIND[row.kind].tone}>{KIND[row.kind].label}</Badge> },
          { id: "supplier", header: "المورّد", cell: (row) => row.supplier },
          { id: "net", header: "قبل الضريبة", numeric: true, cell: (row) => formatAmount(row.net) },
          { id: "vat", header: "الضريبة", numeric: true, cell: (row) => formatAmount(row.vat) },
          { id: "gross", header: "الإجمالي", numeric: true, cell: (row) => formatAmount(row.net + row.vat) },
        ]}
        primary={(row) => row.supplier}
        secondary={(row) => `${KIND[row.kind].label} ${row.number} · ${formatDay(row.date)}`}
        trailing={(row) => (
          <span className="num font-bold" dir="ltr">
            {formatAmount(row.net + row.vat)}
          </span>
        )}
        onOpen={onOpen}
        openLabel={(row) => `افتح ${KIND[row.kind].label} ${row.number}`}
        pageSize={{ compact: 20, gaze: 3, gazeShort: 2 }}
        empty={<EmptyState icon={Wallet} title="لا قيود في هذا الشهر" description="تظهر هنا فواتير الشراء حين تُسجَّل." />}
      />
    </Screen>
  )
}
