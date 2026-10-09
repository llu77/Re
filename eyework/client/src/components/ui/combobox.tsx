/*
 * Combobox — ابحث، أو اختر، أو أنشئ
 * =================================
 * «المنسدل» الذي طلبه المالك للأصناف والقطع: يكتب الموظف بعض الاسم أو الرمز فتظهر
 * المطابقات، فيختار واحداً؛ أو يضغط «أنشئ صنفاً جديداً: …» في آخر القائمة فيفتح المضيف
 * نموذج الصنف بسعره تحت الحقل.
 *
 * الأصل: shadcn/ui combobox (Popover + Command) — والمبدأ لا الشيفرة، بنمط ARIA APG
 * «combobox قابلٌ للكتابة بقائمة اقتراحات» (list autocomplete):
 *   • الحقل role="combobox" وaria-autocomplete="list" وaria-expanded وaria-controls،
 *     والخيار النشط بـaria-activedescendant؛ فيبقى التركيز في الحقل.
 *   • الأسهم تنقل، وEnter يختار، وEscape يغلق ثم يمحو؛ وPageDown وPageUp بين الصفحات.
 *   • لا تمرير في القائمة: صفحةٌ من المطابقات (6 في العادي، 3 في الكبير) و«التالية»
 *     و«السابقة» تحتها. والبحث للمضيف (`options` المطابقة لـ`query`): من الخادم حين
 *     تكثر الأصناف، فلا تُرسل القائمة كلّها إلى المتصفّح.
 *   • لا مستمع mousedown يحفظ التركيز في الحقل: الضغط على خيارٍ يختاره ثم يعيد
 *     التركيز إلى الحقل. والإغلاق بالضغط خارجه، أو Escape، أو الاختيار.
 *   • ما في الحقل بعد الاختيار اسم الصنف؛ وتغييره يلغي الاختيار حتى يُختار من جديد:
 *     لا يُرسل اسمٌ مكتوب كأنه صنفٌ مختار.
 */

import * as React from "react"
import { Check, ChevronDown, Plus, Search } from "lucide-react"

