/*
 * المصاريف والمجاميع والسندات
 * ===========================
 * المصاريف: دفتر المشتريات شهراً شهراً — كل فاتورةٍ مسجّلة قيدٌ فيه، والمرتجع والقيد العكسي يخصمان.
 * المجاميع: بطاقات الشهر (المشتريات قبل الضريبة، وضريبتها، والمرتجعات، وقيمة المخزون) و«يحتاج
 * انتباهك» بأعداده، وآخر الفواتير. السندات: ما سُجّل من أرصدة افتتاحية وصرفٍ وجردٍ فردي.
 */

import { BadgePercent, Boxes, ChevronLeft, ChevronRight, ClipboardList, ShoppingCart, TriangleAlert, Undo2, Wallet } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { StatCard } from "@/components/ui/stat-card"
import { formatDay } from "@/lib/format"
import {
  LEDGER_KIND, PURCHASE_STATUS, VOUCHER_KIND, codeName, formatMilli, monthLabel,
  type Expenses, type InventoryChoices, type LedgerEntry, type Paged, type PurchaseRow, type Summary, type Voucher,
} from "@/lib/inventory"
import { formatAmount, formatWhole } from "@/lib/money"
import { LONG_LIST_PAGE, useSize } from "@/lib/size"

import { Money } from "./common"
import { attentionItems } from "./home"

const TONE: Record<LedgerEntry["kind"], "info" | "warning" | "neutral"> = { PURCHASE: "info", RETURN: "warning", REVERSAL: "neutral" }

