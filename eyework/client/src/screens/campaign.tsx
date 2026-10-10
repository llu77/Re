/*
 * أداة الحملة: الشاشات
 * ====================
 * شاشات static/index.html بمكوّنات التصميم الجديد، في إطارٍ واحد (CampaignFrame): صفٌّ علويٌّ
 * بخانتين ثابتتين («رجوع» في البداية، وفي النهاية ما يغادر أو يتقدّم: «ألغِ الحملة»، «النسخة
 * السابقة»، «التالي»)، ثم الخطوات والعنوان، ثم المحتوى، ثم شريط إجراءاتٍ بخانتين ثابتتين.
 * الخانات ثابتةٌ لأن قاعدة الهبوط تقرأ المواضع: ما يقع تحت ضغطةٍ في الشاشة التالية لا يعتمد
 * شيئاً ولا يغيّر قيمة، وأقرب عنصرٍ مفعّلٍ إليها لا يعتمد. وفي الحجم الكبير لا تمرير: النصّ
 * المقترح صفحاتٌ (PagedText) يُقرأ كلّه ولا يُقصّ منه حرف.
 */

import * as React from "react"
import { Check, ChevronsLeftRight, Download, History, House, MessageSquareText, Minus, Plus, RefreshCw, Save, Share2, SquarePen, Trash2, Undo2, XCircle } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Slots, type TopAction } from "@/components/shell/slots"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, ButtonLink, NextIcon, buttonVariants } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Textarea } from "@/components/ui/input"
import { PagedText } from "@/components/ui/paged-text"
import { Stepper } from "@/components/ui/stepper"
import {
  PERSONA, PRESET_LABELS, STATUS_LABELS, WARNING_LABELS, dailyText, imageUrl, rowNames,
  type BudgetTable, type Campaign, type CampaignListItem, type DaysTable,
} from "@/lib/campaigns"
import { useSize } from "@/lib/size"
import type { EditState } from "@/lib/store"
import { cn } from "@/lib/utils"

export const STEPS = [
  { id: "photo", label: "صورة المنتج" },
  { id: "copy", label: "النصّ" },
  { id: "budget", label: "الميزانية" },
  { id: "days", label: "المدّة" },
  { id: "review", label: "المراجعة" },
]

export function CampaignFrame({ step, title, description, back, end, actions, children }: {
  /** الخطوة من 0، أو null بلا خطوات (التأكيد والإلغاء والجاهزة). */
  step: number | null
  title: string
  description?: React.ReactNode
  back?: TopAction
  end?: TopAction
  actions?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Screen
      title={title}
      description={description}
      back={back}
      end={end}
      above={step !== null ? <Stepper steps={STEPS} current={step} variant="brief" /> : undefined}
      actions={actions}
    >
      {children}
    </Screen>
  )
}

export interface Choice {
  key: string
  label: string
  pressed: boolean
  disabled: boolean
  onPress: () => void
}

/**
 * مجموعة خياراتٍ تُبدَّل في مكانها. في الحجم الكبير لا تزيد الشاشة على اثني عشر هدفاً، فما زاد على
 * أربعة خياراتٍ يُعرض ثلاثةً ثلاثةً وزرٌّ رابع يقلّب بينها («خياراتٌ أخرى» ثم «الخيارات الأولى»)؛
 * وفي الحجم العادي تُعرض كلّها.
 */
function ChoiceGroup({ id, label, items, otherLabel, firstLabel, numeric = false }: {
  id: string
  label: string
  items: Choice[]
  otherLabel: string
  firstLabel: string
  numeric?: boolean
}) {
  const { size } = useSize()
  const [page, setPage] = React.useState(0)
  const paged = size === "gaze" && items.length > 4
  const pages = paged ? Math.ceil(items.length / 3) : 1
  const current = Math.min(page, pages - 1)
  const shown = paged ? items.slice(current * 3, current * 3 + 3) : items
  return (
    <div id={id} role="group" aria-label={label} className={cn("grid gap-tg", paged ? "grid-cols-2" : "grid-cols-3")}>
      {shown.map((item) => (
        <Button
          key={item.key}
          isValue
          aria-pressed={item.pressed}
          disabled={item.disabled}
          data-key={item.key}
          variant={item.pressed ? "secondary" : "outline"}
          onClick={item.onPress}
          className={cn("chip rounded-pill px-2 gaze:px-2", numeric && "num")}
        >
          {item.label}
        </Button>
      ))}
      {paged ? (
        <Button id={`${id}-more`} icon={current + 1 < pages ? ChevronsLeftRight : Undo2} onClick={() => setPage((current + 1) % pages)}>
          {current + 1 < pages ? otherLabel : firstLabel}
        </Button>
      ) : null}
    </div>
  )
}