import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { fieldClass, useFieldControl } from "@/components/ui/input"
import { step, useOutsideClick } from "@/components/ui/popover"
import { usePageSize, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface ComboboxOption {
  value: string
  label: string
  /** سطرٌ ثانٍ: الرمز والوحدة. */
  description?: string
  /** في الطرف: السعر أو الرصيد. */
  meta?: string
}

export interface ComboboxProps {
  /** المطابقات لـ`query`، بترتيبها. */
  options: ComboboxOption[]
  value: ComboboxOption | null
  onValueChange: (option: ComboboxOption | null) => void
  query: string
  onQueryChange: (query: string) => void
  /** «… جديد باسم»: يظهر حين يُكتب ما لا يطابق اسماً بعينه. */
  onCreate?: (query: string) => void
  /** نصّ خيار الإنشاء قبل الاسم المكتوب: «صنف جديد باسم». */
  createLabel?: string
  /** موضع خيار الإنشاء: آخر القائمة (الافتراضي، inventory_spec §3.4) أو أوّلها. */
  createPosition?: "first" | "last"
  createHint?: string
  /** اسم القائمة لقارئ الشاشة: «الأصناف المطابقة». */
  listLabel: string
  pageSize?: { compact: number; gaze: number; gazeShort?: number }
  busy?: boolean
  emptyText?: string
  defaultOpen?: boolean
  /** يُبلَّغ المضيف حين تُفتح القائمة أو تُغلق (في الحجم الكبير يخفي ما تحتها). */
  onOpenChange?: (open: boolean) => void
  inputRef?: React.Ref<HTMLInputElement>
}

type Entry = { kind: "option"; option: ComboboxOption } | { kind: "create" }

export function Combobox({
  options, value, onValueChange, query, onQueryChange, onCreate, createLabel = "جديد باسم", createPosition = "last", createHint,
  listLabel, pageSize = { compact: 6, gaze: 3 }, busy = false, emptyText = "لا مطابقة.", defaultOpen = false, onOpenChange,
  inputRef,
}: ComboboxProps) {
  const control = useFieldControl()
  const { size } = useSize()
  const [open, setOpen] = React.useState(defaultOpen)
  const [active, setActive] = React.useState(-1)
  const [page, setPage] = React.useState(0)
  const root = React.useRef<HTMLDivElement>(null)
  const input = React.useRef<HTMLInputElement | null>(null)
  const listId = React.useId()

  useOutsideClick(open, root, () => setOpen(false))

  const report = React.useRef(onOpenChange)
  report.current = onOpenChange
  React.useEffect(() => {
    report.current?.(open)
  }, [open])

  const perPage = usePageSize(pageSize)
  const pages = Math.max(1, Math.ceil(options.length / perPage))
  const current = Math.min(page, pages - 1)
  const visible = options.slice(current * perPage, current * perPage + perPage)
  const trimmed = query.trim()
  const exact = options.some((option) => option.label.trim() === trimmed)
  const canCreate = Boolean(onCreate) && trimmed.length > 0 && !exact
  const create: Entry[] = canCreate ? [{ kind: "create" as const }] : []
  const found: Entry[] = visible.map((option) => ({ kind: "option" as const, option }))
  const entries: Entry[] = createPosition === "first" ? [...create, ...found] : [...found, ...create]

  function setInput(node: HTMLInputElement | null) {
    input.current = node
    if (typeof inputRef === "function") inputRef(node)
    else if (inputRef && typeof inputRef === "object") (inputRef as React.MutableRefObject<HTMLInputElement | null>).current = node
  }

  function choose(entry: Entry | undefined) {
    if (!entry) return
    setOpen(false)
    setActive(-1)
    if (entry.kind === "create") {
      onCreate?.(trimmed)
      return
    }
    onValueChange(entry.option)
    onQueryChange(entry.option.label)
    input.current?.focus()
  }

  function goToPage(next: number) {
    setPage(Math.max(0, Math.min(pages - 1, next)))
    setActive(-1)
    input.current?.focus()
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        event.preventDefault()
        if (!open) {
          setOpen(true)
          setActive(event.key === "ArrowDown" ? 0 : entries.length - 1)
        } else {
          setActive(step(active, event.key === "ArrowDown" ? 1 : -1, entries.length))
        }
        break
      }
      case "PageDown":
      case "PageUp":
        if (open) {
          event.preventDefault()
          goToPage(current + (event.key === "PageDown" ? 1 : -1))
        }
        break
      case "Enter":
        if (open && active >= 0) {
          event.preventDefault()
          choose(entries[active])
        }
        break
      case "Escape":
        if (open) {
          event.preventDefault()
          setOpen(false)
          setActive(-1)
        } else if (query) {
          event.preventDefault()
          onQueryChange("")
          onValueChange(null)
        }
        break
    }
  }

  const activeId = open && active >= 0 ? `${listId}-${active}` : undefined
  return (
    <div ref={root} className="relative">
      <div className="relative">
        <Search aria-hidden="true" className="pointer-events-none absolute inset-y-0 start-3 my-auto size-icon text-muted-foreground" />
        <input
          ref={setInput}
          type="text"
          role="combobox"
          {...control}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={activeId}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          value={query}
          onChange={(event) => {
            onQueryChange(event.target.value)
            if (value && event.target.value !== value.label) onValueChange(null)
            setOpen(true)
            setPage(0)
            setActive(-1)
          }}
          onClick={() => setOpen((shown) => !shown)}
          onKeyDown={onKeyDown}
          className={cn(fieldClass, "pe-10 ps-10 gaze:ps-12", open && "border-primary", value && "font-semibold")}
        />
        <ChevronDown
          aria-hidden="true"
          className={cn("pointer-events-none absolute inset-y-0 end-3 my-auto size-icon text-muted-foreground", open && "rotate-180")}
        />
      </div>

      {open ? (
        // في الحجم الكبير القائمة في مكانها من الصفحة لا فوقها: الشاشة لا تمرّ، فلا يُقصّ منها
        // شيءٌ تحت حدّها، والمضيف يُخفي ما كان تحت الحقل حتى تُغلق (onOpenChange).
        <div
          className={cn(
            "z-30 flex flex-col gap-tg-min rounded-card border border-border bg-card p-2 shadow-pop",
            size === "gaze" ? "mt-tg" : "absolute inset-x-0 top-full mt-tg-min",
          )}
        >
          {busy ? (
            <p role="status" className="px-2 py-1 text-small text-muted-foreground">
              يبحث…
            </p>
          ) : null}
          <ul id={listId} role="listbox" aria-label={listLabel} className="flex flex-col gap-tg-min">
            {entries.map((entry, index) => {
              const isActive = index === active
              if (entry.kind === "create") {
                return (
                  <li
                    key="__create"
                    id={`${listId}-${index}`}
                    role="option"
                    aria-selected={false}
                    data-safe=""
                    onClick={() => choose(entry)}
                    className={cn(
                      "flex min-h-ctl cursor-default items-center gap-3 rounded-ctl border-2 border-dashed px-3 py-1.5",
                      isActive ? "border-primary bg-secondary" : "border-primary/60 bg-card",
                    )}
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-ctl bg-primary text-primary-foreground gaze:size-10">
                      <Plus aria-hidden="true" className="size-4 gaze:size-5" strokeWidth={2.5} />
                    </span>
                    <span className="flex min-w-0 flex-col">
                      <span className="font-bold text-secondary-foreground">
                        {createLabel} «{trimmed}»
                      </span>
                      {createHint ? <span className="text-small text-muted-foreground gaze:short:hidden">{createHint}</span> : null}
                    </span>
                  </li>
                )
              }
              const { option } = entry
              const isSelected = value?.value === option.value
              return (
                <li
                  key={option.value}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={isSelected}
                  data-value=""
                  onClick={() => choose(entry)}
                  className={cn(
                    "flex min-h-ctl cursor-default items-center gap-3 rounded-ctl border-2 px-3 py-1.5",
                    isActive ? "border-primary bg-secondary" : "border-border bg-card",
                  )}
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-semibold">{option.label}</span>
                    {option.description ? (
                      <span className="truncate text-small text-muted-foreground gaze:short:hidden">{option.description}</span>
                    ) : null}
                  </span>
                  {option.meta ? (
                    <span className="num shrink-0 text-small font-semibold text-foreground" dir="ltr">
                      {option.meta}
                    </span>
                  ) : null}
                  {isSelected ? <Check aria-hidden="true" className="size-icon shrink-0 text-primary" /> : null}
                </li>
              )
            })}
          </ul>
          {entries.length === 0 && !busy ? <p className="px-2 py-1 text-small text-muted-foreground">{emptyText}</p> : null}
          {pages > 1 ? (
            <div className="flex items-center justify-between gap-tg border-t border-border pt-2">
              <Button icon={BackIcon} disabled={current === 0} onClick={() => goToPage(current - 1)}>
                السابقة
              </Button>
              <span className="num whitespace-nowrap text-small text-muted-foreground" aria-live="polite">
                {current * perPage + 1}–{Math.min(options.length, current * perPage + perPage)} من {options.length}
              </span>
              <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => goToPage(current + 1)}>
                التالية
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
