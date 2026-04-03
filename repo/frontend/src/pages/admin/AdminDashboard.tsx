import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge, RoleBadge } from '@/components/ui/Badge'
import { UsersIcon, ShieldCheckIcon, Cog6ToothIcon } from '@/components/ui/icons'
import type { Column } from '@/types'

const STAT_CARDS = [
  { label: 'Total Users',      value: '—', sublabel: 'Active accounts',   icon: <UsersIcon className="w-5 h-5" />,      accent: 'primary' as const },
  { label: 'Audit Entries',    value: '—', sublabel: 'Last 24 h',         icon: <ShieldCheckIcon className="w-5 h-5" />, accent: 'info'    as const },
  { label: 'System Status',    value: 'OK', sublabel: 'All services up',  icon: <Cog6ToothIcon className="w-5 h-5" />,  accent: 'success' as const },
]

interface AuditRow { id: string; user: string; action: string; model: string; object: string; ip: string; time: string }
const AUDIT_COLUMNS: Column<AuditRow>[] = [
  { key: 'user',   header: 'User',   sortable: true },
  { key: 'action', header: 'Action', sortable: true,
    render: (v) => {
      const map: Record<string, 'success'|'warning'|'danger'> = { CREATE: 'success', UPDATE: 'warning', DELETE: 'danger' }
      return <Badge variant={map[String(v)] ?? 'neutral'}>{String(v)}</Badge>
    }
  },
  { key: 'model',  header: 'Model',  sortable: true },
  { key: 'object', header: 'Object', sortable: false, className: 'font-mono text-xs' },
  { key: 'ip',     header: 'IP',     sortable: false, className: 'font-mono text-xs' },
  { key: 'time',   header: 'Time',   sortable: false },
]

interface UserRow { id: string; username: string; role: string; active: string; joined: string }
const USER_COLUMNS: Column<UserRow>[] = [
  { key: 'username', header: 'Username', sortable: true, className: 'font-medium text-text-primary' },
  { key: 'role',     header: 'Role',     sortable: true, render: (v) => <RoleBadge role={String(v)} /> },
  { key: 'active',   header: 'Active',   sortable: true,
    render: (v) => <Badge variant={v === 'Yes' ? 'success' : 'danger'}>{String(v)}</Badge>
  },
  { key: 'joined',   header: 'Joined',   sortable: false },
]

export function AdminDashboard() {
  return (
    <PageWrapper title="Admin Dashboard" subtitle="System overview, users, and audit trail">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {STAT_CARDS.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} sublabel={c.sublabel} icon={c.icon} accent={c.accent} />
        ))}
      </div>

      {/* Users */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Users</h2>
          <Badge variant="neutral">Live in Phase 3+</Badge>
        </div>
        <div className="p-4">
          <DataTable<UserRow>
            columns={USER_COLUMNS}
            data={[]}
            emptyMessage="No users loaded. User management API is ready at /api/users/."
          />
        </div>
      </div>

      {/* Audit log */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Recent Audit Log</h2>
          <Badge variant="neutral">Live in Phase 3+</Badge>
        </div>
        <div className="p-4">
          <DataTable<AuditRow>
            columns={AUDIT_COLUMNS}
            data={[]}
            emptyMessage="No audit entries loaded yet."
          />
        </div>
      </div>
    </PageWrapper>
  )
}
