import { useState } from 'react'
import { useDebounce } from '@/hooks/useDebounce'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Card } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/hooks/useToast'
import { useItems, useWarehouses, useBins, useBalances, useTransferStock } from '@/hooks/useInventory'

export function TransferPage() {
  const toast = useToast()

  const [itemSearch, setItemSearch] = useState('')
  const debouncedItemSearch = useDebounce(itemSearch)
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [fromWarehouseId, setFromWarehouseId] = useState<number | null>(null)
  const [fromBinId, setFromBinId] = useState<number | null>(null)
  const [toWarehouseId, setToWarehouseId] = useState<number | null>(null)
  const [toBinId, setToBinId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState('')
  const [reference, setReference] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)

  const { data: itemsData } = useItems(debouncedItemSearch || undefined)
  const { data: warehousesData } = useWarehouses()
  const { data: fromBinsData } = useBins(fromWarehouseId)
  const { data: toBinsData } = useBins(toWarehouseId)
  const { data: balancesData } = useBalances(
    selectedItemId && fromWarehouseId
      ? { item_id: selectedItemId, warehouse_id: fromWarehouseId }
      : undefined
  )
  const transfer = useTransferStock()

  const selectedItem = itemsData?.results.find(i => i.id === selectedItemId)
  const fromBalance = balancesData?.results.find(
    b => b.item === selectedItemId && b.warehouse === fromWarehouseId && b.bin === fromBinId
  )
  const availableQty = fromBalance ? Number(fromBalance.quantity_on_hand) : null
  const requestedQty = quantity ? Number(quantity) : null
  const qtyExceeded = availableQty !== null && requestedQty !== null && requestedQty > availableQty

  const canSubmit = selectedItemId && fromWarehouseId && toWarehouseId && quantity && !qtyExceeded
    && !(fromWarehouseId === toWarehouseId && fromBinId === toBinId)

  async function handleConfirm() {
    setShowConfirm(false)
    try {
      await transfer.mutateAsync({
        item_id: selectedItemId!,
        from_warehouse_id: fromWarehouseId!,
        from_bin_id: fromBinId,
        to_warehouse_id: toWarehouseId!,
        to_bin_id: toBinId,
        quantity,
        reference,
      })
      toast.success(`Transferred ${quantity} × ${selectedItem?.sku}.`)
      setSelectedItemId(null); setItemSearch(''); setQuantity(''); setReference('')
      setFromWarehouseId(null); setFromBinId(null)
      setToWarehouseId(null); setToBinId(null)
    } catch (err: unknown) {
      const data = (err as { response?: { data?: { message?: string } } })?.response?.data
      toast.error(data?.message ?? 'Transfer failed.')
    }
  }

  const warehouseOptions = [
    { value: '', label: 'Select warehouse…' },
    ...(warehousesData?.results ?? []).map(w => ({ value: String(w.id), label: `${w.code} — ${w.name}` })),
  ]

  function binOptions(binsData: typeof fromBinsData) {
    return [
      { value: '', label: 'No specific bin' },
      ...(binsData?.results ?? []).map(b => ({ value: String(b.id), label: b.code })),
    ]
  }

  return (
    <PageWrapper title="Transfer Stock" subtitle="Move stock between warehouses or bins.">
      <div className="max-w-2xl space-y-6">
        {/* Item */}
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wide">Item</h3>
          <Input label="Search SKU or name" value={itemSearch}
            onChange={v => { setItemSearch(v); setSelectedItemId(null) }}
            placeholder="Type to search…" />
          {itemSearch && !selectedItemId && (itemsData?.results ?? []).length > 0 && (
            <ul className="mt-2 border border-surface-600 rounded-lg overflow-hidden">
              {(itemsData?.results ?? []).slice(0, 5).map(item => (
                <li key={item.id}>
                  <button type="button" className="w-full text-left px-4 py-2 hover:bg-surface-700 text-sm"
                    onClick={() => { setSelectedItemId(item.id); setItemSearch(item.sku) }}>
                    <span className="font-mono text-primary-400">{item.sku}</span>
                    <span className="text-text-secondary ml-2">{item.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Source */}
        <Card className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">From</h3>
          <Select label="Source Warehouse" value={fromWarehouseId ? String(fromWarehouseId) : ''}
            onChange={v => { setFromWarehouseId(v ? Number(v) : null); setFromBinId(null) }}
            options={warehouseOptions} />
          {fromWarehouseId && <Select label="Source Bin (optional)" value={fromBinId ? String(fromBinId) : ''}
            onChange={v => setFromBinId(v ? Number(v) : null)} options={binOptions(fromBinsData)} />}
          {fromBalance && (
            <div className="text-sm px-3 py-2 bg-surface-700 rounded-lg">
              <span className="text-text-muted">Available: </span>
              <span className={`font-semibold ${Number(fromBalance.quantity_on_hand) <= 0 ? 'text-danger-400' : 'text-success-400'}`}>
                {fromBalance.quantity_on_hand} {selectedItem?.unit_of_measure}
              </span>
            </div>
          )}
        </Card>

        {/* Destination */}
        <Card className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">To</h3>
          <Select label="Destination Warehouse" value={toWarehouseId ? String(toWarehouseId) : ''}
            onChange={v => { setToWarehouseId(v ? Number(v) : null); setToBinId(null) }}
            options={warehouseOptions} />
          {toWarehouseId && <Select label="Destination Bin (optional)" value={toBinId ? String(toBinId) : ''}
            onChange={v => setToBinId(v ? Number(v) : null)} options={binOptions(toBinsData)} />}
        </Card>

        {/* Quantity & ref */}
        <Card className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">Quantity</h3>
          <Input label="Transfer Quantity" value={quantity} onChange={setQuantity}
            placeholder="0.0000" type="number"
            error={qtyExceeded ? `Exceeds available stock (${availableQty})` : undefined} />
          <Input label="Reference (optional)" value={reference} onChange={setReference}
            placeholder="Transfer note…" />
          <Button type="button" variant="primary" size="lg" className="w-full"
            disabled={!canSubmit} onClick={() => setShowConfirm(true)}>
            Review Transfer
          </Button>
        </Card>
      </div>

      {/* Confirmation modal */}
      <Modal
        isOpen={showConfirm}
        onClose={() => setShowConfirm(false)}
        title="Confirm Transfer"
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowConfirm(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleConfirm} loading={transfer.isPending}>
              Confirm Transfer
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-sm">
          <div className="flex justify-between py-2 border-b border-surface-600">
            <span className="text-text-muted">Item</span>
            <span className="font-mono font-semibold">{selectedItem?.sku}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-surface-600">
            <span className="text-text-muted">From</span>
            <span>{warehousesData?.results.find(w => w.id === fromWarehouseId)?.code}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-surface-600">
            <span className="text-text-muted">To</span>
            <span>{warehousesData?.results.find(w => w.id === toWarehouseId)?.code}</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-text-muted">Quantity</span>
            <span className="font-semibold text-lg">{quantity} {selectedItem?.unit_of_measure}</span>
          </div>
        </div>
      </Modal>
    </PageWrapper>
  )
}
