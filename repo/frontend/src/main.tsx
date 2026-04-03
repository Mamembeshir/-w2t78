import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'

// Global dark-theme stylesheet — Tailwind directives + base layer
import './styles/globals.css'

import { queryClient } from './lib/queryClient'

// ── Bootstrap placeholder ─────────────────────────────────────────────────
// Full routing + auth shell implemented in Phase 4.
// This page confirms Tailwind + React + providers are wired correctly.
function BootstrapPage() {
  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center px-4">
      <div className="card max-w-lg w-full text-center space-y-6">
        {/* Logo area */}
        <div className="flex items-center justify-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            Warehouse Intelligence
          </h1>
        </div>

        {/* Status */}
        <div className="space-y-2">
          <p className="text-text-secondary text-sm">Platform is initialising</p>
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <span className="badge-success">React 19</span>
            <span className="badge-success">Vite</span>
            <span className="badge-success">TailwindCSS</span>
            <span className="badge-success">React Query</span>
            <span className="badge-info">Phase 1.5 ✓</span>
          </div>
        </div>

        {/* Phase note */}
        <p className="text-text-muted text-xs">
          Full routing, auth, and UI built in Phases 3–7.
          Backend API: <span className="text-accent-400 font-mono">
            {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}
          </span>
        </p>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BootstrapPage />
    </QueryClientProvider>
  </StrictMode>,
)
