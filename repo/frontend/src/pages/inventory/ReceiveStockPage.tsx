import { useState, useRef, useEffect } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { BarcodeScanner } from '@/components/ui/BarcodeScanner'
import { useToast } from '@/hooks/useToast'
import { extractFieldErrors, extractMessage } from '@/lib/formErrors'
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
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [cameraOpen, setCameraOpen] = useState(false)

  const { data: itemsData } = useItems(scanValue || undefined)
  const { data: warehousesData } = useWarehouses()
  const { data: binsData } = useBins(warehouseId)
  const { data: lotsData } = useItemLots(selectedItemId)
  const receive = useReceiveStock()

  // Auto-focus scan field on mount
  useEffect(() => { scanRef.current?.focus() }, [])

  function handleScanEnter(value: string) {
    const match = itemsData?.results?.find(
      i => i.sku.toLowerCase() === value.toLowerCase()
    )
    if (match) {
      setSelectedItemId(match.id)
      setScanValue(match.sku)
    }
  }

  function handleCameraDetected(code: string) {
    setScanValue(code)
    setCameraOpen(false)
    // Attempt direct match; user can press Enter if not found
    const match = itemsData?.results?.find(
      i => i.sku.toLowerCase() === code.toLowerCase()
    )
    if (match) {
      setSelectedItemId(match.id)
      setScanValue(match.sku)
    }
    scanRef.current?.focus()
  }

  const selectedItem = itemsData?.results?.find(i => i.id === selectedItemId)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedItemId || !warehouseId || !quantity || !unitCost) return
    setFieldErrors({})

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
      setFieldErrors({})
      scanRef.current?.focus()
    } catch (err: unknown) {
      const fe = extractFieldErrors(err)
      if (Object.keys(fe).length) {
        setFieldErrors(fe)
      } else {
        toast.error(extractMessage(err, 'Receive failed.'))
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
    { value: '', label: 'No lot' },
    ...(lotsData?.results ?? []).map(l => ({ value: String(l.id), label: l.lot_number })),
  ]

  return (
    <PageWrapper title="Receive Stock" subtitle="Record incoming stock into a warehouse location.">
      <BarcodeScanner
        isOpen={cameraOpen}
        onDetected={handleCameraDetected}
        onClose={() => setCameraOpen(false)}
      />

      <div className="max-w-2xl">
        {/* Scan / lookup field */}
        <Card className="mb-6">
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">
            Item Lookup
          </h3>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Input
                ref={scanRef}
                label="Scan barcode or enter SKU"
                value={scanValue}
                onChange={v => { setScanValue(v); setSelectedItemId(null) }}
                onKeyDown={e => { if (e.key === 'Enter') handleScanEnter(scanValue) }}
                placeholder="Scan or type SKU…"
                helpText="Keyboard wedge, manual entry, or use the camera button."
              />
            </div>
            <button
              type="button"
              title="Use camera to scan barcode"
              onClick={() => setCameraOpen(true)}
              className="mb-5 p-2.5 min-h-touch rounded-xl border border-surface-600 bg-surface-800 text-text-muted hover:text-primary-400 hover:border-primary-500 transition-colors"
              aria-label="Open camera scanner"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
              </svg>
            </button>
          </div>
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
                onChange={v => { setQuantity(v); setFieldErrors(e => { const n={...e}; delete n.quantity; return n }) }}
                placeholder="0.0000"
                type="number"
                error={fieldErrors.quantity}
              />
              <Input
                label="Unit Cost"
                value={unitCost}
                onChange={v => { setUnitCost(v); setFieldErrors(e => { const n={...e}; delete n.unit_cost; return n }) }}
                placeholder="0.000000"
                type="number"
                prefix="$"
                error={fieldErrors.unit_cost}
              />
            </div>

            <Input
              label="Reference (optional)"
              value={reference}
              onChange={setReference}
              placeholder="PO number, delivery note…"
              error={fieldErrors.reference}
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
