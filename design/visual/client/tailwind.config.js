/** @type {import('tailwindcss').Config} */

// ألوان shadcn بأسمائها (HSL في متغيّرات CSS) — فيعمل مكوّنٌ من 21st.dev أو من سجلّ
// shadcn بلا تعديلٍ في أسماء ألوانه — وفوقها رموز صياغة: حدود الأهداف، والعناوين،
// والنجاح. القيم في src/styles/globals.css، ومعها «زيادة التباين» والوضع الداكن.
const token = (name) => `hsl(var(--${name}) / <alpha-value>)`

export default {
  // الوضع الداكن يتبع النظام وحده: زرُّ تبديلٍ هدفٌ آخر في كل شاشة.
  darkMode: "media",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // متغيّر `hover:` في مكوّنٍ مستورد لا يعمل إلا بمؤشّرٍ يعرف المرور (لا لمس ولا نظر).
  future: { hoverOnlyWhenSupported: true },
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
      },
      fontSize: {
        // ثابتةٌ بالجذر: الأزرار والأشرطة لا تتبع «حجم النصّ».
        control: ["var(--fs-body)", { lineHeight: "1.3" }],
        // نسبيّةٌ داخل `.content`: تكبر مع المتن حتى السقف وتحفظ ترتيبها.
        small: ["var(--text-small)", { lineHeight: "1.5" }],
        body: ["1em", { lineHeight: "var(--line-height)" }],
        title: ["var(--text-title)", { lineHeight: "1.35" }],
        value: ["var(--text-value)", { lineHeight: "1.25" }],
        display: ["var(--text-display)", { lineHeight: "1.3" }],
      },
      spacing: {
        target: "var(--target)",
        gap: "var(--target-gap)",
        edge: "var(--edge)",
      },
      minHeight: { target: "var(--target)" },
      minWidth: { target: "var(--target)" },
      borderRadius: {
        control: "var(--radius)",
        card: "var(--radius-card)",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
      },
      boxShadow: {
        control: "var(--shadow-control)",
        card: "var(--shadow-card)",
      },
      colors: {
        border: token("border"),
        input: token("input"),
        ring: token("ring"),
        background: token("background"),
        foreground: token("foreground"),
        heading: token("heading"),
        control: token("control"),
        primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
        secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
        destructive: {
          DEFAULT: token("destructive"),
          foreground: token("destructive-foreground"),
          tint: token("destructive-tint"),
        },
        success: { DEFAULT: token("success"), tint: token("success-tint") },
        muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
        accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
        popover: { DEFAULT: token("popover"), foreground: token("popover-foreground") },
        card: { DEFAULT: token("card"), foreground: token("card-foreground") },
        gaze: token("gaze"),
      },
    },
  },
  plugins: [],
}
