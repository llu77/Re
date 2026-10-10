/** @type {import('tailwindcss').Config} */
const hsl = (name) => `hsl(var(--${name}) / <alpha-value>)`

export default {
  darkMode: ["media"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
      },
      fontSize: {
        small: ["var(--text-small)", { lineHeight: "1.5" }],
        body: ["1em", { lineHeight: "var(--line-height)" }],
        title: ["var(--text-title)", { lineHeight: "1.4" }],
        value: ["var(--text-value)", { lineHeight: "1.3" }],
        display: ["var(--text-display)", { lineHeight: "1.25" }],
      },
      borderRadius: {
        control: "var(--radius)",
        card: "var(--radius-card)",
      },
      boxShadow: {
        control: "var(--shadow-control)",
        card: "var(--shadow-card)",
      },
      colors: {
        background: hsl("background"),
        foreground: hsl("foreground"),
        heading: hsl("heading"),
        card: { DEFAULT: hsl("card"), foreground: hsl("card-foreground") },
        popover: { DEFAULT: hsl("popover"), foreground: hsl("popover-foreground") },
        primary: { DEFAULT: hsl("primary"), foreground: hsl("primary-foreground") },
        secondary: { DEFAULT: hsl("secondary"), foreground: hsl("secondary-foreground") },
        muted: { DEFAULT: hsl("muted"), foreground: hsl("muted-foreground") },
        accent: { DEFAULT: hsl("accent"), foreground: hsl("accent-foreground") },
        destructive: {
          DEFAULT: hsl("destructive"),
          foreground: hsl("destructive-foreground"),
          tint: hsl("destructive-tint"),
        },
        success: { DEFAULT: hsl("success"), tint: hsl("success-tint") },
        border: hsl("border"),
        control: hsl("control"),
        input: hsl("input"),
        ring: hsl("ring"),
        gaze: hsl("gaze"),
      },
    },
  },
  plugins: [],
}
