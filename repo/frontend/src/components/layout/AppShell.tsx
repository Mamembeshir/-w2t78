import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { ToastContainer } from '@/components/ui/Toast'

const SIDEBAR_EXPANDED_WIDTH = 240  // px — matches Sidebar w-60
const SIDEBAR_COLLAPSED_WIDTH = 64  // px — matches Sidebar w-16
const LS_KEY = 'sidebar_expanded'

export function AppShell() {
  const [expanded, setExpanded] = useState<boolean>(() => {
    try { return localStorage.getItem(LS_KEY) !== 'false' }
    catch { return true }
  })

  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  useEffect(() => {
    const on = () => setIsOffline(false)
    const off = () => setIsOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])

  const sidebarWidth = expanded ? SIDEBAR_EXPANDED_WIDTH : SIDEBAR_COLLAPSED_WIDTH

  function toggle() {
    setExpanded((v) => {
      const next = !v
      try { localStorage.setItem(LS_KEY, String(next)) } catch { /* noop */ }
      return next
    })
  }

  // Update CSS custom property for smooth transitions
  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-width', `${sidebarWidth}px`)
  }, [sidebarWidth])

  return (
    <div className="min-h-screen bg-surface-950">
      <Sidebar expanded={expanded} onToggle={toggle} />

      {/* Main area: offset by sidebar, padded by topbar */}
      <div
        className="flex flex-col min-h-screen transition-[padding-left] duration-200 ease-in-out"
        style={{ paddingLeft: sidebarWidth, paddingTop: '3.5rem' /* h-14 = 56px */ }}
      >
        <TopBar sidebarWidth={sidebarWidth} />

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
