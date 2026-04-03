import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge } from '@/components/ui/Badge'
import {
  CubeIcon, ArrowDownTrayIcon, ArrowUpTrayIcon, ExclamationTriangleIcon,
} from '@/components/ui/icons'
import type { Column } from '@/types'

// ── Skeleton data — replaced with real API calls in Phase 5 ──────────────────

const STAT_CARDS = [
  { label: 'Total SKUs',        value: '—', sublabel: 'API wired in Phase 5', icon: <CubeIcon className="w-5 h-5" />,              accent: 'primary'  as const },
  { label: 'Low Stock Alerts',  value: '—', sublabel: 'Below safety threshold',icon: <ExclamationTriangleIcon className="w-5 h-5" />, accent: 'warning' as const },
  { label: 'Receipts Today',    value: '—', sublabel: 'Stock received today',  icon: <ArrowDownTrayIcon className="w-5 h-5" />,       accent: 'success' as const },
  { label: 'Issues Today',      value: '—', sublabel: 'Stock issued today',    icon: <ArrowUpTrayIcon className="w-5 h-5" />,         accent: 'info'    as const },
]

interface TxRow { id: string; type: string; sku: string; warehouse: string; qty: string; user: string; time: string }
const TX_COLUMNS: Column<TxRow>[] = [
  { key: 'type',      header: 'Type',      sortable: true,  render: (v) => <Badge variant={v === 'RECEIVE' ? 'success' : v === 'ISSUE' ? 'warning' : 'info'}>{String(v)}</Badge> },
  { key: 'sku',       header: 'SKU',       sortable: true,  className: 'font-mono text-text-primary' },
  { key: 'warehouse', header: 'Warehouse', sortable: true },
  { key: 'qty',       header: 'Qty',       sortable: false, className: 'tabular-nums text-right' },
  { key: 'user',      header: 'User',      sortable: true },
  { key: 'time',      header: 'Time',      sortable: false },
]

export function InventoryDashboard() {
  return (
    <PageWrapper title="Inventory Dashboard" subtitle="Stock overview and recent activity">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} sublabel={c.sublabel} icon={c.icon} accent={c.accent} />
        ))}
      </div>

      {/* Recent transactions */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Recent Transactions</h2>
          <Badge variant="neutral">Live in Phase 5</Badge>
        </div>
        <div className="p-4">
          <DataTable<TxRow>
            columns={TX_COLUMNS}
            data={[]}
            emptyMessage="No transactions yet. Inventory operations available in Phase 5."
          />
        </div>
      </div>

      {/* Safety stock alerts placeholder */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-text-primary">Safety Stock Alerts</h2>
          <Badge variant="neutral">Live in Phase 5</Badge>
        </div>
        <p className="text-sm text-text-muted">
          Safety stock monitoring triggers when quantity stays below threshold for 10 consecutive minutes.
          Alerts will appear here once Phase 5 inventory operations are complete.
        </p>
      </div>
    </PageWrapper>
  )
}
