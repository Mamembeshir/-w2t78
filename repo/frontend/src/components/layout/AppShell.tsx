import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { ToastContainer } from '@/components/ui/Toast'

const SIDEBAR_EXPANDED_WIDTH = 240  // px — matches Sidebar w-60
const SIDEBAR_COLLAPSED_WIDTH = 64  // px — matches Sidebar w-16
const LS_KEY = 'sidebar_expanded'
const LG_BREAKPOINT = 1024         // px — Tailwind lg

export function AppShell() {
  const [expanded, setExpanded] = useState<boolean>(() => {
    try { return localStorage.getItem(LS_KEY) !== 'false' }
    catch { return true }
  })

  const [mobileOpen, setMobileOpen] = useState(false)

  // Track whether we're in desktop (lg+) mode
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= LG_BREAKPOINT)
  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${LG_BREAKPOINT}px)`)
    const handler = (e: MediaQueryListEvent) => {
      setIsDesktop(e.matches)
      if (e.matches) setMobileOpen(false)
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  useEffect(() => {
    const on = () => setIsOffline(false)
    const off = () => setIsOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])

  const desktopSidebarWidth = expanded ? SIDEBAR_EXPANDED_WIDTH : SIDEBAR_COLLAPSED_WIDTH
  // On mobile the sidebar is a drawer — main content takes full width
  const effectiveSidebarWidth = isDesktop ? desktopSidebarWidth : 0

  function toggle() {
    setExpanded((v) => {
      const next = !v
      try { localStorage.setItem(LS_KEY, String(next)) } catch { /* noop */ }
      return next
    })
  }

  // Update CSS custom property for smooth transitions (desktop only)
  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', `${effectiveSidebarWidth}px`)
  }, [effectiveSidebarWidth])

  return (
    <div className="min-h-screen bg-surface-950">
      <Sidebar
        expanded={expanded}
        onToggle={toggle}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* Main area: offset by sidebar on desktop; full-width on mobile */}
      <div
        className="flex flex-col min-h-screen transition-[padding-left] duration-200 ease-in-out"
        style={{ paddingLeft: effectiveSidebarWidth, paddingTop: '3.5rem' /* h-14 = 56px */ }}
      >
        <TopBar
          sidebarWidth={effectiveSidebarWidth}
          onMobileMenuOpen={() => setMobileOpen(true)}
        />

        {isOffline && (
          <div className="bg-danger-950/80 border-b border-danger-700/60 px-4 py-2 text-sm text-danger-300 text-center">
            Network unreachable — operating offline. Changes may not be saved until connectivity is restored.
          </div>
        )}

        <main className="flex-1">
          <Outlet />
        </main>
      </div>

      <ToastContainer />
    </div>
  )
}
