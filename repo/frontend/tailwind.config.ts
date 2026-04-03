import type { Config } from 'tailwindcss'

// All semantic colors are driven by CSS custom properties so that the dark/light
// theme switch is handled entirely in globals.css — no component changes needed.
// The `rgb(var(--x) / <alpha-value>)` pattern supports Tailwind's opacity modifier
// syntax (e.g. bg-primary-500/20, text-surface-900/80).

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],

  // Class-based theming: html has no extra class → dark (default)
  //                       html.light → light theme
  darkMode: 'class',

  theme: {
    extend: {
      // ── Colour palette — CSS-variable driven ─────────────────────────────
      colors: {
        // Page / panel backgrounds
        surface: {
          950: 'rgb(var(--surface-950) / <alpha-value>)',
          900: 'rgb(var(--surface-900) / <alpha-value>)',
          800: 'rgb(var(--surface-800) / <alpha-value>)',
          700: 'rgb(var(--surface-700) / <alpha-value>)',
          600: 'rgb(var(--surface-600) / <alpha-value>)',
          500: 'rgb(var(--surface-500) / <alpha-value>)',
        },

        // Primary accent — Amber / Warm Gold
        // Rare in enterprise tools; premium financial-terminal feel.
        primary: {
          50:  'rgb(var(--primary-50)  / <alpha-value>)',
          100: 'rgb(var(--primary-100) / <alpha-value>)',
          200: 'rgb(var(--primary-200) / <alpha-value>)',
          300: 'rgb(var(--primary-300) / <alpha-value>)',
          400: 'rgb(var(--primary-400) / <alpha-value>)',
          500: 'rgb(var(--primary-500) / <alpha-value>)',
          600: 'rgb(var(--primary-600) / <alpha-value>)',
          700: 'rgb(var(--primary-700) / <alpha-value>)',
          800: 'rgb(var(--primary-800) / <alpha-value>)',
          900: 'rgb(var(--primary-900) / <alpha-value>)',
        },

        // Status colours — semantic, consistent across themes
        success: {
          400: 'rgb(74 222 128 / <alpha-value>)',
          500: 'rgb(34 197 94  / <alpha-value>)',
          600: 'rgb(22 163 74  / <alpha-value>)',
          900: 'rgb(20 83  45  / <alpha-value>)',
          950: 'rgb(5  46  22  / <alpha-value>)',
        },
        warning: {
          400: 'rgb(251 191 36  / <alpha-value>)',
          500: 'rgb(245 158 11  / <alpha-value>)',
          600: 'rgb(217 119 6   / <alpha-value>)',
        },
        danger: {
          300: 'rgb(252 165 165 / <alpha-value>)',
          400: 'rgb(248 113 113 / <alpha-value>)',
          500: 'rgb(239 68  68  / <alpha-value>)',
          600: 'rgb(220 38  38  / <alpha-value>)',
          700: 'rgb(185 28  28  / <alpha-value>)',
          900: 'rgb(127 29  29  / <alpha-value>)',
          950: 'rgb(69  10  10  / <alpha-value>)',
        },
        info: {
          400: 'rgb(96  165 250 / <alpha-value>)',
          500: 'rgb(59  130 246 / <alpha-value>)',
          600: 'rgb(37  99  235 / <alpha-value>)',
        },

        // Text hierarchy — CSS-variable driven
        text: {
          primary:   'rgb(var(--text-primary)   / <alpha-value>)',
          secondary: 'rgb(var(--text-secondary) / <alpha-value>)',
          muted:     'rgb(var(--text-muted)     / <alpha-value>)',
          disabled:  'rgb(var(--text-disabled)  / <alpha-value>)',
        },
      },

      // ── Typography ────────────────────────────────────────────────────────
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'monospace',
        ],
      },

      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },

      // ── Spacing ───────────────────────────────────────────────────────────
      spacing: {
        '4.5': '1.125rem',
        '13':  '3.25rem',
        '15':  '3.75rem',
        '18':  '4.5rem',
      },

      // ── Minimum tap-target size ────────────────────────────────────────────
      minHeight: {
        'touch':    '2.75rem',
        'touch-lg': '3.25rem',
      },
      minWidth: {
        'touch': '2.75rem',
      },

      // ── Shadows ───────────────────────────────────────────────────────────
      boxShadow: {
        'card':         '0 1px 3px 0 rgba(0,0,0,0.25), 0 1px 2px -1px rgba(0,0,0,0.25)',
        'card-md':      '0 4px 6px -1px rgba(0,0,0,0.3), 0 2px 4px -2px rgba(0,0,0,0.3)',
        'card-lg':      '0 10px 15px -3px rgba(0,0,0,0.35), 0 4px 6px -4px rgba(0,0,0,0.35)',
        // Amber glow — primary focus ring / hover highlight
        'glow-primary': '0 0 0 3px rgba(245,158,11,0.28)',
        'glow-accent':  '0 0 0 3px rgba(245,158,11,0.18)',
        'glow-danger':  '0 0 0 3px rgba(239,68,68,0.28)',
        // Inner bottom border line — premium card edge highlight
        'inner-top':    'inset 0 1px 0 0 rgba(255,255,255,0.06)',
      },

      // ── Border radius ─────────────────────────────────────────────────────
      borderRadius: {
        'xl':  '0.75rem',
        '2xl': '1rem',
        '3xl': '1.25rem',
      },

      // ── Transitions ───────────────────────────────────────────────────────
      transitionDuration: {
        '150': '150ms',
        '200': '200ms',
      },

      // ── Z-index layers ────────────────────────────────────────────────────
      zIndex: {
        'sidebar':  '40',
        'topbar':   '50',
        'modal':    '60',
        'toast':    '70',
        'tooltip':  '80',
      },

      // ── Keyframes for micro-animations ───────────────────────────────────
      keyframes: {
        'fade-in': {
          '0%':   { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'amber-pulse': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(245,158,11,0)' },
          '50%':      { boxShadow: '0 0 0 6px rgba(245,158,11,0.12)' },
        },
      },
      animation: {
        'fade-in':     'fade-in 0.15s ease-out',
        'amber-pulse': 'amber-pulse 2s ease-in-out infinite',
      },
    },
  },

  plugins: [],
}

export default config