function Headline({ campaign, title, prefix }: { campaign: Campaign; title: string; prefix: string }) {
  return (
    <div className="flex items-start gap-tg-min">
      <img
        id={`${prefix}-thumb`}
        src={imageUrl(campaign)}
        alt=""
        width={56}
        height={56}
        className="size-12 shrink-0 rounded-ctl border border-border bg-muted object-cover gaze:size-14"
      />
      <p id={`${prefix}-title`} className="min-w-0 self-center text-lead font-semibold leading-snug text-heading">
        {title}
      </p>
    </div>
  )
}

/* ── الصورة ──────────────────────────────────────────────────────── */

export function PhotoScreen({ campaign, uploading, onFile, onGenerate, onBack, onCancel }: {
  campaign: Campaign | null
  uploading: boolean
  onFile: (file: File) => void
  onGenerate: () => void
  onBack: () => void
  /** حملةٌ قائمة تُلغى؛ والجديدة التي لا صورة لها بعد لا شيء يُلغى فيها. */
  onCancel: (() => void) | null
}) {
  const hasImage = Boolean(campaign?.image)
  return (
    <CampaignFrame
      step={0}
      title="صورة المنتج"
      back={{ id: "photo-back", label: "رجوع", onClick: onBack }}
      end={onCancel ? { id: "photo-cancel", label: "ألغِ الحملة", danger: true, icon: XCircle, onClick: onCancel } : undefined}
      actions={
        <Slots
          actions
          start={
            <Button id="photo-generate" variant="primary" commit disabled={!hasImage || uploading} icon={SquarePen} onClick={onGenerate}>
              اكتب لي العنوان والوصف
            </Button>
          }
        />
      }
    >
      <label
        htmlFor="photo-input"
        id="photo-pick"
        data-safe=""
        className={cn(buttonVariants({ variant: "secondary", width: "full" }), "cursor-pointer", uploading && "pointer-events-none opacity-60")}
      >
        {hasImage ? "اختر صورةً أخرى" : "اختر صورة المنتج"}
      </label>
      <input
        id="photo-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only text-input"
        disabled={uploading}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0]
          event.currentTarget.value = ""
          if (file) onFile(file)
        }}
      />
      {hasImage && campaign ? (
        <div className="flex min-h-0 justify-center gaze:min-h-0 gaze:flex-1">
          <img
            id="photo-preview"
            src={imageUrl(campaign)}
            alt="صورة المنتج"
            className="max-h-44 w-auto max-w-full rounded-card border border-border object-contain tablet:max-h-80 gaze:max-h-full"
          />
        </div>
      ) : null}
      <p id="photo-status" role="status" className="text-small text-muted-foreground empty:hidden">
        {uploading ? "تُرفع الصورة…" : ""}
      </p>
      {/* بعد اختيار الصورة يُخفى الشرح في الهاتف (قُرئ قبلها) لتتّسع الشاشة بلا تمرير، بالحجمين، وفي الكبير القصير. */}
      <p className={cn("text-small text-muted-foreground", hasImage && "compact:hidden compact:tablet:block gaze:max-tablet:hidden gaze:short:hidden")}>
        تُرسل صورة المنتج وحدها إلى خدمة ذكاءٍ اصطناعي لتكتب العنوان والوصف، بلا اسمك ولا أيّ معلومةٍ عنك. صوّر المنتج وحده، دون أشخاصٍ أو أوراق.
      </p>
    </CampaignFrame>
  )
}

/* ── الانتظار ────────────────────────────────────────────────────── */