export function ExpensesScreen({ month, data, canNext, onPrevious, onNext, page, onPage, onOpen, onBack }: {
  month: string
  data: Expenses | null
  canNext: boolean
  onPrevious: () => void
  onNext: () => void
  page: number
  onPage: (page: number) => void
  onOpen: (entry: LedgerEntry) => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const totals = data?.totals
  // الحجم الكبير: الشهر في العنوان (يُعلَن حين يتغيّر) وصافيه سطر الوصف، فيبقى للزرّين صفٌّ يتّسعان فيه وللقيود الباقي.
  return (
    <Screen
      title={gaze ? `مصاريف ${monthLabel(month)}` : "المصاريف"}
      description={!gaze ? "كل فاتورة شراءٍ مسجّلة تُضاف هنا، والمرتجع والقيد العكسي يخصمان منها." : totals ? (
        <span>
          الصافي <Money halalas={totals.net.net} className="font-semibold text-foreground" /> · الضريبة{" "}
          <Money halalas={totals.net.vat} className="font-semibold text-foreground" unit={false} />
        </span>
      ) : undefined}
      back={gaze ? undefined : { id: "expenses-back", label: "الرئيسية", onClick: onBack }}
    >
      <nav aria-label="الشهر" className={gaze ? "grid grid-cols-2 gap-x-6" : "flex items-center justify-between gap-tg"}>
        <Button id="expenses-previous" icon={ChevronRight} onClick={onPrevious} className="justify-self-start">
          الشهر السابق
        </Button>
        {gaze ? null : (
          <p className="whitespace-nowrap text-lead font-bold" aria-live="polite">
            {monthLabel(month)}
          </p>
        )}
        <Button id="expenses-next" iconEnd={ChevronLeft} disabled={!canNext} onClick={onNext} className="justify-self-end">
          الشهر التالي
        </Button>
      </nav>
      {totals ? (
        gaze ? null : (
          <div className="grid grid-cols-2 gap-tg-min lg:grid-cols-4 lg:gap-tg">
            <StatCard label="المشتريات" icon={ShoppingCart} value={formatWhole(totals.purchases.net)} unit="ر.س" />
            <StatCard label="المرتجعات والعكسي" icon={Undo2} value={formatWhole(totals.returns.net + totals.reversals.net)} unit="ر.س" />
            <StatCard label="الصافي قبل الضريبة" icon={Wallet} value={formatWhole(totals.net.net)} unit="ر.س" />
            <StatCard label="صافي الضريبة" icon={BadgePercent} value={formatWhole(totals.net.vat)} unit="ر.س" />
          </div>
        )
      ) : null}
      {data ? (
        <DataTable<LedgerEntry>
          caption={`قيود ${monthLabel(month)}`}
          rows={data.entries.items}
          rowKey={(row) => `${row.kind}-${row.document}`}
          columns={[
            { id: "document", header: "المستند", cell: (row) => <span className="num">{row.document}</span> },
            { id: "date", header: "التاريخ", cell: (row) => formatDay(row.date) },
            { id: "kind", header: "النوع", cell: (row) => <Badge tone={TONE[row.kind]}>{LEDGER_KIND[row.kind]}</Badge> },
            { id: "supplier", header: "المورّد", cell: (row) => row.supplier_name ?? "" },
            // قبل الضريبة والضريبة على الحاسوب وحده: بجوار الشريط الجانبي في الآيباد لا تتّسع سبعة أعمدة، والمجموعان في البطاقات فوقها.
            { id: "net", header: "قبل الضريبة", numeric: true, className: "hidden xl:table-cell", cell: (row) => formatAmount(row.net) },
            { id: "vat", header: "الضريبة", numeric: true, className: "hidden xl:table-cell", cell: (row) => formatAmount(row.vat) },
            { id: "gross", header: "الإجمالي", numeric: true, cell: (row) => formatAmount(row.gross) },
          ]}
          primary={(row) => row.supplier_name ?? LEDGER_KIND[row.kind]}
          secondary={(row) => `${LEDGER_KIND[row.kind]} ${row.document} · ${formatDay(row.date)}`}
          trailing={(row) => (
            <span className="num font-bold" dir="ltr">
              {formatAmount(row.gross)}
            </span>
          )}
          onOpen={onOpen}
          openLabel={(row) => `افتح ${LEDGER_KIND[row.kind]} ${row.document}`}
          pageSize={LONG_LIST_PAGE}
          page={page}
          onPageChange={onPage}
          total={data.entries.total}
          empty={<EmptyState icon={Wallet} title="لا قيود في هذا الشهر" description="تظهر هنا فواتير الشراء حين تُسجَّل." />}
        />
      ) : null}
    </Screen>
  )
}

export function TotalsScreen({ summary, recent, onNavigate, onOpenPurchase, onBack }: {
  summary: Summary
  recent: PurchaseRow[] | null
  onNavigate: (href: string) => void
  onOpenPurchase: (row: PurchaseRow) => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const t = summary.month_totals
  const items = attentionItems(summary)
  return (
    <Screen
      title="المجاميع"
      description={`هذا الشهر: ${monthLabel(summary.month)}`}
      back={gaze ? undefined : { id: "totals-back", label: "الرئيسية", onClick: onBack }}
    >
      <div className="grid grid-cols-2 gap-tg-min lg:grid-cols-4 lg:gap-tg gaze:gap-tg">
        <StatCard label="المشتريات قبل الضريبة" icon={ShoppingCart} value={formatWhole(t.purchases.net)} unit="ر.س" />
        <StatCard label="ضريبة المشتريات" icon={BadgePercent} value={formatWhole(t.purchases.vat)} unit="ر.س" />
        <StatCard label="المرتجعات" icon={Undo2} value={formatWhole(t.returns.gross)} unit="ر.س" />
        <StatCard label="قيمة المخزون" icon={Boxes} value={formatWhole(summary.stock_value)} unit="ر.س" />
      </div>
      <section aria-labelledby="totals-attention" className="flex flex-col gap-tg-min gaze:gap-tg">
        <h2 id="totals-attention" className="flex items-center gap-2 text-lead font-bold gaze:sr-only">
          <TriangleAlert aria-hidden="true" className="size-icon text-warning" />
          يحتاج انتباهك
        </h2>
        {items.length === 0 ? (
          <p className="text-flow text-muted-foreground">لا شيء ينتظرك.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-tg-min tablet:grid-cols-3 gaze:gap-tg">
            {items.slice(0, gaze ? 2 : 6).map((item) => (
              <li key={item.id}>
                <StatCard label={item.text} icon={TriangleAlert} tone="warning" value="" onSelect={() => onNavigate(item.href)} className="w-full" />
              </li>
            ))}
          </ul>
        )}
      </section>
      {gaze || recent === null ? null : (
        <section aria-labelledby="totals-recent" className="flex flex-col gap-tg">
          <h2 id="totals-recent" className="text-lead font-bold">آخر فواتير الشراء</h2>
          <DataTable<PurchaseRow>
            caption="آخر فواتير الشراء"
            rows={recent}
            rowKey={(row) => row.id}
            columns={[
              { id: "label", header: "الرقم", cell: (row) => <span className="num">{row.label ?? "مسودة"}</span> },
              { id: "supplier", header: "المورّد", cell: (row) => row.supplier_name ?? "" },
              { id: "date", header: "التاريخ", cell: (row) => (row.invoice_date ? formatDay(row.invoice_date) : "") },
              { id: "status", header: "الحالة", cell: (row) => <Badge tone={row.status === "POSTED" ? "success" : row.status === "DRAFT" ? "info" : "neutral"}>{PURCHASE_STATUS[row.status]}</Badge> },
              { id: "total", header: "الإجمالي", numeric: true, cell: (row) => (row.total_halalas === null ? "" : formatAmount(row.total_halalas)) },
            ]}
            primary={(row) => row.supplier_name ?? "بلا مورّد"}
            secondary={(row) => `${row.label ?? "مسودة"}${row.invoice_date ? ` · ${formatDay(row.invoice_date)}` : ""}`}
            trailing={(row) => (row.total_halalas === null ? null : <span className="num font-bold" dir="ltr">{formatAmount(row.total_halalas)}</span>)}
            onOpen={onOpenPurchase}
            openLabel={(row) => `افتح ${row.label ?? "المسودة"}`}
            pageSize={{ compact: 5, gaze: 2, gazeShort: 1 }}
            empty={<p className="text-small text-muted-foreground">لا فواتير بعد.</p>}
          />
        </section>
      )}
    </Screen>
  )
}

export function VouchersScreen({ data, page, onPage, choices, onOpenItem, onBack }: {
  data: Paged<Voucher> | null
  page: number
  onPage: (page: number) => void
  choices: InventoryChoices
  onOpenItem: (voucher: Voucher) => void
  onBack: () => void
}) {
  const reasonName = (voucher: Voucher) =>
    voucher.kind === "ISSUE" ? codeName(choices.issue_reasons, voucher.reason) : codeName([...choices.count_reasons.SHORTAGE, ...choices.count_reasons.SURPLUS], voucher.reason)
  return (
    <Screen title="السندات" back={{ id: "vouchers-back", label: "المخزون", onClick: onBack }}>
      {data === null ? null : (
        <DataTable<Voucher>
          caption="السندات"
          rows={data.items}
          rowKey={(row) => row.id}
          columns={[
            { id: "label", header: "السند", cell: (row) => <span className="num">{row.label}</span> },
            { id: "date", header: "التاريخ", cell: (row) => formatDay(row.occurred_on) },
            { id: "kind", header: "النوع", cell: (row) => VOUCHER_KIND[row.kind] },
            { id: "item", header: "المنتج", cell: (row) => row.item.name },
            { id: "quantity", header: "الكمية", numeric: true, cell: (row) => `${formatMilli(row.quantity_milli)} ${row.item.unit_name}` },
            { id: "reason", header: "السبب", cell: (row) => (row.reason ? reasonName(row) : "") },
          ]}
          primary={(row) => row.item.name}
          secondary={(row) => `${VOUCHER_KIND[row.kind]} ${row.label} · ${formatDay(row.occurred_on)}${row.count_label ? ` · ${row.count_label}` : ""}`}
          trailing={(row) => (
            <span className="num font-bold" dir="ltr">
              {formatMilli(row.quantity_milli)}
            </span>
          )}
          onOpen={onOpenItem}
          openLabel={(row) => `افتح ${row.item.name}`}
          pageSize={LONG_LIST_PAGE}
          page={page}
          onPageChange={onPage}
          total={data.total}
          empty={<EmptyState icon={ClipboardList} title="لا سندات بعد" description="تُسجَّل من بطاقة المنتج: رصيدٌ افتتاحي أو صرفٌ أو جرد." />}
        />
      )}
    </Screen>
  )
}
