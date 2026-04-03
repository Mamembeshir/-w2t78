import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge } from '@/components/ui/Badge'
import { GlobeAltIcon, ListBulletIcon, ExclamationTriangleIcon } from '@/components/ui/icons'
import type { Column } from '@/types'

const STAT_CARDS = [
  { label: 'Active Tasks',   value: '—', sublabel: 'Running right now',  icon: <ListBulletIcon className="w-5 h-5" />,         accent: 'primary'  as const },
  { label: 'Sources',        value: '—', sublabel: 'Configured sources', icon: <GlobeAltIcon className="w-5 h-5" />,           accent: 'info'     as const },
  { label: 'Failed Today',   value: '—', sublabel: 'Max 5 retry attempts',icon: <ExclamationTriangleIcon className="w-5 h-5" />, accent: 'danger'  as const },
]

interface TaskRow { id: string; source: string; status: string; url: string; attempts: string; updated: string }
const TASK_COLUMNS: Column<TaskRow>[] = [
  { key: 'source',   header: 'Source',   sortable: true },
  { key: 'status',   header: 'Status',   sortable: true,
    render: (v) => {
      const map: Record<string, 'success'|'warning'|'danger'|'info'|'neutral'> = {
        COMPLETED: 'success', PENDING: 'neutral', RUNNING: 'info', FAILED: 'danger', RETRYING: 'warning',
      }
      return <Badge variant={map[String(v)] ?? 'neutral'}>{String(v)}</Badge>
    }
  },
  { key: 'url',      header: 'URL',      sortable: false, className: 'font-mono text-xs max-w-xs truncate' },
  { key: 'attempts', header: 'Attempts', sortable: true,  className: 'text-right tabular-nums' },
  { key: 'updated',  header: 'Updated',  sortable: false },
]

export function CrawlingDashboard() {
  return (
    <PageWrapper title="Crawling Dashboard" subtitle="Task queue health and source monitoring">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {STAT_CARDS.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} sublabel={c.sublabel} icon={c.icon} accent={c.accent} />
        ))}
      </div>

      {/* Recent tasks */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Recent Crawl Tasks</h2>
          <Badge variant="neutral">Live in Phase 6</Badge>
        </div>
        <div className="p-4">
          <DataTable<TaskRow>
            columns={TASK_COLUMNS}
            data={[]}
            emptyMessage="No crawl tasks yet. Crawling engine available in Phase 6."
          />
        </div>
      </div>

      {/* Source health */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-text-primary">Source Health</h2>
          <Badge variant="neutral">Live in Phase 6</Badge>
        </div>
        <p className="text-sm text-text-muted">
          Per-source rate limit usage, canary status, and error rates will display here.
          Canary releases run at 5 % traffic for 30 minutes — automatic rollback if error rate exceeds 2 %.
        </p>
      </div>
    </PageWrapper>
  )
}