export function WaitingScreen({ reloaded, mayLock, busy, onCheck, onBack }: {
  /** انتظارٌ لم تبدأه هذه الصفحة (أو لم يُعرف مآله): «تحقّق الآن» فيه. */
  reloaded: boolean
  /** لا قفل للشاشة: يُقال إنها قد تُقفل. */
  mayLock: boolean
  busy: boolean
  onCheck: () => void
  onBack: () => void
}) {
  return (
    // الشريط السفلي خانتان فارغتان في مكانهما: نتيجةٌ تصل بعد دقائق لا تجد زرّاً تحت النظر.
    <CampaignFrame step={1} title={`يكتب ${PERSONA}`} back={{ id: "proposal-back", label: "رجوع", onClick: onBack }} actions={<Slots actions />}>
      <div id="proposal-waiting" className="flex flex-col gap-tg">
        <p role="status" className="text-flow">
          يكتب {PERSONA} العنوان والوصف. قد يستغرق ذلك حتى ثلاث دقائق تقريباً. لا حاجة لفعل شيء.
        </p>
        {mayLock ? (
          <p id="proposal-awake" className="text-small text-muted-foreground">
            قد تُقفل الشاشة أثناء الانتظار. إن أُقفلت فافتح التطبيق من جديد: يعود إلى هذه الشاشة.
          </p>
        ) : null}
        {reloaded ? (
          <Button id="proposal-check" icon={RefreshCw} busy={busy} onClick={onCheck}>
            تحقّق الآن
          </Button>
        ) : null}
      </div>
    </CampaignFrame>
  )
}

/* ── النصّ المقترح ───────────────────────────────────────────────── */

export function ProposalScreen({ campaign, versionsMax, busy, onStart, onEnd, onBack, onCancel }: {
  campaign: Campaign
  versionsMax: number
  busy: boolean
  onStart: () => void
  onEnd: () => void
  onBack: () => void
  onCancel: () => void
}) {
  const { size } = useSize()
  const copy = campaign.copy
  if (!copy) return null
  const approved = campaign.status === "COPY_APPROVED"
  const canEdit = campaign.versions_left > 0
  const warnings = copy.warnings.length
    ? `تحقّق من هذه العبارة قبل الموافقة: ${copy.warnings.map((w) => WARNING_LABELS[w] ?? w).join("، ")}`
    : null
  const note = copy.assistant_note ? `${PERSONA}: ${copy.assistant_note}` : null
  const status = approved
    ? "تمّت الموافقة على هذا النص."
    : size === "gaze"
      ? `النسخة ${copy.version} من ${versionsMax} · لم توافق عليه بعد`
      : `نصٌّ مقترحٌ آلياً — لم توافق عليه بعد · النسخة ${copy.version} من ${versionsMax}`
  // بلا نسخٍ متبقية يبقى الرجوع إلى نسخةٍ سابقة ممكناً من شاشة التعديل.
  const start = approved ? (
    <Button id="proposal-start" commit busy={busy} icon={Undo2} onClick={onStart}>
      تراجع عن الموافقة
    </Button>
  ) : (
    <Button id="proposal-start" icon={SquarePen} disabled={!(canEdit || copy.can_restore_previous || copy.can_restore_newest)} onClick={onStart}>
      {canEdit ? "اطلب تعديلاً" : "نسخةٌ سابقة"}
    </Button>
  )
  const end = approved ? (
    <Button id="proposal-end" variant="secondary" iconEnd={NextIcon} onClick={onEnd}>
      تابع إلى الميزانية
    </Button>
  ) : (
    <Button id="proposal-end" variant="primary" commit busy={busy} icon={Check} onClick={onEnd}>
      أوافق على النص
    </Button>
  )
  return (
    <CampaignFrame
      step={1}
      title="النصّ المقترح"
      description={<span id="proposal-status">{status}</span>}
      back={{ id: "proposal-back", label: "رجوع", onClick: onBack }}
      end={{ id: "proposal-cancel", label: "ألغِ الحملة", danger: true, icon: XCircle, onClick: onCancel }}
      actions={<Slots actions start={start} end={end} />}
    >
      {size === "gaze" ? (
        // الحجم الكبير: العنوان والوصف والتنبيه والملاحظة صفحاتٌ تُقرأ كلّها؛ والصورة اختارها صاحبها للتوّ.
        <div id="proposal-copy" className="flex min-h-0 flex-col">
          {/* 150 حرفاً في الصفحة تتّسع في 320×635 و375×635 بالحجم الكبير بلا قصٍّ بأطول نصٍّ تقبله القواعد
              (test_the_longest_valid_copy_is_read_whole_before_approval)، و90 في الشاشة القصيرة. */}
          <PagedText
            key={copy.version_id}
            label="النصّ المقترح"
            text={[copy.title, copy.description, warnings, note].filter(Boolean).join("\n")}
            perPage={{ gaze: 150, gazeShort: 90 }}
          />
        </div>
      ) : (
        <div id="proposal-copy" className="flex flex-col gap-tg">
          <div className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad shadow-card">
            <Headline campaign={campaign} title={copy.title} prefix="proposal" />
            <p id="proposal-description" className="text-flow whitespace-pre-line">
              {copy.description}
            </p>
            {warnings ? (
              <p id="proposal-warnings" className="text-small font-semibold text-warning">
                {warnings}
              </p>
            ) : null}
          </div>
          {copy.assistant_note ? (
            <Alert id="proposal-note" tone="info" title={PERSONA}>
              {copy.assistant_note}
            </Alert>
          ) : null}
        </div>
      )}
    </CampaignFrame>
  )
}

