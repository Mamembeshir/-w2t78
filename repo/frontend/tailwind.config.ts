import type { Config } from 'tailwindcss'

const config: Config = {
  // Scan all source files for class names
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],

  // Enable class-based dark mode (controlled by <html class="dark">)
  darkMode: 'class',

  theme: {
    extend: {
      // ── Colour palette — dark enterprise ─────────────────────────────────
      colors: {
        // Page / panel backgrounds
        surface: {
          900: '#0b1120', // deepest background (page bg)
          800: '#0f172a', // primary card / sidebar
          700: '#1e293b', // secondary card / hover surface
          600: '#334155', // borders, dividers
          500: '#475569', // muted icon, disabled
        },

        // Primary accent — indigo
        primary: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1', // default action
          600: '#4f46e5', // hover
          700: '#4338ca', // pressed
          800: '#3730a3',
          900: '#312e81',
        },

        // Secondary accent — cyan (data / info)
        accent: {
          50:  '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4', // default
          600: '#0891b2', // hover
          700: '#0e7490',
        },

        // Status colours
        success: {
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
        },
        warning: {
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
        },
        danger: {
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
        },
        info: {
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
        },

        // Text hierarchy
        text: {
          primary:   '#f1f5f9', // slate-100
          secondary: '#94a3b8', // slate-400
          muted:     '#64748b', // slate-500
          disabled:  '#475569', // slate-600
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

      // ── Spacing — generous padding for warehouse / kiosk use ─────────────
      spacing: {
        '4.5': '1.125rem',
        '13':  '3.25rem',
        '15':  '3.75rem',
        '18':  '4.5rem',
      },

      // ── Minimum tap-target size (CLAUDE.md: min 44px) ────────────────────
      minHeight: {
        'touch': '2.75rem',  // 44px
        'touch-lg': '3.25rem', // 52px — primary action buttons
      },
      minWidth: {
        'touch': '2.75rem',
      },

      // ── Shadows — subtle, enterprise-grade ───────────────────────────────
      boxShadow: {
        'card':  '0 1px 3px 0 rgba(0,0,0,0.4), 0 1px 2px -1px rgba(0,0,0,0.4)',
        'card-md': '0 4px 6px -1px rgba(0,0,0,0.5), 0 2px 4px -2px rgba(0,0,0,0.5)',
        'card-lg': '0 10px 15px -3px rgba(0,0,0,0.6), 0 4px 6px -4px rgba(0,0,0,0.6)',
        'glow-primary': '0 0 0 3px rgba(99,102,241,0.35)',
        'glow-accent':  '0 0 0 3px rgba(6,182,212,0.35)',
        'glow-danger':  '0 0 0 3px rgba(239,68,68,0.35)',
      },

      // ── Border radius ─────────────────────────────────────────────────────
      borderRadius: {
        'xl':  '0.75rem',
        '2xl': '1rem',
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
    },
  },

  plugins: [],
}

export default config
