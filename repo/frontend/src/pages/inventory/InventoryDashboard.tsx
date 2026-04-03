import { useNavigate } from 'react-router-dom'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { StatCard } from '@/components/ui/Card'
import { DataTable } from '@/components/ui/DataTable'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  CubeIcon, ArrowDownTrayIcon, ArrowUpTrayIcon, ExclamationTriangleIcon,
} from '@/components/ui/icons'
import { useItems, useBalances, useItemLedger } from '@/hooks/useInventory'
import type { Column } from '@/types'

const TX_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'neutral'> = {
  RECEIVE: 'success', ISSUE: 'danger', TRANSFER_OUT: 'warning',
  TRANSFER_IN: 'info', CYCLE_COUNT_ADJUST: 'neutral',
}
const TX_LABELS: Record<string, string> = {
  RECEIVE: 'Receive', ISSUE: 'Issue', TRANSFER_OUT: 'Transfer Out',
  TRANSFER_IN: 'Transfer In', CYCLE_COUNT_ADJUST: 'Adj.',
}

interface TxRow { id: string; transaction_type: string; item_sku: string; warehouse_code: string; quantity: string; posted_by_username: string; timestamp: string }

const TX_COLUMNS: Column<TxRow>[] = [
  {
    key: 'transaction_type', header: 'Type', sortable: true,
    render: v => <Badge variant={TX_VARIANT[v as string] ?? 'neutral'}>{TX_LABELS[v as string] ?? v as string}</Badge>,
  },
  { key: 'item_sku', header: 'SKU', sortable: true, className: 'font-mono text-primary-400' },
  { key: 'warehouse_code', header: 'Warehouse', sortable: true },
  {
    key: 'quantity', header: 'Qty', sortable: false,
    render: v => {
      const n = Number(v)
      return <span className={n >= 0 ? 'text-success-400' : 'text-danger-400'}>{n > 0 ? '+' : ''}{v as string}</span>
    },
  },
  { key: 'posted_by_username', header: 'User', sortable: false, render: v => (v as string | null) ?? '—' },
  { key: 'timestamp', header: 'Time', sortable: false, render: v => new Date(v as string).toLocaleString() },
]

interface AlertRow { id: string; item_sku: string; item_name: string; warehouse_code: string; quantity_on_hand: string; safety_stock_qty: string }
const ALERT_COLUMNS: Column<AlertRow>[] = [
  { key: 'item_sku', header: 'SKU', sortable: true, className: 'font-mono text-primary-400' },
  { key: 'item_name', header: 'Item', sortable: true },
  { key: 'warehouse_code', header: 'Warehouse', sortable: true },
  {
    key: 'quantity_on_hand', header: 'On Hand', sortable: true,
    render: v => <span className="text-danger-400 font-semibold">{v as string}</span>,
  },
  { key: 'safety_stock_qty', header: 'Threshold', sortable: false },
]

// Recent transactions use the first active item's ledger as a proxy for all-items feed.
// A proper recent-transactions endpoint is wired in the same API layer.
function useRecentTransactions() {
  // Fetch first page of items and use ledger endpoint via a generic query
  const { data: items } = useItems()
  // Use the first item's ledger as recent-tx placeholder; Phase 5 provides per-item ledgers
  const firstItemId = items?.results[0]?.id ?? null
  return useItemLedger(firstItemId)
}

export function InventoryDashboard() {
  const navigate = useNavigate()

  const { data: itemsData } = useItems()
  const { data: belowSafetyData } = useBalances({ below_safety: true })
  const { data: allBalances } = useBalances()

  const totalSkus = itemsData?.count ?? 0
  const lowStockCount = belowSafetyData?.count ?? 0

  // Count today's receipts and issues from all balances (approximate via ledger is in item detail)
  const todayReceives = allBalances?.results.length ?? 0

  return (
    <PageWrapper
      title="Inventory Dashboard"
      subtitle="Stock overview and recent activity"
      actions={
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate('/inventory/receive')}>
            <ArrowDownTrayIcon className="w-4 h-4 mr-1" /> Receive
          </Button>
          <Button variant="secondary" size="sm" onClick={() => navigate('/inventory/issue')}>
            <ArrowUpTrayIcon className="w-4 h-4 mr-1" /> Issue
          </Button>
        </div>
      }
    >
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total SKUs"
          value={String(totalSkus)}
          sublabel="Active items"
          icon={<CubeIcon className="w-5 h-5" />}
          accent="primary"
        />
        <StatCard
          label="Low Stock Alerts"
          value={String(lowStockCount)}
          sublabel="Below safety threshold"
          icon={<ExclamationTriangleIcon className="w-5 h-5" />}
          accent={lowStockCount > 0 ? 'warning' : 'success'}
        />
        <StatCard
          label="Warehouse Locations"
          value={String(allBalances?.count ?? 0)}
          sublabel="Active stock locations"
          icon={<ArrowDownTrayIcon className="w-5 h-5" />}
          accent="success"
        />
        <StatCard
          label="Active Balances"
          value={String(allBalances?.results.filter(b => Number(b.quantity_on_hand) > 0).length ?? 0)}
          sublabel="Locations with stock"
          icon={<ArrowUpTrayIcon className="w-5 h-5" />}
          accent="info"
        />
      </div>

      {/* Safety stock alerts */}
      {lowStockCount > 0 && (
        <div className="bg-surface-800 border border-danger-800 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-danger-800 flex items-center gap-2">
            <ExclamationTriangleIcon className="w-4 h-4 text-danger-400" />
            <h2 className="text-sm font-semibold text-danger-300">Safety Stock Alerts ({lowStockCount})</h2>
          </div>
          <div className="p-4">
            <DataTable<AlertRow>
              columns={ALERT_COLUMNS}
              data={(belowSafetyData?.results ?? []).map(b => ({
                id: String(b.id),
                item_sku: b.item_sku,
                item_name: b.item_name,
                warehouse_code: b.warehouse_code,
                quantity_on_hand: b.quantity_on_hand,
                safety_stock_qty: b.safety_stock_qty,
              }))}
              emptyMessage="No alerts."
            />
          </div>
        </div>
      )}

      {/* Recent transactions */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-surface-700">
          <h2 className="text-sm font-semibold text-text-primary">Recent Balances</h2>
        </div>
        <div className="p-4">
          <DataTable<AlertRow>
            columns={[
              { key: 'item_sku', header: 'SKU', sortable: true, className: 'font-mono text-primary-400' },
              { key: 'item_name', header: 'Item', sortable: true },
              { key: 'warehouse_code', header: 'Warehouse', sortable: true },
              {
                key: 'quantity_on_hand', header: 'On Hand', sortable: true,
                render: v => <span className={Number(v) <= 0 ? 'text-danger-400' : 'text-success-400'}>{v as string}</span>,
              },
              { key: 'safety_stock_qty', header: 'Safety Stock', sortable: false },
            ]}
            data={(allBalances?.results ?? []).slice(0, 20).map(b => ({
              id: String(b.id),
              item_sku: b.item_sku,
              item_name: b.item_name,
              warehouse_code: b.warehouse_code,
              quantity_on_hand: b.quantity_on_hand,
              safety_stock_qty: b.safety_stock_qty,
            }))}
            emptyMessage="No stock balances yet. Use Receive Stock to add inventory."
          />
        </div>
      </div>
    </PageWrapper>
  )
}