/* ── طلب التعديل ─────────────────────────────────────────────────── */

export function EditScreen({ campaign, edit, presets, presetsMax, conflictOf, busy, onToggle, onNote, onRestore, onSubmit, onBack }: {
  campaign: Campaign
  edit: EditState
  presets: string[]
  presetsMax: number
  conflictOf: (preset: string) => string | null
  busy: boolean
  onToggle: (preset: string) => void
  onNote: () => void
  onRestore: (target: "previous" | "newest") => void
  onSubmit: () => void
  onBack: () => void
}) {
  const copy = campaign.copy
  if (!copy) return null
  const exhausted = campaign.versions_left <= 0
  const full = edit.presets.length >= presetsMax
  // «النسخة الأحدث» تُلغي «النسخة السابقة»: ضغطةٌ خاطئة لا تُفقد نسخة.
  const newest = copy.can_restore_newest
  const left = exhausted
    ? "بلغت الحملة حدّ النسخ؛ يمكن الرجوع إلى نسخةٍ سابقة."
    : full
      ? "ثلاثة تعديلاتٍ على الأكثر"
      : `النسخ المتبقية: ${campaign.versions_left}`
  // المختار يُسمّى: في الحجم الكبير قد يكون خيارٌ مختارٌ في الصفحة الأخرى من الخيارات.
  const chosen = edit.presets.map((preset) => PRESET_LABELS[preset] ?? preset).join("، ")
  return (
    <CampaignFrame
      step={1}
      title="ما التعديل الذي تريده؟"
      description={
        <span id="edit-left">
          {left}
          {chosen ? ` · المختار: ${chosen}` : ""}
        </span>
      }
      back={{ id: "edit-back", label: "رجوع", onClick: onBack }}
      // «النسخة السابقة» في أعلى الشاشة لا أسفلها: «الانتقال إلى العنصر» ينقل النظر الباقي إلى أقرب
      // عنصر، فأقرب ما إلى «اطلب تعديلاً» (أسفل شاشة المقترح) هنا خيارٌ أو «ملاحظة نصية»، لا ما يعتمد.
      end={{
        id: "edit-restore",
        label: newest ? "النسخة الأحدث" : "النسخة السابقة",
        commit: true,
        icon: History,
        disabled: !(newest || copy.can_restore_previous),
        busy,
        onClick: () => onRestore(newest ? "newest" : "previous"),
      }}
      actions={
        <Slots
          actions
          // بلا نسخٍ متبقية يصير الزرّ «عُد إلى النص»: الوصول هنا من «نسخةٌ سابقة» في موضعه.
          start={
            exhausted ? (
              <Button id="edit-submit" icon={BackIcon} onClick={onSubmit}>
                عُد إلى النص
              </Button>
            ) : (
              <Button
                id="edit-submit"
                variant="primary"
                commit
                busy={busy}
                disabled={!(edit.armed && (edit.presets.length > 0 || Boolean(edit.note)))}
                onClick={onSubmit}
              >
                اطلب نسخة جديدة
              </Button>
            )
          }
          end={
            <Button id="edit-note" icon={MessageSquareText} disabled={exhausted} onClick={onNote}>
              {edit.note ? "ملاحظة نصية (مكتوبة)" : "ملاحظة نصية"}
            </Button>
          }
        />
      }
    >
      {/* مجموعة متعدّدة الاختيار: كل خيارٍ يُبدَّل وحده، وأثره في مكانه. */}
      <ChoiceGroup
        id="edit-chips"
        label="التعديلات، حتى ثلاثة"
        otherLabel="تعديلاتٌ أخرى"
        firstLabel="التعديلات الأولى"
        items={presets.map((preset) => {
          const on = edit.presets.includes(preset)
          const conflict = conflictOf(preset)
          return {
            key: preset,
            label: PRESET_LABELS[preset] ?? preset,
            pressed: on,
            disabled: exhausted || (!on && (full || (conflict !== null && edit.presets.includes(conflict)))),
            onPress: () => onToggle(preset),
          }
        })}
      />
    </CampaignFrame>
  )
}

/* ── الملاحظة ────────────────────────────────────────────────────── */

