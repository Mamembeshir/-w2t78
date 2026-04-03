import { useState, useRef, useEffect } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/hooks/useToast'
import {
  useItems,
  useWarehouses,
  useBins,
  useItemLots,
  useReceiveStock,
} from '@/hooks/useInventory'

export function ReceiveStockPage() {
  const toast = useToast()
  const scanRef = useRef<HTMLInputElement>(null)

  const [scanValue, setScanValue] = useState('')
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [binId, setBinId] = useState<number | null>(null)
  const [lotId, setLotId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [reference, setReference] = useState('')
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null)

  const { data: itemsData } = useItems(scanValue || undefined)
  const { data: warehousesData } = useWarehouses()
  const { data: binsData } = useBins(warehouseId)
  const { data: lotsData } = useItemLots(selectedItemId)
  const receive = useReceiveStock()

  // Auto-focus scan field on mount
  useEffect(() => { scanRef.current?.focus() }, [])

  function handleScanEnter(value: string) {
    const match = itemsData?.results.find(
      i => i.sku.toLowerCase() === value.toLowerCase()
    )
    if (match) {
      setSelectedItemId(match.id)
      setScanValue(match.sku)
    }
  }

  const selectedItem = itemsData?.results.find(i => i.id === selectedItemId)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedItemId || !warehouseId || !quantity || !unitCost) return

    try {
      const result = await receive.mutateAsync({
        item_id: selectedItemId,
        warehouse_id: warehouseId,
        bin_id: binId,
        lot_id: lotId,
        quantity,
        unit_cost: unitCost,
        reference,
      })
      setLastResult(result)
      toast.success(`Received ${quantity} × ${selectedItem?.sku} — balance updated.`)
      // Reset form
      setScanValue('')
      setSelectedItemId(null)
      setQuantity('')
      setUnitCost('')
      setReference('')
      setBinId(null)
      setLotId(null)
      scanRef.current?.focus()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? 'Receive failed.'
      toast.error(msg)
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
    { value: '', label: 'No lot' },
    ...(lotsData?.results ?? []).map(l => ({ value: String(l.id), label: l.lot_number })),
  ]

  return (
    <PageWrapper title="Receive Stock" subtitle="Record incoming stock into a warehouse location.">
      <div className="max-w-2xl">
        {/* Scan / lookup field */}
        <Card className="mb-6">
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
            Item Lookup
          </h3>
          <Input
            ref={scanRef}
            label="Scan barcode or enter SKU"
            value={scanValue}
            onChange={v => { setScanValue(v); setSelectedItemId(null) }}
            onKeyDown={e => { if (e.key === 'Enter') handleScanEnter(scanValue) }}
            placeholder="Scan or type SKU…"
            helpText="Barcode scanner (keyboard wedge) or manual entry — press Enter to look up."
          />
          {/* Live search suggestions */}
          {scanValue && !selectedItemId && (itemsData?.results ?? []).length > 0 && (
            <ul className="mt-2 border border-surface-600 rounded-lg overflow-hidden">
              {(itemsData?.results ?? []).slice(0, 5).map(item => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="w-full text-left px-4 py-2 hover:bg-surface-700 text-sm"
                    onClick={() => { setSelectedItemId(item.id); setScanValue(item.sku) }}
                  >
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
                <p className="font-semibold text-text-primary">{selectedItem.name}</p>
                <p className="text-sm text-text-muted font-mono">{selectedItem.sku} · {selectedItem.unit_of_measure} · {selectedItem.costing_method}</p>
              </div>
              <Badge variant="success">Found</Badge>
            </div>
          )}
        </Card>

        {/* Receive form */}
        <form onSubmit={handleSubmit}>
          <Card className="space-y-4">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
              Receipt Details
            </h3>

            <Select
              label="Warehouse"
              value={warehouseId ? String(warehouseId) : ''}
              onChange={v => { setWarehouseId(v ? Number(v) : null); setBinId(null) }}
              options={warehouseOptions}
            />

            {warehouseId && (
              <Select
                label="Bin (optional)"
                value={binId ? String(binId) : ''}
                onChange={v => setBinId(v ? Number(v) : null)}
                options={binOptions}
              />
            )}

            {selectedItemId && (
              <Select
                label="Lot (optional)"
                value={lotId ? String(lotId) : ''}
                onChange={v => setLotId(v ? Number(v) : null)}
                options={lotOptions}
              />
            )}

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Quantity"
                value={quantity}
                onChange={setQuantity}
                placeholder="0.0000"
                type="number"
              />
              <Input
                label="Unit Cost"
                value={unitCost}
                onChange={setUnitCost}
                placeholder="0.000000"
                type="number"
                prefix="$"
              />
            </div>

            <Input
              label="Reference (optional)"
              value={reference}
              onChange={setReference}
              placeholder="PO number, delivery note…"
            />

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                loading={receive.isPending}
                disabled={!selectedItemId || !warehouseId || !quantity || !unitCost}
              >
                Post Receipt
              </Button>
            </div>
          </Card>
        </form>

        {/* Last result */}
        {lastResult && (() => {
          const bal = lastResult.balance as Record<string, string> | undefined
          if (!bal) return null
          return (
            <Card className="mt-6">
              <h3 className="text-sm font-semibold text-success-400 mb-3">Receipt Posted</h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-text-muted">On Hand</p>
                  <p className="text-text-primary font-semibold text-lg">{bal.quantity_on_hand}</p>
                </div>
                <div>
                  <p className="text-text-muted">Avg Cost</p>
                  <p className="text-text-primary font-semibold text-lg">${bal.avg_cost}</p>
                </div>
                <div>
                  <p className="text-text-muted">Location</p>
                  <p className="text-text-primary font-semibold text-lg">{bal.warehouse_code}</p>
                </div>
              </div>
            </Card>
          )
        })()}
      </div>
    </PageWrapper>
  )
}
