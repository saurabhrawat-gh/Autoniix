import type { Config } from 'tailwindcss';

function cssVar(name: string) {
  return `rgb(var(--${name}) / <alpha-value>)`;
}

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },
      colors: {
        surface: {
          0: cssVar('surface-0'),
          1: cssVar('surface-1'),
          2: cssVar('surface-2'),
          3: cssVar('surface-3'),
        },
        accent: {
          DEFAULT: cssVar('accent'),
          hover: cssVar('accent-hover'),
          light: cssVar('accent-light'),
          muted: cssVar('accent-muted'),
        },
        secondary: {
          DEFAULT: cssVar('secondary'),
          light: cssVar('secondary-light'),
        },
        content: {
          primary: cssVar('content-primary'),
          secondary: cssVar('content-secondary'),
          tertiary: cssVar('content-tertiary'),
          inverse: cssVar('content-inverse'),
        },
        status: {
          success: cssVar('status-success'),
          warning: cssVar('status-warning'),
          error: cssVar('status-error'),
          info: cssVar('status-info'),
        },
        border: {
          DEFAULT: cssVar('border'),
          hover: cssVar('border-hover'),
          focus: cssVar('accent'),
        },
      },
      borderRadius: {
        none: '0px',
        sm: '6px',
        DEFAULT: '8px',
        md: '8px',
        lg: '10px',
        xl: '12px',
        '2xl': '14px',
        full: '9999px',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        elevated: 'var(--shadow-elevated)',
        focus: '0 0 0 2px rgb(var(--accent-light)), 0 0 0 4px rgb(var(--accent))',
        glow: 'var(--shadow-glow)',
      },
    },
  },
  plugins: [],
};

export default config;
