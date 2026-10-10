import animate from "tailwindcss-animate"
import plugin from "tailwindcss/plugin"

/*
 * كل بُعدٍ يتغيّر بين الحجمين متغيّرٌ في CSS (src/styles/globals.css)، والأداة تقرؤه:
 *   h-ctl / min-h-ctl / size-ctl   الهدف (44 أو 72)
 *   gap-tg / gap-tg-min            بين هدفين (12 أو 24) وأقلّه (8 أو 24)
 *   px-edge                        الحافّة (16)
 *   p-pad / gap-sec                حشو البطاقة وبين الأقسام
 *   size-icon / size-fab / h-bar   الأيقونة والزرّ العائم والرأس
 *   text-small … text-display      درجات الخطّ
 * فتبديل `data-size` على <html> يبدّل الواجهة كلّها بلا إعادة رسمٍ من React.
 *
 * والمتغيّرات `gaze:` و`compact:` لما يختلف شكلاً لا قياساً (جدولٌ أو قائمة).
 * و`hov:` بدل `hover:`: لونٌ يتغيّر تحت فأرةٍ في الحجم العادي وحده، لا تحت النظر ولا
 * اللمس، ولا يُظهر شيئاً لا يظهر بغيره (اختبار المصدر يرفض `hover:`).
 */
const hsl = (name) => `hsl(var(--${name}) / <alpha-value>)`

const sizes = {
  ctl: "var(--ctl)",
  "ctl-lg": "var(--ctl-lg)",
  tg: "var(--tg)",
  "tg-min": "var(--tg-min)",
  edge: "var(--edge)",
  sec: "var(--sec)",
  pad: "var(--pad)",
  icon: "var(--icon)",
  fab: "var(--fab)",
  row: "var(--row)",
  bar: "var(--bar)",
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./demo.html", "./src/**/*.{ts,tsx}"],
  future: { hoverOnlyWhenSupported: true },
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-body)"],
        num: ["var(--font-num)"],
      },
      fontSize: {
        small: ["var(--fs-small)", { lineHeight: "var(--lh-small)" }],
        body: ["var(--fs-body)", { lineHeight: "var(--lh-body)" }],
        lead: ["var(--fs-lead)", { lineHeight: "var(--lh-lead)" }],
        title: ["var(--fs-title)", { lineHeight: "var(--lh-title)" }],
        display: ["var(--fs-display)", { lineHeight: "var(--lh-display)" }],
        value: ["var(--fs-value)", { lineHeight: "1.2" }],
      },
      spacing: sizes,
      minHeight: sizes,
      minWidth: sizes,
      maxWidth: { content: "var(--content-max)" },
      borderRadius: {
        ctl: "var(--radius)",
        card: "var(--radius-card)",
        pill: "999px",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
        ctl: "var(--shadow-ctl)",
      },
      colors: {
        background: hsl("background"),
        foreground: hsl("foreground"),
        heading: hsl("heading"),
        card: { DEFAULT: hsl("card"), foreground: hsl("foreground") },
        primary: { DEFAULT: hsl("primary"), foreground: hsl("primary-foreground") },
        secondary: { DEFAULT: hsl("secondary"), foreground: hsl("secondary-foreground") },
        muted: { DEFAULT: hsl("muted"), foreground: hsl("muted-foreground") },
        destructive: { DEFAULT: hsl("destructive"), foreground: hsl("primary-foreground"), tint: hsl("destructive-tint") },
        success: { DEFAULT: hsl("success"), tint: hsl("success-tint") },
        warning: { DEFAULT: hsl("warning"), tint: hsl("warning-tint"), line: hsl("warning-line") },
        ai: { DEFAULT: hsl("ai"), tint: hsl("ai-tint") },
        border: hsl("border"),
        control: { DEFAULT: hsl("control"), strong: hsl("control-strong") },
        ring: hsl("ring"),
      },
    },
  },
  plugins: [
    animate,
    plugin(({ addVariant }) => {
      addVariant("gaze", ':root[data-size="gaze"] &')
      addVariant("compact", ':root:not([data-size="gaze"]) &')
      addVariant("short", "@media (max-height: 43.75rem)")
      addVariant("hov", '@media (hover: hover) and (pointer: fine) { :root:not([data-size="gaze"]) &:hover }')
    }),
  ],
}
