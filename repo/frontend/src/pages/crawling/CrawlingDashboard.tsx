import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { GlobeAltIcon, ListBulletIcon, ExclamationTriangleIcon } from '@/components/ui/icons'
import { useSources, useTasks, type CrawlTask, type CrawlSource } from '@/hooks/useCrawling'
import type { Column } from '@/types'

const STATUS_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'neutral'> = {
  COMPLETED: 'success', PENDING: 'neutral', RUNNING: 'info',
  FAILED: 'danger', RETRYING: 'warning', WAITING: 'neutral', CANCELLED: 'neutral',
}

// Row types to satisfy DataTable's Record<string, unknown> constraint
interface TaskRow extends Record<string, unknown> { id: string; source_name: string; status: string; url: string; attempt_count: string; created_at: string }
interface SourceRow extends Record<string, unknown> { id: string; name: string; rate_limit_rpm: string; active_rule_version: string; is_active: string }

function toTaskRow(t: CrawlTask): TaskRow {
  return {
    id: String(t.id),
    source_name: t.source_name,
    status: t.status,
    url: t.url,
    attempt_count: String(t.attempt_count),
    created_at: t.created_at,
  }
}

function toSourceRow(s: CrawlSource): SourceRow {
  return {
    id: String(s.id),
    name: s.name,
    rate_limit_rpm: String(s.rate_limit_rpm),
    active_rule_version: s.active_rule_version != null ? String(s.active_rule_version) : '',
    is_active: String(s.is_active),
  }
}

const TASK_COLUMNS: Column<TaskRow>[] = [
  { key: 'source_name', header: 'Source', sortable: true },
  {
    key: 'status', header: 'Status', sortable: true,
    render: v => <Badge variant={STATUS_VARIANT[v as string] ?? 'neutral'}>{v as string}</Badge>,
  },
  { key: 'url', header: 'URL', sortable: false, className: 'font-mono text-xs max-w-xs truncate' },
  { key: 'attempt_count', header: 'Attempts', sortable: true, className: 'text-right tabular-nums' },
  {
    key: 'created_at', header: 'Created', sortable: false,
    render: v => new Date(v as string).toLocaleString(),
  },
]

const SOURCE_COLUMNS: Column<SourceRow>[] = [
  { key: 'name', header: 'Source', sortable: true },
  { key: 'rate_limit_rpm', header: 'RPM', sortable: true, className: 'text-right tabular-nums' },
  {
    key: 'active_rule_version', header: 'Rule', sortable: false,
    render: v => (v as string)
      ? <span className="text-success-400 font-mono text-xs">v{v as string}</span>
      : <Badge variant="warning">No active rule</Badge>,
  },
  {
    key: 'is_active', header: 'Status', sortable: false,
    render: v => <Badge variant={(v as string) === 'true' ? 'success' : 'neutral'}>{(v as string) === 'true' ? 'Active' : 'Disabled'}</Badge>,
  },
]

export function CrawlingDashboard() {
  const navigate = useNavigate()
  const { data: tasksData, isLoading: tasksLoading } = useTasks()
  const { data: sourcesData, isLoading: sourcesLoading } = useSources()

  const tasks = tasksData?.results ?? []
  const sources = sourcesData?.results ?? []

  const activeTasks = tasks.filter(t => t.status === 'RUNNING').length
  const failedTasks  = tasks.filter(t => t.status === 'FAILED').length
  const sourceCount  = sourcesData?.count ?? 0

  const statCards = [
    { label: 'Running Tasks',  value: String(activeTasks),  sublabel: 'Executing right now',      icon: <ListBulletIcon className="w-5 h-5" />,          accent: 'primary' as const },
    { label: 'Sources',        value: String(sourceCount),  sublabel: 'Configured crawl sources', icon: <GlobeAltIcon className="w-5 h-5" />,            accent: 'info'    as const },
    { label: 'Failed Tasks',   value: String(failedTasks),  sublabel: 'Awaiting retry or review', icon: <ExclamationTriangleIcon className="w-5 h-5" />, accent: 'danger'  as const },
  ]

  return (
    <PageWrapper title="Crawling Dashboard" subtitle="Task queue health and source monitoring">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {statCards.map(c => (
          <StatCard key={c.label} label={c.label} value={c.value} sublabel={c.sublabel} icon={c.icon} accent={c.accent} />
        ))}
      </div>

      {/* Recent tasks */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Recent Crawl Tasks</h2>
          <Button size="sm" variant="ghost" onClick={() => navigate('/crawling/tasks')}>View All →</Button>
        </div>
        <div className="p-4">
          <DataTable<TaskRow>
            columns={TASK_COLUMNS}
            data={tasks.slice(0, 10).map(toTaskRow)}
            isLoading={tasksLoading}
            emptyMessage="No crawl tasks yet."
            onRowClick={() => navigate('/crawling/tasks')}
          />
        </div>
      </div>

      {/* Source health */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">Source Health</h2>
          <Button size="sm" variant="ghost" onClick={() => navigate('/crawling/sources')}>Manage →</Button>
        </div>
        <div className="p-4">
          <DataTable<SourceRow>
            columns={SOURCE_COLUMNS}
            data={sources.map(toSourceRow)}
            isLoading={sourcesLoading}
            emptyMessage="No sources configured. Add one to start crawling."
            onRowClick={row => navigate(`/crawling/rules?source=${row.id}`)}
          />
        </div>
      </div>
    </PageWrapper>
  )
}
