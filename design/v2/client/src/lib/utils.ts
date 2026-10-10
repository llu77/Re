import { type ClassValue, clsx } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/*
 * tailwind-merge لا يعرف درجات الخطّ والأبعاد المسمّاة هنا (text-body، h-ctl…)، فيظنّ
 * `text-body` لوناً ويحذف `text-foreground` معه. يُعرَّف بها ليدمج الصحيح بالصحيح.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["small", "body", "lead", "title", "display", "value"] }],
    },
    theme: {
      spacing: ["ctl", "ctl-lg", "tg", "tg-min", "edge", "sec", "pad", "icon", "fab", "row", "bar"],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