export function NoteScreen({ text, max, onChange, onSave, onBack }: {
  text: string
  max: number
  onChange: (text: string) => void
  onSave: () => void
  onBack: () => void
}) {
  return (
    <CampaignFrame
      step={1}
      title={`ملاحظة لـ${PERSONA}`}
      back={{ id: "note-back", label: "رجوع", onClick: onBack }}
      // «احفظ الملاحظة» في خانة النهاية: تحتها في شاشة التعديل «ملاحظة نصية» لا «اطلب نسخة جديدة».
      actions={
        <Slots
          actions
          end={
            <Button id="note-save" variant="secondary" icon={Save} onClick={onSave}>
              احفظ الملاحظة
            </Button>
          }
        />
      }
    >
      <Field id="note-text" label={`اختيارية، حتى ${max} حرف`} hint="اكتب ما يخصّ المنتج فقط، بلا بياناتٍ شخصية أو صحية.">
        <Textarea value={text} maxLength={max} autoComplete="off" onChange={(event) => onChange(event.currentTarget.value)} />
      </Field>
      <p id="note-count" role="status" className="text-small text-muted-foreground">
        الأحرف المتبقية: <span className="num">{max - text.length}</span>
      </p>
    </CampaignFrame>
  )
}

/* ── الميزانية والمدّة ───────────────────────────────────────────── */

