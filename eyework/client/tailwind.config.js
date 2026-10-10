import animate from "tailwindcss-animate"
import plugin from "tailwindcss/plugin"

/*
 * كل بُعدٍ يتغيّر بين الحجمين متغيّرٌ في CSS (src/styles/globals.css)، والأداة تقرؤه:
 *   h-ctl / min-h-ctl / size-ctl   الهدف (40 أو 48)
 *   gap-tg / gap-tg-min            بين هدفين (8 أو 12)
 *   px-edge                        الحافّة (16)
 *   p-pad / gap-sec                حشو البطاقة وبين الأقسام
 *   size-icon / h-bar / h-tab      الأيقونة والصفّ العلوي وشريط التبويب
 *   w-side                         الشريط الجانبي
 *   text-small … text-display      درجات الخطّ، وtext-input للحقول (16px على الأقل)
 *   border                         شعرة (var(--line)) على كل عنصر تحكّم
 * فتبديل `data-size` على <html> يبدّل الواجهة كلّها بلا إعادة رسمٍ من React.
 *
 * الإطارات: `tablet:` (744px: iPad mini عمودياً فأوسع) يعرض الشريط الجانبي، و`lg:` (1024)
 * القائمة والتفصيل معاً، و`xl:` الحاسوب. لا `sm:` ولا `md:` (اختبار المصدر يرفضهما).
 * والمتغيّرات `gaze:` و`compact:` لما يختلف شكلاً لا قياساً، و`short:` للشاشة القصيرة (الهاتف
 * أفقياً أو لوحة المفاتيح)، و`kb:` وحقلٌ مركَّز (شريط التبويب يختفي)، و`hov:` بدل `hover:`.
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
  row: "var(--row)",
  bar: "var(--bar)",
  tab: "var(--tab)",
  header: "var(--header)",
  side: "var(--side)",
  field: "var(--field)",
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  future: { hoverOnlyWhenSupported: true },
  theme: {
    screens: {
      tablet: "744px",
      lg: "1024px",
      xl: "1280px",
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-body)"],
        num: ["var(--font-num)"],
      },
      fontSize: {
        small: ["var(--fs-small)", { lineHeight: "var(--lh-small)" }],
        body: ["var(--fs-body)", { lineHeight: "var(--lh-body)" }],
        input: ["var(--fs-input)", { lineHeight: "var(--lh-body)" }],
        lead: ["var(--fs-lead)", { lineHeight: "var(--lh-lead)" }],
        title: ["var(--fs-title)", { lineHeight: "var(--lh-title)" }],
        display: ["var(--fs-display)", { lineHeight: "var(--lh-display)" }],
        value: ["var(--fs-value)", { lineHeight: "1.2" }],
      },
      spacing: sizes,
      minHeight: sizes,
      minWidth: sizes,
      maxWidth: { content: "var(--content-max)" },
      borderWidth: { DEFAULT: "var(--line)" },
      borderRadius: {
        ctl: "var(--radius)",
        card: "var(--radius-card)",
        pill: "999px",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
      },
      colors: {
        background: hsl("background"),
        foreground: hsl("foreground"),
        heading: hsl("heading"),
        card: { DEFAULT: hsl("card"), foreground: hsl("foreground") },
        primary: { DEFAULT: hsl("primary"), foreground: hsl("primary-foreground"), line: hsl("primary-line") },
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
      addVariant("short", "@media (max-height: 30rem)")
      // لوحة المفاتيح مفتوحة (حقلٌ مركَّز): في الحجم العادي وحده، حيث الشريط السفلي ثابتٌ فوق الصفحة
      // فيركب لوحة المفاتيح؛ في الكبير الشريط في التدفّق ولا يركب شيئاً، وإخفاؤه يحرّك الأهداف تحت
      // نظرٍ باقٍ (ضغطةٌ تبدأ فوق زرٍّ وتنتهي فوق غيره).
      addVariant("kb", ':root[data-keyboard="open"]:not([data-size="gaze"]) &')
      addVariant("hov", '@media (hover: hover) and (pointer: fine) { :root:not([data-size="gaze"]) &:hover }')
    }),
  ],
}
