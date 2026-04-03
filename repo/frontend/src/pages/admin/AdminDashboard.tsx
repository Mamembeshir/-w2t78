import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge, RoleBadge } from '@/components/ui/Badge'
import { UsersIcon, ShieldCheckIcon, Cog6ToothIcon } from '@/components/ui/icons'
import { useUsers, useAuditLog } from '@/hooks/useAdmin'
import type { Column } from '@/types'

interface AuditRow extends Record<string, unknown> { id: string; user: string; action: string; model_name: string; object_id: string; ip_address: string; timestamp: string }
const AUDIT_COLUMNS: Column<AuditRow>[] = [
  { key: 'user',       header: 'User',    sortable: true },
  { key: 'action',     header: 'Action',  sortable: true,
    render: (v) => {
      const map: Record<string, 'success'|'warning'|'danger'> = { CREATE: 'success', UPDATE: 'warning', DELETE: 'danger' }
      return <Badge variant={map[String(v)] ?? 'neutral'}>{String(v)}</Badge>
    }
  },
  { key: 'model_name', header: 'Model',   sortable: true },
  { key: 'object_id',  header: 'Object',  sortable: false, className: 'font-mono text-xs' },
  { key: 'ip_address', header: 'IP',      sortable: false, className: 'font-mono text-xs',
    render: v => (v as string | null) ?? '—' },
  { key: 'timestamp',  header: 'Time',    sortable: true,
    render: v => new Date(v as string).toLocaleString() },
]

interface UserRow extends Record<string, unknown> { id: string; username: string; role: string; is_active: string; date_joined: string }
const USER_COLUMNS: Column<UserRow>[] = [
  { key: 'username',   header: 'Username', sortable: true, className: 'font-medium text-text-primary' },
  { key: 'role',       header: 'Role',     sortable: true, render: (v) => <RoleBadge role={String(v)} /> },
  { key: 'is_active',  header: 'Active',   sortable: true,
    render: (v) => <Badge variant={v === 'Yes' ? 'success' : 'danger'}>{String(v)}</Badge>
  },
  { key: 'date_joined', header: 'Joined',  sortable: false,
    render: v => new Date(v as string).toLocaleDateString() },
]

export function AdminDashboard() {
  const { data: usersData, isLoading: usersLoading } = useUsers()
  const { data: auditData, isLoading: auditLoading } = useAuditLog()

  const totalUsers = usersData?.count ?? 0
  const activeUsers = usersData?.results?.filter(u => u.is_active)?.length ?? 0
  const auditCount = auditData?.count ?? 0

  const userRows: UserRow[] = (usersData?.results ?? []).map(u => ({
    id: String(u.id),
    username: u.username,
    role: u.role,
    is_active: u.is_active ? 'Yes' : 'No',
    date_joined: u.date_joined,
  }))

  const auditRows: AuditRow[] = (auditData?.results ?? []).slice(0, 50).map(e => ({
    id: String(e.id),
    user: e.user,
    action: e.action,
    model_name: e.model_name,
    object_id: e.object_id,
    ip_address: e.ip_address ?? '—',
    timestamp: e.timestamp,
  }))

  return (
    <PageWrapper title="Admin Dashboard" subtitle="System overview, users, and audit trail">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Total Users"
          value={String(totalUsers)}
          sublabel={`${activeUsers} active`}
          icon={<UsersIcon className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Audit Entries"
          value={String(auditCount)}
          sublabel="All time (365-day retention)"
          icon={<ShieldCheckIcon className="w-5 h-5" />}
          accent="info"
        />
        <StatCard
          label="System Status"
          value="OK"
          sublabel="All services up"
          icon={<Cog6ToothIcon className="w-5 h-5" />}
          accent="success"
        />
      </div>

      {/* Users */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700">
          <h2 className="text-sm font-semibold text-text-primary">Users</h2>
        </div>
        <div className="p-4">
          <DataTable<UserRow>
            columns={USER_COLUMNS}
            data={userRows}
            rowKey="id"
            isLoading={usersLoading}
            emptyMessage="No users found."
          />
        </div>
      </div>

      {/* Audit log */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700">
          <h2 className="text-sm font-semibold text-text-primary">Recent Audit Log</h2>
        </div>
        <div className="p-4">
          <DataTable<AuditRow>
            columns={AUDIT_COLUMNS}
            data={auditRows}
            rowKey="id"
            isLoading={auditLoading}
            emptyMessage="No audit entries yet."
          />
        </div>
      </div>
    </PageWrapper>
  )
}