export function ValueScreen({ kind, campaign, table, busy, onPick, onNext, onBack }: {
  kind: "budget" | "days"
  campaign: Campaign
  table: BudgetTable | DaysTable
  busy: boolean
  onPick: (value: number) => void
  onNext: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const budget = kind === "budget"
  const rows = budget
    ? (table as BudgetTable).values.map((v) => ({ value: v.sar, short: v.short, words: v.words }))
    : (table as DaysTable).values.map((v) => ({ value: v.n, short: v.short, words: v.words }))
  const values = rows.map((row) => row.value)
  const current = budget ? (campaign.budget ? campaign.budget.sar : null) : campaign.days ? campaign.days.n : null
  // الميزانية بأرقامها وحدها في الأزرار (الوحدة في العنوان)، والمدّة بكلمتها («15 يوماً»).
  const label = (value: number) => (budget ? value.toLocaleString("en-US") : (rows.find((row) => row.value === value)?.short ?? String(value)))
  const neighbour = (delta: 1 | -1): number | null => {
    if (current === null) return delta > 0 ? values[0] : null
    const index = values.indexOf(current) + delta
    return index >= 0 && index < values.length ? values[index] : null
  }
  const down = neighbour(-1)
  const up = neighbour(1)
  const words = budget
    ? campaign.budget
      ? `الميزانية الإجمالية: ${campaign.budget.words}`
      : "لم تُحدَّد الميزانية بعد."
    : campaign.days
      ? `المدة: ${campaign.days.words}`
      : "لم تُحدَّد المدة بعد."
  const short = budget ? campaign.budget?.short : campaign.days?.short
  const daily = budget ? "" : dailyText(campaign)
  return (
    <CampaignFrame
      step={budget ? 2 : 3}
      title={budget ? "الميزانية بالريال" : "عدد الأيام"}
      back={{ id: `${kind}-back`, label: "رجوع", onClick: onBack }}
      // «التالي» في خانة النهاية العلوية: ما يقع تحت «تابع إلى الميزانية» و«التالي: عدد الأيام» في
      // الشاشة التالية إمّا «أقل» معطّلةٌ (لا قيمة بعد) أو «التالي» معطّلة.
      end={{
        id: `${kind}-next`,
        // في الحجم الكبير «التالي» وحدها: الخانة 120px في أضيق هاتف، والوجهة في سطر الخطوة.
        label: size === "gaze" ? "التالي" : budget ? "التالي: عدد الأيام" : "التالي: المراجعة",
        iconEnd: NextIcon,
        disabled: current === null,
        onClick: onNext,
      }}
      actions={
        <Slots
          actions
          start={
            <Button id={`${kind}-up`} isValue icon={Plus} disabled={up === null || busy} data-value={up === null ? "" : String(up)} onClick={() => up !== null && onPick(up)}>
              {up === null ? "أكثر" : `أكثر: ${label(up)}`}
            </Button>
          }
          end={
            <Button id={`${kind}-down`} isValue icon={Minus} disabled={down === null || busy} data-value={down === null ? "" : String(down)} onClick={() => down !== null && onPick(down)}>
              {down === null ? "أقل" : `أقل: ${label(down)}`}
            </Button>
          }
        />
      }
    >
      {/* الكلمات بعد العنوان والنقطتين — موضع الرفع — والأرقام بعدها، كما في المراجعة. */}
      <div id={`${kind}-value`} aria-live="polite" className="flex flex-col gap-1 rounded-card border border-border bg-card px-pad py-3 shadow-card gaze:border-0 gaze:bg-transparent gaze:px-0 gaze:py-0 gaze:shadow-none">
        {/* سطران محجوزان دائماً: اختيار قيمةٍ لا يحرّك الخيارات تحت نظرٍ باقٍ على الضغطة. */}
        <p className="min-h-[3.2em] text-flow gaze:short:text-small">
          {words}
          {short ? (
            <>
              {" ("}
              <bdi className="num font-semibold text-heading">{short}</bdi>
              {")"}
            </>
          ) : null}
          {daily ? (
            // سطرٌ ثانٍ في الحجم العادي، وفي الكبير في السطر نفسه: الشاشة القصيرة لا تتّسع لسطرٍ ثالث.
            <>
              <br className="gaze:hidden" />
              <span className="hidden gaze:inline"> · </span>
              <span className="text-small text-muted-foreground">{daily}</span>
            </>
          ) : null}
        </p>
      </div>
      <ChoiceGroup
        id={`${kind}-presets`}
        label={budget ? "مبالغ جاهزة" : "مُدَدٌ جاهزة"}
        otherLabel={budget ? "مبالغ أخرى" : "مُدَدٌ أخرى"}
        firstLabel={budget ? "المبالغ الأولى" : "المُدَد الأولى"}
        numeric
        items={table.presets.map((value) => ({
          key: String(value),
          label: budget ? value.toLocaleString("en-US") : label(value),
          pressed: value === current,
          disabled: busy,
          onPress: () => onPick(value),
        }))}
      />
    </CampaignFrame>
  )
}

/* ── المراجعة والتأكيد ───────────────────────────────────────────── */

/** بطاقة الملخّص (المراجعة والجاهزة): حدٌّ شعرة وظلٌّ خفيف في الحجم العادي، وبلا إطارٍ في الكبير. */
function SummaryCard({ children }: { children: React.ReactNode }) {
  // بين أسطرها فجوة نصّين لا فجوة هدفين: لا هدف فيها.
  return <div className="flex min-h-0 flex-col gap-tg-min rounded-card border border-border bg-card p-pad shadow-card gaze:border-0 gaze:bg-transparent gaze:p-0 gaze:shadow-none">{children}</div>
}

function Line({ id, label, words, digits }: { id: string; label: string; words: string; digits: string }) {
  // الكلمات بعد العنوان والنقطتين مباشرةً — موضع الرفع — والأرقام بعدها.
  return (
    <p id={id} className="text-flow">
      {label}: {words} (<bdi className="num">{digits}</bdi>)
    </p>
  )
}

export function ReviewScreen({ campaign, onContinue, onBack, onCancel }: {
  campaign: Campaign
  onContinue: () => void
  onBack: () => void
  onCancel: () => void
}) {
  const copy = campaign.copy
  if (!copy || !campaign.budget || !campaign.days) return null
  return (
    <CampaignFrame
      step={4}
      title="راجِع قبل الاعتماد"
      back={{ id: "review-back", label: "رجوع", onClick: onBack }}
      end={{ id: "review-cancel", label: "ألغِ الحملة", danger: true, icon: XCircle, onClick: onCancel }}
      actions={
        <Slots
          actions
          start={
            <Button id="review-continue" variant="secondary" iconEnd={NextIcon} onClick={onContinue}>
              متابعة للتأكيد
            </Button>
          }
        />
      }
    >
      <SummaryCard>
        <Headline campaign={campaign} title={copy.title} prefix="review" />
        <p id="review-description" className="text-flow whitespace-pre-line gaze:line-clamp-2">
          {copy.description}
        </p>
        <div className="flex flex-col gap-1 border-t border-border pt-tg-min">
          <Line id="review-budget" label="الميزانية الإجمالية" words={campaign.budget.words} digits={campaign.budget.short} />
          <Line id="review-days" label="المدة" words={campaign.days.words} digits={campaign.days.short} />
          <p id="review-daily" className="text-flow">
            {dailyText(campaign)}
          </p>
        </div>
      </SummaryCard>
    </CampaignFrame>
  )
}

export function ConfirmScreen({ campaign, busy, onYes, onBack }: { campaign: Campaign; busy: boolean; onYes: () => void; onBack: () => void }) {
  if (!campaign.budget || !campaign.days) return null
  return (
    // الخانة التي ضُغط فيها «متابعة للتأكيد» نصٌّ هنا: نظرةٌ باقية لا تعتمد شيئاً.
    <CampaignFrame
      step={null}
      title="تأكيدٌ نهائي"
      actions={<Slots start={<p className="self-center text-center text-small text-muted-foreground">لن يُنشر شيءٌ تلقائياً</p>} />}
    >
      <Button id="confirm-yes" variant="primary" size="lg" width="full" commit busy={busy} icon={Check} onClick={onYes}>
        نعم، اعتمد الحملة
      </Button>
      <p id="confirm-restate" className="text-flow">
        الميزانية الإجمالية: {campaign.budget.words}. المدة: {campaign.days.words}. لن يُنشر شيءٌ ولن يُدفع أيّ مبلغٍ تلقائياً، ولا يمكن تعديل الحملة بعد اعتمادها.
      </p>
      <Button id="confirm-back" width="full" icon={BackIcon} onClick={onBack}>
        رجوع دون اعتماد
      </Button>
    </CampaignFrame>
  )
}

/* ── الإلغاء والسحب ──────────────────────────────────────────────── */

export function CancelScreen({ withdraw, busy, onYes, onBack }: { withdraw: boolean; busy: boolean; onYes: () => void; onBack: () => void }) {
  return (
    <CampaignFrame
      step={null}
      title={withdraw ? "سحب الحملة" : "إلغاء الحملة"}
      actions={
        <Slots
          actions
          start={
            <Button id="cancel-yes" variant="danger" commit busy={busy} icon={Trash2} onClick={onYes}>
              {withdraw ? "نعم، اسحب الحملة" : "نعم، ألغِ الحملة"}
            </Button>
          }
        />
      }
    >
      <p className="text-flow">ستُحذف صورة الحملة فوراً، ولا يمكن التراجع عن الإلغاء.</p>
      <Button id="cancel-back" width="full" icon={BackIcon} onClick={onBack}>
        رجوع دون إلغاء
      </Button>
    </CampaignFrame>
  )
}

/* ── جاهزة للتسليم ───────────────────────────────────────────────── */

export function ReadyScreen({ campaign, shareEnabled, status, downloadOffered, onCopyTitle, onCopyDescription, onShare, onHome, onWithdraw }: {
  campaign: Campaign
  shareEnabled: boolean
  status: string
  /** في التطبيق المضاف إلى الشاشة الرئيسية لا يُعرض التنزيل (WebKit 290847)، ويبقى مكانه. */
  downloadOffered: boolean
  onCopyTitle: () => void
  onCopyDescription: () => void
  onShare: () => void
  onHome: () => void
  onWithdraw: () => void
}) {
  const { size } = useSize()
  const copy = campaign.copy
  if (!copy || !campaign.budget || !campaign.days) return null
  return (
    <CampaignFrame
      step={null}
      title={size === "gaze" ? "جاهزة للتسليم" : "الحملة جاهزة للتسليم"}
      description={<span className="gaze:short:hidden">لم يُنشر شيءٌ ولم يُدفع أيّ مبلغ. انسخ النصّ أو شاركه مع من سينشر الحملة.</span>}
      back={{ id: "ready-home", label: "الرئيسية", icon: House, onClick: onHome }}
      end={{ id: "ready-withdraw", label: "اسحب الحملة", danger: true, icon: XCircle, onClick: onWithdraw }}
      actions={
        <Slots
          actions
          start={
            <Button id="ready-share" icon={Share2} disabled={!shareEnabled} onClick={onShare}>
              شارك الحملة
            </Button>
          }
          end={
            downloadOffered ? (
              <ButtonLink id="ready-download" icon={Download} href={imageUrl(campaign)} download="campaign.jpg">
                نزّل الصورة
              </ButtonLink>
            ) : undefined
          }
        />
      }
    >
      <SummaryCard>
        <Headline campaign={campaign} title={copy.title} prefix="ready" />
        <p id="ready-description" className="text-flow line-clamp-2 whitespace-pre-line gaze:short:line-clamp-1">
          {copy.description}
        </p>
        <p id="ready-summary" className="text-flow border-t border-border pt-tg-min">
          <bdi className="num">{`${campaign.budget.short} · ${campaign.days.short}`}</bdi>
        </p>
      </SummaryCard>
      <Slots
        start={
          <Button id="ready-copy-title" onClick={onCopyTitle}>
            انسخ العنوان
          </Button>
        }
        end={
          <Button id="ready-copy-description" onClick={onCopyDescription}>
            انسخ الوصف
          </Button>
        }
      />
      <p id="ready-status" role="status" className="text-small text-muted-foreground empty:hidden">
        {status}
      </p>
    </CampaignFrame>
  )
}

/* ── حملاتي ──────────────────────────────────────────────────────── */

/** صفوف «حملاتي»: زرٌّ من جزأين يُصاب كلّه (ما تحت المؤشر هو الزرّ لا جزؤه)؛ العنوان سطرٌ أو أكثر
 *  بعرض الزرّ والحالة تحته، فلا يضيق العنوان بجانب الشارة في أضيق إطار. والحملة المفتوحة (في
 *  القائمة بجانب الحملة) بالتدرّج الثانوي و`aria-current`. */
export function CampaignRows({ items, names, currentId = null, onOpen }: {
  items: CampaignListItem[]
  names: string[]
  currentId?: string | null
  onOpen: (item: CampaignListItem) => void
}) {
  return (
    <ul id="campaigns-list" aria-label="حملاتي" className="flex flex-col gap-tg">
      {items.map((item, index) => {
        const current = item.id === currentId
        return (
          <li key={item.id}>
            <button
              type="button"
              data-safe=""
              aria-current={current ? "true" : undefined}
              onClick={() => onOpen(item)}
              className={cn(
                "flex min-h-ctl w-full flex-col items-start justify-center gap-1 rounded-card border px-pad py-2 text-start font-semibold",
                current ? "border-primary-line bg-secondary text-secondary-foreground" : "border-control bg-card text-foreground hov:bg-muted",
              )}
            >
              <span className="min-w-0 leading-snug">{names[index]}</span>
              <Badge tone={item.status === "READY" ? "success" : item.status === "COPY_APPROVED" ? "info" : "neutral"} className="row-status pointer-events-none">
                {STATUS_LABELS[item.status] ?? ""}
              </Badge>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

/** «حملاتي» بجانب الحملة في العريض بحجم اللمس: الصفحة الأولى، والقائمة كلّها من «حملاتي» في الشريط الجانبي. */
export function CampaignsPane({ items, currentId, onOpen }: {
  items: CampaignListItem[]
  currentId: string
  onOpen: (item: CampaignListItem) => void
}) {
  return (
    <section aria-labelledby="campaigns-pane-title" className="flex flex-col gap-tg">
      <h2 id="campaigns-pane-title" className="flex min-h-ctl items-center text-lead font-semibold">
        حملاتي
      </h2>
      {items.length ? <CampaignRows items={items} names={rowNames(items, 0)} currentId={currentId} onOpen={onOpen} /> : null}
    </section>
  )
}

/* ── حملاتي ──────────────────────────────────────────────────────── */

export function CampaignsScreen({ items, page, pageSize, hasMore, installHint, onOpen, onOlder, onNewer, onNew }: {
  items: CampaignListItem[] | null
  page: number
  pageSize: number
  hasMore: boolean
  /** التلميح يظهر حين يتّسع له المكان: صفّان يملآن الشاشة بلا تمرير. */
  installHint: boolean
  onOpen: (item: CampaignListItem) => void
  onOlder: () => void
  onNewer: () => void
  onNew: () => void
}) {
  const names = items ? rowNames(items, (page - 1) * pageSize) : []
  return (
    <Screen
      title="حملاتي"
      actions={
        <Slots
          actions
          start={
            <Button id="campaigns-newer" icon={BackIcon} disabled={page <= 1} onClick={onNewer}>
              الأحدث
            </Button>
          }
          end={
            <Button id="campaigns-older" iconEnd={NextIcon} disabled={!hasMore} onClick={onOlder}>
              الأقدم
            </Button>
          }
        />
      }
    >
      {items === null ? null : items.length === 0 && page <= 1 ? (
        <EmptyState
          icon={SquarePen}
          title="لا حملات بعد."
          action={
            <Button id="campaigns-new" variant="primary" icon={SquarePen} onClick={onNew}>
              حملة جديدة
            </Button>
          }
        />
      ) : (
        <CampaignRows items={items} names={names} onOpen={onOpen} />
      )}
      {installHint ? (
        <p id="campaigns-install" className="text-small text-muted-foreground">
          يمكن لمن يساعدك إضافة التطبيق إلى الشاشة الرئيسية من قائمة المشاركة في Safari.
        </p>
      ) : null}
    </Screen>
  )
}
