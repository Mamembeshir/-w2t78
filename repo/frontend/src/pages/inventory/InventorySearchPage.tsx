import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { DataTable } from '@/components/ui/DataTable'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useItems, useItemLedger, type Item } from '@/hooks/useInventory'
import type { Column } from '@/types'

const TX_LABELS: Record<string, string> = {
  RECEIVE: 'Receive',
  ISSUE: 'Issue',
  TRANSFER_OUT: 'Transfer Out',
  TRANSFER_IN: 'Transfer In',
  CYCLE_COUNT_ADJUST: 'Cycle Count Adj.',
}

const TX_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'neutral'> = {
  RECEIVE: 'success',
  ISSUE: 'danger',
  TRANSFER_OUT: 'warning',
  TRANSFER_IN: 'info',
  CYCLE_COUNT_ADJUST: 'neutral',
}

const itemColumns: Column<Record<string, unknown>>[] = [
  {
    key: 'sku',
    header: 'SKU',
    sortable: true,
    render: v => <span className="font-mono text-primary-400">{v as string}</span>,
  },
  { key: 'name', header: 'Name', sortable: true },
  {
    key: 'unit_of_measure',
    header: 'UOM',
    sortable: false,
    render: v => <span className="text-text-muted">{v as string}</span>,
  },
  {
    key: 'costing_method',
    header: 'Costing',
    sortable: true,
    render: v => (
      <Badge variant={v === 'FIFO' ? 'info' : 'neutral'}>
        {v === 'FIFO' ? 'FIFO' : 'Avg Cost'}
      </Badge>
    ),
  },
  {
    key: 'total_on_hand',
    header: 'On Hand',
    sortable: true,
    render: v => <span className="font-semibold">{v as string}</span>,
  },
  {
    key: 'slow_moving_flagged_at',
    header: 'Slow Moving',
    sortable: false,
    render: v => v ? <Badge variant="warning">Slow</Badge> : null,
  },
]

const ledgerColumns: Column<Record<string, unknown>>[] = [
  {
    key: 'timestamp',
    header: 'Date',
    sortable: true,
    render: v => new Date(v as string).toLocaleString(),
  },
  {
    key: 'transaction_type',
    header: 'Type',
    sortable: true,
    render: v => (
      <Badge variant={TX_VARIANT[v as string] ?? 'neutral'}>
        {TX_LABELS[v as string] ?? v as string}
      </Badge>
    ),
  },
  {
    key: 'warehouse_code',
    header: 'Warehouse',
    sortable: true,
  },
  {
    key: 'bin_code',
    header: 'Bin',
    sortable: false,
    render: v => (v as string | null) ?? '—',
  },
  {
    key: 'lot_number',
    header: 'Lot',
    sortable: false,
    render: v => (v as string | null) ?? '—',
  },
  {
    key: 'quantity',
    header: 'Qty',
    sortable: true,
    render: v => {
      const n = Number(v)
      return <span className={n >= 0 ? 'text-success-400' : 'text-danger-400'}>{n > 0 ? '+' : ''}{v as string}</span>
    },
  },
  {
    key: 'unit_cost',
    header: 'Unit Cost',
    sortable: false,
    render: v => `$${v}`,
  },
  {
    key: 'reference',
    header: 'Reference',
    sortable: false,
    render: v => <span className="text-text-muted">{(v as string) || '—'}</span>,
  },
]

export function InventorySearchPage() {
  const [query, setQuery] = useState('')
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [showLedger, setShowLedger] = useState(false)

  const { data: itemsData, isLoading } = useItems(query || undefined)
  const { data: ledgerData } = useItemLedger(showLedger ? selectedItem?.id ?? null : null)

  return (
    <PageWrapper title="Inventory Search" subtitle="Search items by SKU, name, or lot number.">
      <div className="space-y-6">
        <Card>
          <Input
            label="Search"
            value={query}
            onChange={setQuery}
            placeholder="SKU, item name…"
          />
        </Card>

        <DataTable<Record<string, unknown>>
          columns={itemColumns}
          data={(itemsData?.results ?? []).map(i => ({ ...i } as Record<string, unknown>))}
          rowKey="id"
          isLoading={isLoading}
          emptyMessage="No items found."
          onRowClick={row => {
            setSelectedItem(row as unknown as Item)
            setShowLedger(true)
          }}
        />
      </div>

      {/* Ledger drill-down modal */}
      <Modal
        isOpen={showLedger && selectedItem != null}
        onClose={() => { setShowLedger(false); setSelectedItem(null) }}
        title={`Ledger: ${selectedItem?.sku}`}
        size="xl"
        footer={
          <Button variant="secondary" onClick={() => { setShowLedger(false); setSelectedItem(null) }}>
            Close
          </Button>
        }
      >
        <div className="space-y-4">
          {selectedItem && (
            <div className="flex gap-4 text-sm p-3 bg-surface-700 rounded-lg">
              <div>
                <p className="text-text-muted">Name</p>
                <p className="font-semibold">{selectedItem.name}</p>
              </div>
              <div>
                <p className="text-text-muted">UOM</p>
                <p className="font-semibold">{selectedItem.unit_of_measure}</p>
              </div>
              <div>
                <p className="text-text-muted">Costing</p>
                <Badge variant={selectedItem.costing_method === 'FIFO' ? 'info' : 'neutral'}>
                  {selectedItem.costing_method}
                </Badge>
              </div>
              {selectedItem.total_on_hand !== undefined && (
                <div>
                  <p className="text-text-muted">Total On Hand</p>
                  <p className="font-semibold text-success-400">{selectedItem.total_on_hand}</p>
                </div>
              )}
            </div>
          )}

          <DataTable<Record<string, unknown>>
            columns={ledgerColumns}
            data={(ledgerData?.results ?? []).map(e => ({ ...e } as Record<string, unknown>))}
            rowKey="id"
            isLoading={showLedger && ledgerData === undefined}
            emptyMessage="No ledger entries for this item."
          />
        </div>
      </Modal>
    </PageWrapper>
  )
}
