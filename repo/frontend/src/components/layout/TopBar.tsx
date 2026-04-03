import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { RoleBadge } from '@/components/ui/Badge'
import { BellIcon, ArrowRightOnRectangleIcon } from '@/components/ui/icons'

interface TopBarProps {
  sidebarWidth: number
}

export function TopBar({ sidebarWidth }: TopBarProps) {
  const { user, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  async function handleLogout() {
    setUserMenuOpen(false)
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      toast.error('Logout failed. You have been signed out locally.')
      navigate('/login', { replace: true })
    }
  }

  return (
    <header
      className="fixed top-0 right-0 z-topbar flex items-center justify-between px-5 bg-surface-800 border-b border-surface-700 h-14"
      style={{ left: sidebarWidth }}
    >
      {/* Left side — placeholder for breadcrumb / page title (set per-page via Portal or context in future phases) */}
      <div />

      {/* Right side — notification + user */}
      <div className="flex items-center gap-2">
        {/* Notification bell */}
        <button
          className="relative p-2 rounded-xl text-text-muted hover:text-text-secondary hover:bg-surface-700 transition-colors min-h-touch min-w-touch flex items-center justify-center"
          aria-label="Notifications"
          onClick={() => toast.info('Notifications coming in Phase 7.')}
        >
          <BellIcon className="w-5 h-5" />
          {/* Unread badge — skeleton for Phase 4; wired in Phase 7 */}
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger-500 ring-2 ring-surface-800" />
        </button>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl hover:bg-surface-700 transition-colors min-h-touch"
            aria-expanded={userMenuOpen}
            aria-haspopup="true"
          >
            {/* Avatar */}
            <div className="w-7 h-7 rounded-full bg-primary-500/20 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-bold text-primary-400">
                {user?.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <span className="text-sm font-medium text-text-primary hidden sm:block max-w-[8rem] truncate">
              {user?.username}
            </span>
          </button>

          {/* Dropdown */}
          {userMenuOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-56 bg-surface-800 border border-surface-700 rounded-xl shadow-card-lg py-1 z-tooltip">
              {/* User info */}
              <div className="px-4 py-3 border-b border-surface-700">
                <p className="text-sm font-semibold text-text-primary truncate">{user?.username}</p>
                {user?.email && <p className="text-xs text-text-muted truncate mt-0.5">{user.email}</p>}
                <div className="mt-2">{user && <RoleBadge role={user.role} />}</div>
              </div>
              {/* Actions */}
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-danger-400 hover:bg-surface-700 transition-colors"
              >
                <ArrowRightOnRectangleIcon className="w-4 h-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
