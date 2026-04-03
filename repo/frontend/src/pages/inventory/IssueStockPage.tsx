import { useState, useRef, useEffect } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { DataTable } from '@/components/ui/DataTable'
import { useToast } from '@/hooks/useToast'
import { extractFieldErrors, extractMessage } from '@/lib/formErrors'
import {
  useItems,
  useWarehouses,
  useBins,
  useItemLots,
  useBalances,
  useIssueStock,
  type LedgerEntry,
} from '@/hooks/useInventory'
import type { Column } from '@/types'

const lotColumns: Column<Record<string, unknown>>[] = [
  { key: 'lot_number', header: 'Lot', sortable: false },
  { key: 'received_date', header: 'Received', sortable: true },
  { key: 'expiry_date', header: 'Expires', sortable: true, render: v => (v as string | null) ?? '—' },
]

export function IssueStockPage() {
  const toast = useToast()
  const scanRef = useRef<HTMLInputElement>(null)

  const [scanValue, setScanValue] = useState('')
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [binId, setBinId] = useState<number | null>(null)
  const [lotId, setLotId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState('')
  const [reference, setReference] = useState('')
  const [issuedEntries, setIssuedEntries] = useState<LedgerEntry[]>([])
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const { data: itemsData } = useItems(scanValue || undefined)
  const { data: warehousesData } = useWarehouses()
  const { data: binsData } = useBins(warehouseId)
  const { data: lotsData } = useItemLots(selectedItemId)
  const { data: balancesData } = useBalances(
    selectedItemId && warehouseId
      ? { item_id: selectedItemId, warehouse_id: warehouseId }
      : undefined
  )
  const issueStock = useIssueStock()

  useEffect(() => { scanRef.current?.focus() }, [])

  const selectedItem = itemsData?.results.find(i => i.id === selectedItemId)
  const currentBalance = balancesData?.results.find(
    b => b.item === selectedItemId && b.warehouse === warehouseId && b.bin === binId
  )

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedItemId || !warehouseId || !quantity) return

    try {
      const result = await issueStock.mutateAsync({
        item_id: selectedItemId,
        warehouse_id: warehouseId,
        bin_id: binId,
        lot_id: lotId,
        quantity,
        reference,
      })
      setIssuedEntries(result.ledger_entries as LedgerEntry[])
      toast.success(`Issued ${quantity} × ${selectedItem?.sku}.`)
      setScanValue(''); setSelectedItemId(null); setQuantity(''); setReference('')
      setBinId(null); setLotId(null)
      scanRef.current?.focus()
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string; code?: string } } })?.response?.data
      if (data?.code === 'insufficient_stock') {
        toast.error(`Insufficient stock: ${data.message}`)
      } else {
        const fe = extractFieldErrors(err)
        if (Object.keys(fe).length) {
          setFieldErrors(fe)
        } else {
          toast.error(extractMessage(err, 'Issue failed.'))
        }
      }
    }
  }

  const warehouseOptions = [
    { value: '', label: 'Select warehouse…' },
    ...(warehousesData?.results ?? []).map(w => ({ value: String(w.id), label: `${w.code} — ${w.name}` })),
  ]
  const binOptions = [
    { value: '', label: 'No specific bin' },
    ...(binsData?.results ?? []).map(b => ({ value: String(b.id), label: b.code })),
  ]
  const lotOptions = [
    { value: '', label: 'Auto FIFO' },
    ...(lotsData?.results ?? []).map(l => ({ value: String(l.id), label: l.lot_number })),
  ]

  const availableQty = currentBalance ? Number(currentBalance.quantity_on_hand) : null
  const requestedQty = quantity ? Number(quantity) : null
  const qtyExceeded = availableQty !== null && requestedQty !== null && requestedQty > availableQty

  return (
    <PageWrapper title="Issue Stock" subtitle="Issue stock from a warehouse location for a work order.">
      <div className="max-w-2xl">
        {/* Scan */}
        <Card className="mb-6">
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">Item Lookup</h3>
          <Input
            ref={scanRef}
            label="Scan barcode or enter SKU"
            value={scanValue}
            onChange={v => { setScanValue(v); setSelectedItemId(null) }}
            onKeyDown={e => { if (e.key === 'Enter') {
              const match = itemsData?.results.find(i => i.sku.toLowerCase() === scanValue.toLowerCase())
              if (match) { setSelectedItemId(match.id); setScanValue(match.sku) }
            }}}
            placeholder="Scan or type SKU…"
          />
          {scanValue && !selectedItemId && (itemsData?.results ?? []).length > 0 && (
            <ul className="mt-2 border border-surface-600 rounded-lg overflow-hidden">
              {(itemsData?.results ?? []).slice(0, 5).map(item => (
                <li key={item.id}>
                  <button type="button" className="w-full text-left px-4 py-2 hover:bg-surface-700 text-sm"
                    onClick={() => { setSelectedItemId(item.id); setScanValue(item.sku) }}>
                    <span className="font-mono text-primary-400">{item.sku}</span>
                    <span className="text-text-secondary ml-2">{item.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {selectedItem && (
            <div className="mt-3 flex items-center gap-3 p-3 bg-surface-700 rounded-lg">
              <div className="flex-1">
                <p className="font-semibold">{selectedItem.name}</p>
                <p className="text-sm text-text-muted font-mono">{selectedItem.sku} · {selectedItem.costing_method}</p>
              </div>
              {selectedItem.costing_method === 'FIFO' && <Badge variant="info">FIFO</Badge>}
              {selectedItem.costing_method === 'MOVING_AVG' && <Badge variant="neutral">Avg Cost</Badge>}
            </div>
          )}
        </Card>

        {/* Available lots (FIFO info) */}
        {selectedItemId && selectedItem?.costing_method === 'FIFO' && lotsData && lotsData.results.length > 0 && (
          <Card className="mb-6">
            <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
              Available Lots (FIFO Order)
            </h3>
            <DataTable<Record<string, unknown>>
              columns={lotColumns}
              data={lotsData.results.map(l => ({ ...l } as Record<string, unknown>))}
              rowKey="id"
            />
          </Card>
        )}

        {/* Issue form */}
        <form onSubmit={handleSubmit}>
          <Card className="space-y-4">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">Issue Details</h3>

            <Select label="Warehouse" value={warehouseId ? String(warehouseId) : ''}
              onChange={v => { setWarehouseId(v ? Number(v) : null); setBinId(null) }}
              options={warehouseOptions} />

            {warehouseId && <Select label="Bin (optional)" value={binId ? String(binId) : ''}
              onChange={v => setBinId(v ? Number(v) : null)} options={binOptions} />}

            {selectedItemId && selectedItem?.costing_method === 'FIFO' && (
              <Select label="Lot (optional — leave blank for auto FIFO)"
                value={lotId ? String(lotId) : ''}
                onChange={v => setLotId(v ? Number(v) : null)} options={lotOptions} />
            )}

            {currentBalance && (
              <div className="px-3 py-2 bg-surface-700 rounded-lg text-sm">
                <span className="text-text-muted">Available: </span>
                <span className={`font-semibold ${Number(currentBalance.quantity_on_hand) <= 0 ? 'text-danger-400' : 'text-success-400'}`}>
                  {currentBalance.quantity_on_hand} {selectedItem?.unit_of_measure}
                </span>
              </div>
            )}

            <Input
              label="Quantity"
              value={quantity}
              onChange={v => { setQuantity(v); setFieldErrors(e => { const n={...e}; delete n.quantity; return n }) }}
              placeholder="0.0000"
              type="number"
              error={qtyExceeded ? `Exceeds available stock (${availableQty})` : fieldErrors.quantity}
            />

            <Input label="Work Order / Reference" value={reference} onChange={setReference}
              placeholder="WO-12345, pick ticket…"
              error={fieldErrors.reference} />

            <div className="pt-2">
              <Button type="submit" variant="primary" size="lg" className="w-full"
                loading={issueStock.isPending}
                disabled={!selectedItemId || !warehouseId || !quantity || qtyExceeded}>
                Post Issue
              </Button>
            </div>
          </Card>
        </form>

        {/* Result */}
        {issuedEntries.length > 0 && (
          <Card className="mt-6">
            <h3 className="text-sm font-semibold text-success-400 mb-3">Issue Posted — Lots Consumed</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-text-muted border-b border-surface-600">
                  <th className="text-left pb-2">Lot</th>
                  <th className="text-right pb-2">Qty</th>
                  <th className="text-right pb-2">Unit Cost</th>
                  <th className="text-right pb-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {issuedEntries.map(e => (
                  <tr key={e.id} className="border-b border-surface-700">
                    <td className="py-2">{e.lot_number ?? '—'}</td>
                    <td className="text-right py-2">{Math.abs(Number(e.quantity))}</td>
                    <td className="text-right py-2">${e.unit_cost}</td>
                    <td className="text-right py-2">${(Math.abs(Number(e.quantity)) * Number(e.unit_cost)).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </PageWrapper>
  )
}
