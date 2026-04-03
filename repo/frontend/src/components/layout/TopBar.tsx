import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { useTheme } from '@/contexts/ThemeContext'
import { useUnreadCount } from '@/hooks/useNotifications'
import { RoleBadge } from '@/components/ui/Badge'
import { BellIcon, ArrowRightOnRectangleIcon } from '@/components/ui/icons'

interface TopBarProps {
  sidebarWidth: number
}

function SunIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
    </svg>
  )
}

function MoonIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  )
}

export function TopBar({ sidebarWidth }: TopBarProps) {
  const { user, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { theme, toggle: toggleTheme } = useTheme()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const { data: unreadData } = useUnreadCount()
  const unreadCount = unreadData?.unread_count ?? 0

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
      className="fixed top-0 right-0 z-topbar flex items-center justify-between px-5
                 bg-surface-800/95 backdrop-blur-sm
                 border-b border-surface-600/50 h-14
                 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-px
                 after:bg-gradient-to-r after:from-transparent after:via-primary-500/30 after:to-transparent"
      style={{ left: sidebarWidth }}
    >
      {/* Left — empty slot for breadcrumbs/page title if needed */}
      <div />

      {/* Right — theme toggle + notifications + user */}
      <div className="flex items-center gap-1.5">

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-xl text-text-muted hover:text-primary-400
                     hover:bg-primary-500/10 transition-all duration-200
                     min-h-touch min-w-touch flex items-center justify-center"
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark'
            ? <SunIcon className="w-4.5 h-4.5" />
            : <MoonIcon className="w-4.5 h-4.5" />
          }
        </button>

        {/* Notification bell */}
        <button
          className="relative p-2 rounded-xl text-text-muted hover:text-primary-400
                     hover:bg-primary-500/10 transition-all duration-200
                     min-h-touch min-w-touch flex items-center justify-center"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          onClick={() => navigate('/notifications')}
        >
          <BellIcon className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 min-w-[1rem] h-4 rounded-full
                             bg-primary-500 flex items-center justify-center
                             ring-2 ring-surface-800">
              <span className="text-[0.55rem] font-bold text-surface-950 leading-none tabular-nums">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            </span>
          )}
        </button>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen((v) => !v)}
            className="flex items-center gap-2.5 pl-1.5 pr-3 py-1.5 rounded-xl
                       hover:bg-primary-500/10 transition-all duration-200 min-h-touch"
            aria-expanded={userMenuOpen}
            aria-haspopup="true"
          >
            {/* Avatar — amber gradient ring */}
            <div className="w-7 h-7 rounded-full bg-gradient-amber ring-1 ring-primary-500/40
                            flex items-center justify-center flex-shrink-0">
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
            <div className="absolute right-0 top-full mt-1.5 w-56
                            bg-surface-800 border border-surface-600/60
                            rounded-2xl shadow-card-lg py-1 z-tooltip
                            animate-fade-in">
              <div className="px-4 py-3 border-b border-surface-600/50">
                <p className="text-sm font-semibold text-text-primary truncate">{user?.username}</p>
                {user?.email && <p className="text-xs text-text-muted truncate mt-0.5">{user.email}</p>}
                <div className="mt-2">{user && <RoleBadge role={user.role} />}</div>
              </div>
              <button
                onClick={() => { setUserMenuOpen(false); navigate('/notifications/settings') }}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm
                           text-text-secondary hover:text-text-primary hover:bg-primary-500/8
                           transition-colors"
              >
                <BellIcon className="w-4 h-4" />
                Notification settings
              </button>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm
                           text-text-secondary hover:text-danger-400 hover:bg-danger-500/8
                           transition-colors"
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
