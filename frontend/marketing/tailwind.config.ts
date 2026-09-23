import type { Config } from "tailwindcss";

/* Token bridge — identical to frontend/dashboard/tailwind.config.ts so both
 * autoniix.com and dash.autoniix.com share one palette. Values live in
 * src/app/globals.css as space-separated RGB triplets. */
function cssVar(name: string) {
  return `rgb(var(--${name}) / <alpha-value>)`;
}

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          bg: cssVar("surface-bg"),
          0: cssVar("surface-0"),
          1: cssVar("surface-1"),
          2: cssVar("surface-2"),
          3: cssVar("surface-3"),
        },
        accent: {
          DEFAULT: cssVar("accent"),
          hover: cssVar("accent-hover"),
          light: cssVar("accent-light"),
          muted: cssVar("accent-muted"),
        },
        "accent-primary": cssVar("accent-primary-bg"),
        "accent-primary-fg": cssVar("accent-primary-text"),
        secondary: {
          DEFAULT: cssVar("secondary"),
          light: cssVar("secondary-light"),
        },
        brand: {
          violet: "#8A56FF",
          pink: "#FF6FB5",
        },
        content: {
          primary: cssVar("content-primary"),
          secondary: cssVar("content-secondary"),
          tertiary: cssVar("content-tertiary"),
          disabled: cssVar("content-disabled"),
          inverse: cssVar("content-inverse"),
        },
        border: {
          DEFAULT: cssVar("border"),
          hover: cssVar("border-hover"),
        },
        status: {
          success: cssVar("status-success"),
          warning: cssVar("status-warning"),
          error: cssVar("status-error"),
          info: cssVar("status-info"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Satoshi", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        glow: "var(--shadow-glow)",
      },
      letterSpacing: {
        tight: "-0.022em",
        tighter: "-0.035em",
      },
      animation: {
        marquee: "marquee 40s linear infinite",
        "flow-dash": "flowDash 1.6s linear infinite",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        shimmer: "shimmer 2.8s linear infinite",
        scan: "scan 7s linear infinite",
        "spin-slow": "spin 14s linear infinite",
        "float-slow": "float 9s ease-in-out infinite",
      },
      keyframes: {
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        flowDash: {
          to: { strokeDashoffset: "-24" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "0.45", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.06)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 50%" },
          "100%": { backgroundPosition: "-200% 50%" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-14px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
