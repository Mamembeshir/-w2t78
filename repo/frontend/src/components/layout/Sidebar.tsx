import { NavLink } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { NavItem, Role } from '@/types'
import {
  HomeIcon, ArrowDownTrayIcon, ArrowUpTrayIcon, ArrowsRightLeftIcon,
  ClipboardDocumentCheckIcon, MagnifyingGlassIcon, GlobeAltIcon,
  Cog6ToothIcon, ListBulletIcon, BugAntIcon, UsersIcon, ShieldCheckIcon,
  Squares2X2Icon, CubeIcon,
} from '@/components/ui/icons'

const NAV_ITEMS: NavItem[] = [
  // ── Inventory ──────────────────────────────────────────────────────────────
  { label: 'Dashboard',        path: '/inventory',          icon: HomeIcon,                  roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Receive Stock',    path: '/inventory/receive',  icon: ArrowDownTrayIcon,          roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Issue Stock',      path: '/inventory/issue',    icon: ArrowUpTrayIcon,            roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Transfer',         path: '/inventory/transfer', icon: ArrowsRightLeftIcon,        roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Cycle Count',      path: '/inventory/cycle',    icon: ClipboardDocumentCheckIcon, roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Inventory Search', path: '/inventory/search',   icon: MagnifyingGlassIcon,        roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  // ── Crawling ───────────────────────────────────────────────────────────────
  { label: 'Crawl Dashboard',  path: '/crawling',           icon: Squares2X2Icon,             roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Crawl Sources',    path: '/crawling/sources',   icon: GlobeAltIcon,               roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Rule Config',      path: '/crawling/rules',     icon: Cog6ToothIcon,              roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Task Monitor',     path: '/crawling/tasks',     icon: ListBulletIcon,             roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Req. Debugger',    path: '/crawling/debugger',  icon: BugAntIcon,                 roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  // ── Admin ──────────────────────────────────────────────────────────────────
  { label: 'Admin Dashboard',  path: '/admin',              icon: CubeIcon,                   roles: ['ADMIN'] },
  { label: 'User Management',  path: '/admin/users',        icon: UsersIcon,                  roles: ['ADMIN'] },
  { label: 'Audit Log',        path: '/admin/audit',        icon: ShieldCheckIcon,            roles: ['ADMIN'] },
  { label: 'System Settings',  path: '/admin/settings',     icon: Cog6ToothIcon,              roles: ['ADMIN'] },
]

interface SidebarProps {
  expanded: boolean
  onToggle: () => void
}

function hasAccess(item: NavItem, role: Role): boolean {
  return item.roles.includes(role)
}

function NavGroup({ label, expanded }: { label: string; expanded: boolean }) {
  return expanded ? (
    <div className="px-3 pt-5 pb-1.5">
      <p className="text-2xs font-bold uppercase tracking-[0.12em] text-text-disabled/80 px-1">{label}</p>
    </div>
  ) : (
    <div className="pt-4 pb-1 mx-3">
      <div className="h-px bg-surface-600/40 rounded-full" />
    </div>
  )
}

export function Sidebar({ expanded, onToggle }: SidebarProps) {
  const { user } = useAuth()
  if (!user) return null

  const role = user.role
  const inventoryItems = NAV_ITEMS.filter((i) => i.path.startsWith('/inventory') && hasAccess(i, role))
  const crawlingItems  = NAV_ITEMS.filter((i) => i.path.startsWith('/crawling')  && hasAccess(i, role))
  const adminItems     = NAV_ITEMS.filter((i) => i.path.startsWith('/admin')     && hasAccess(i, role))

  function NavEntry({ item }: { item: NavItem }) {
    const Icon = item.icon
    return (
      <NavLink
        to={item.path}
        end={item.path === '/inventory' || item.path === '/crawling' || item.path === '/admin'}
        title={!expanded ? item.label : undefined}
        className={({ isActive }) => `
          relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
          transition-all duration-150 min-h-touch group
          ${isActive
            ? 'bg-primary-500/12 text-primary-400'
            : 'text-text-muted hover:text-text-secondary hover:bg-surface-700/70'
          }
        `.trim()}
      >
        {({ isActive }) => (
          <>
            {/* Amber left-bar indicator */}
            {isActive && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-primary-500" />
            )}
            <Icon className={`w-5 h-5 flex-shrink-0 transition-colors duration-150
              ${isActive ? 'text-primary-400' : 'text-text-disabled group-hover:text-text-muted'}`} />
            {expanded && <span className="truncate">{item.label}</span>}
          </>
        )}
      </NavLink>
    )
  }

  return (
    <aside
      className={`
        fixed left-0 top-0 bottom-0 z-sidebar flex flex-col
        bg-surface-800 border-r border-surface-600/50
        transition-[width] duration-200 ease-in-out
        ${expanded ? 'w-60' : 'w-16'}
      `.trim()}
    >
      {/* Brand */}
      <div className={`
        flex items-center gap-3 border-b border-surface-600/50 min-h-[3.5rem]
        ${expanded ? 'px-4 py-3.5' : 'justify-center px-0 py-3.5'}
      `}>
        {/* Amber gradient logo mark */}
        <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-gradient-amber
                        ring-1 ring-primary-500/30
                        flex items-center justify-center">
          <CubeIcon className="w-4.5 h-4.5 text-primary-400" />
        </div>
        {expanded && (
          <div className="min-w-0">
            <span className="text-sm font-bold text-text-primary tracking-tight block truncate">
              Warehouse Intel
            </span>
            <span className="text-2xs text-text-disabled uppercase tracking-widest">Operations</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-2 space-y-0.5">
        {inventoryItems.length > 0 && (
          <>
            <NavGroup label="Inventory" expanded={expanded} />
            {inventoryItems.map((i) => <NavEntry key={i.path} item={i} />)}
          </>
        )}
        {crawlingItems.length > 0 && (
          <>
            <NavGroup label="Crawling" expanded={expanded} />
            {crawlingItems.map((i) => <NavEntry key={i.path} item={i} />)}
          </>
        )}
        {adminItems.length > 0 && (
          <>
            <NavGroup label="Admin" expanded={expanded} />
            {adminItems.map((i) => <NavEntry key={i.path} item={i} />)}
          </>
        )}
      </nav>

      {/* Collapse toggle */}
      <div className="p-2 border-t border-surface-600/50">
        <button
          onClick={onToggle}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl
                      text-text-disabled hover:text-text-muted hover:bg-surface-700/70
                      transition-all duration-150 min-h-touch
                      ${!expanded && 'justify-center'}`}
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" strokeWidth={1.5}>
            {expanded
              ? <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              : <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            }
          </svg>
          {expanded && <span className="text-xs">Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
