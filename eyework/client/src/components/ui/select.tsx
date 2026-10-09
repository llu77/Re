/*
 * Select — اختيارٌ من قائمةٍ قصيرة
 * ===============================
 * الأصل: shadcn/ui select (MIT) بلا Radix (يفتح عند pointerdown ويضيف <style>)، بنمط
 * ARIA APG «combobox للاختيار وحده»:
 *   • الزرّ role="combobox" وaria-expanded وaria-controls؛ والقائمة role="listbox"
 *     وخياراتها role="option" وaria-selected؛ والخيار النشط بـaria-activedescendant،
 *     فيبقى التركيز على الزرّ.
 *   • لوحة المفاتيح: الأسهم وHome وEnd تنقل، وEnter أو المسافة تختار، وEscape يغلق.
 *   • الضغط وحده يفتح ويختار: لا تحويم. وكل خيارٍ هدفٌ بارتفاع `h-ctl` وبينه وبين
 *     التالي `gap-tg-min`.
 *   • القائمة لقيمٍ قليلة (وحدات القياس، طرق الدفع). وما يُبحث فيه Combobox.
 */

import * as React from "react"
import { Check, ChevronDown } from "lucide-react"

import { useFieldControl } from "@/components/ui/input"
import { step, useOutsideClick } from "@/components/ui/popover"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps {
  options: SelectOption[]
  value: string | null
  onValueChange: (value: string) => void
  /** ما يظهر قبل الاختيار: نصٌّ داخل الزرّ، والتسمية فوقه في `Field`. */
  emptyLabel?: string
  disabled?: boolean
  /** مفتوحةٌ من أولها (صفحة العرض). */
  defaultOpen?: boolean
  className?: string
}

export function Select({ options, value, onValueChange, emptyLabel = "اختر", disabled, defaultOpen = false, className }: SelectProps) {
  const control = useFieldControl()
  const { size } = useSize()
  const [open, setOpen] = React.useState(defaultOpen)
  const [active, setActive] = React.useState(-1)
  const root = React.useRef<HTMLDivElement>(null)
  const trigger = React.useRef<HTMLButtonElement>(null)
  const listId = React.useId()
  const valueId = React.useId()
  const selected = options.find((option) => option.value === value) ?? null

  useOutsideClick(open, root, () => setOpen(false))

  function show() {
    setOpen(true)
    setActive(Math.max(0, options.findIndex((option) => option.value === value)))
  }

  function choose(index: number) {
    const option = options[index]
    if (!option) return
    onValueChange(option.value)
    setOpen(false)
    trigger.current?.focus()
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault()
        show()
      }
      return
    }
    const moves: Record<string, () => number> = {
      ArrowDown: () => step(active, 1, options.length),
      ArrowUp: () => step(active, -1, options.length),
      Home: () => 0,
      End: () => options.length - 1,
    }
    if (moves[event.key]) {
      event.preventDefault()
      setActive(moves[event.key]())
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      choose(active)
    } else if (event.key === "Escape" || event.key === "Tab") {
      if (event.key === "Escape") event.preventDefault()
      setOpen(false)
    }
  }

  return (
    <div ref={root} className={cn("relative", className)}>
      <button
        ref={trigger}
        type="button"
        role="combobox"
        {...control}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        disabled={disabled}
        data-safe=""
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
        className={cn(
          "flex min-h-ctl w-full items-center justify-between gap-2 rounded-ctl border-2 border-control bg-card px-3 text-start text-body shadow-ctl",
          "disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground",
          open && "border-primary",
        )}
      >
        <span id={valueId} className={cn("truncate", !selected && "text-muted-foreground")}>
          {selected ? selected.label : emptyLabel}
        </span>
        <ChevronDown aria-hidden="true" className={cn("size-icon shrink-0 text-muted-foreground", open && "rotate-180")} />
      </button>
      {open ? (
        <ul
          id={listId}
          role="listbox"
          className={cn(
            "z-30 flex flex-col gap-tg-min rounded-card border border-border bg-card p-2 shadow-pop",
            size === "gaze" ? "mt-tg" : "absolute inset-x-0 top-full mt-tg-min",
          )}
        >
          {options.map((option, index) => {
            const isSelected = option.value === value
            return (
              <li
                key={option.value}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={isSelected}
                data-value=""
                onClick={() => choose(index)}
                className={cn(
                  "flex min-h-ctl cursor-default items-center justify-between gap-2 rounded-ctl border-2 px-3",
                  index === active ? "border-primary bg-secondary" : "border-transparent",
                  isSelected && "font-bold",
                )}
              >
                {option.label}
                {isSelected ? <Check aria-hidden="true" className="size-icon text-primary" /> : null}
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
