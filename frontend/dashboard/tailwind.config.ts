import type { Config } from "tailwindcss";

function cssVar(name: string) {
  return `rgb(var(--${name}) / <alpha-value>)`;
}

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontSize: {
        "display-xl": [
          "var(--type-display-xl-size)",
          {
            lineHeight: "1.14",
            fontWeight: "var(--type-display-xl-weight)",
            letterSpacing: "var(--type-display-xl-tracking)",
          },
        ],
        "display-l": [
          "var(--type-display-l-size)",
          {
            lineHeight: "1.17",
            fontWeight: "var(--type-display-l-weight)",
            letterSpacing: "var(--type-display-l-tracking)",
          },
        ],
        h1: [
          "var(--type-h1-size)",
          {
            lineHeight: "var(--type-h1-leading)",
            fontWeight: "var(--type-h1-weight)",
            letterSpacing: "var(--type-h1-tracking)",
          },
        ],
        h2: [
          "var(--type-h2-size)",
          {
            lineHeight: "var(--type-h2-leading)",
            fontWeight: "var(--type-h2-weight)",
            letterSpacing: "var(--type-h2-tracking)",
          },
        ],
        h3: [
          "var(--type-h3-size)",
          {
            lineHeight: "var(--type-h3-leading)",
            fontWeight: "var(--type-h3-weight)",
            letterSpacing: "var(--type-h3-tracking)",
          },
        ],
        h4: [
          "var(--type-h4-size)",
          {
            lineHeight: "var(--type-h4-leading)",
            fontWeight: "var(--type-h4-weight)",
            letterSpacing: "var(--type-h4-tracking)",
          },
        ],
        body: [
          "var(--type-body-md-size)",
          { lineHeight: "var(--type-body-md-leading)", letterSpacing: "var(--type-body-md-tracking)" },
        ],
        "body-sm": [
          "var(--type-body-sm-size)",
          { lineHeight: "var(--type-body-sm-leading)", letterSpacing: "var(--type-body-sm-tracking)" },
        ],
        caption: [
          "var(--type-caption-size)",
          { lineHeight: "var(--type-caption-leading)", letterSpacing: "var(--type-caption-tracking)" },
        ],
        metric: [
          "var(--type-metric-size)",
          {
            lineHeight: "var(--type-metric-leading)",
            fontWeight: "var(--type-metric-weight)",
            letterSpacing: "var(--type-metric-tracking)",
          },
        ],
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Satoshi", "system-ui", "-apple-system", "sans-serif"],
        display: ["var(--font-sans)", "Satoshi", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
      colors: {
        surface: {
          bg: cssVar("surface-bg"),
          sidebar: cssVar("surface-sidebar"),
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
        content: {
          primary: cssVar("content-primary"),
          secondary: cssVar("content-secondary"),
          tertiary: cssVar("content-tertiary"),
          muted: cssVar("content-muted"),
          disabled: cssVar("content-disabled"),
          inverse: cssVar("content-inverse"),
        },
        status: {
          success: cssVar("status-success"),
          warning: cssVar("status-warning"),
          error: cssVar("status-error"),
          info: cssVar("status-info"),
        },
        border: {
          DEFAULT: cssVar("border"),
          hover: cssVar("border-hover"),
          focus: cssVar("accent"),
        },
      },
      borderRadius: {
        none: "0px",
        sm: "4px",
        DEFAULT: "6px",
        md: "6px",
        lg: "10px",
        xl: "12px",
        "2xl": "16px",
        full: "9999px",
      },
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
        "30": "7.5rem",
        sidebar: "240px",
        "sidebar-collapsed": "56px",
        topbar: "56px",
      },
      maxWidth: {
        content: "1600px",
        onboarding: "480px",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        modal: "var(--shadow-elevated)",
        focus: "0 0 0 2px rgb(var(--accent-light)), 0 0 0 4px rgb(var(--accent))",
        glow: "var(--shadow-glow)",
      },
    },
  },
  plugins: [],
};

export default config;
