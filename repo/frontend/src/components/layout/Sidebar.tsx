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
  { label: 'Dashboard',       path: '/inventory',         icon: HomeIcon,                  roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Receive Stock',   path: '/inventory/receive', icon: ArrowDownTrayIcon,          roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Issue Stock',     path: '/inventory/issue',   icon: ArrowUpTrayIcon,            roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Transfer',        path: '/inventory/transfer',icon: ArrowsRightLeftIcon,        roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Cycle Count',     path: '/inventory/cycle',   icon: ClipboardDocumentCheckIcon, roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  { label: 'Inventory Search',path: '/inventory/search',  icon: MagnifyingGlassIcon,        roles: ['ADMIN', 'INVENTORY_MANAGER'] },
  // ── Crawling ───────────────────────────────────────────────────────────────
  { label: 'Crawl Dashboard', path: '/crawling',          icon: Squares2X2Icon,             roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Crawl Sources',   path: '/crawling/sources',  icon: GlobeAltIcon,               roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Rule Config',     path: '/crawling/rules',    icon: Cog6ToothIcon,              roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Task Monitor',    path: '/crawling/tasks',    icon: ListBulletIcon,             roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  { label: 'Req. Debugger',   path: '/crawling/debugger', icon: BugAntIcon,                 roles: ['ADMIN', 'PROCUREMENT_ANALYST'] },
  // ── Admin ──────────────────────────────────────────────────────────────────
  { label: 'Admin Dashboard', path: '/admin',             icon: CubeIcon,                   roles: ['ADMIN'] },
  { label: 'User Management', path: '/admin/users',       icon: UsersIcon,                  roles: ['ADMIN'] },
  { label: 'Audit Log',       path: '/admin/audit',       icon: ShieldCheckIcon,            roles: ['ADMIN'] },
  { label: 'System Settings', path: '/admin/settings',    icon: Cog6ToothIcon,              roles: ['ADMIN'] },
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
    <div className="px-3 pt-5 pb-1">
      <p className="text-2xs font-semibold uppercase tracking-widest text-text-disabled">{label}</p>
    </div>
  ) : (
    <div className="pt-4 pb-1 border-t border-surface-700/60 mx-2" />
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
        className={({ isActive }) => `
          flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
          transition-colors duration-150 group min-h-touch
          ${isActive
            ? 'bg-primary-500/15 text-primary-400'
            : 'text-text-muted hover:text-text-secondary hover:bg-surface-700'
          }
        `.trim()}
        title={!expanded ? item.label : undefined}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        {expanded && <span className="truncate">{item.label}</span>}
      </NavLink>
    )
  }

  return (
    <aside
      className={`
        fixed left-0 top-0 bottom-0 z-sidebar flex flex-col
        bg-surface-800 border-r border-surface-700
        transition-[width] duration-200 ease-in-out
        ${expanded ? 'w-60' : 'w-16'}
      `.trim()}
    >
      {/* Brand */}
      <div className={`flex items-center gap-3 px-4 py-4 border-b border-surface-700 min-h-[3.5rem] ${!expanded && 'justify-center px-0'}`}>
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center">
          <CubeIcon className="w-5 h-5 text-primary-400" />
        </div>
        {expanded && <span className="text-sm font-bold text-text-primary truncate">Warehouse Intel</span>}
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
      <div className="p-2 border-t border-surface-700">
        <button
          onClick={onToggle}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-text-muted hover:text-text-secondary hover:bg-surface-700 transition-colors min-h-touch ${!expanded && 'justify-center'}`}
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <svg className="w-5 h-5 flex-shrink-0 transition-transform duration-200" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
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
