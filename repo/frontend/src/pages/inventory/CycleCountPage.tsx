import { useState, useRef, useEffect } from 'react'
import { useDebounce } from '@/hooks/useDebounce'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Card } from '@/components/ui/Card'
import { BarcodeScanner } from '@/components/ui/BarcodeScanner'
import { useToast } from '@/hooks/useToast'
import {
  useItems,
  useWarehouses,
  useBins,
  useCycleCountStart,
  useCycleCountSubmit,
  useCycleCountConfirm,
  type CycleCountSession,
} from '@/hooks/useInventory'

type Step = 1 | 2 | 3 | 4

const REASON_CODES = [
  { value: 'COUNTING_ERROR', label: 'Counting Error' },
  { value: 'DAMAGE', label: 'Damage / Shrinkage' },
  { value: 'RECEIVING_ERROR', label: 'Receiving Error' },
  { value: 'THEFT', label: 'Theft / Shortage' },
  { value: 'OTHER', label: 'Other' },
]

export function CycleCountPage() {
  const toast = useToast()
  const scanRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>(1)
  const [session, setSession] = useState<CycleCountSession | null>(null)
  const [cameraOpen, setCameraOpen] = useState(false)

  // Step 1 form
  const [itemSearch, setItemSearch] = useState('')
  const debouncedItemSearch = useDebounce(itemSearch)
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [binId, setBinId] = useState<number | null>(null)

  // Step 2 form
  const [countedQty, setCountedQty] = useState('')

  // Step 3 form (supervisor confirmation)
  const [reasonCode, setReasonCode] = useState('')
  const [supervisorNote, setSupervisorNote] = useState('')

  const { data: itemsData } = useItems(debouncedItemSearch || undefined)
  const { data: warehousesData } = useWarehouses()
  const { data: binsData } = useBins(warehouseId)
  const startCount = useCycleCountStart()
  const submitCount = useCycleCountSubmit()
  const confirmCount = useCycleCountConfirm()

  useEffect(() => { scanRef.current?.focus() }, [])

  const selectedItem = itemsData?.results?.find(i => i.id === selectedItemId)

  function _resolveScanned(value: string) {
    const v = value.toLowerCase()
    return itemsData?.results?.find(
      i =>
        i.sku.toLowerCase() === v ||
        (i.barcode && i.barcode.toLowerCase() === v) ||
        (i.rfid_tag && i.rfid_tag.toLowerCase() === v)
    ) ?? null
  }

  function handleCameraDetected(code: string) {
    setItemSearch(code)
    setSelectedItemId(null)
    setCameraOpen(false)
    const match = _resolveScanned(code)
    if (match) { setSelectedItemId(match.id); setItemSearch(match.sku) }
    scanRef.current?.focus()
  }

  // ── Step 1: Start ──────────────────────────────────────────────────────────
  async function handleStart(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedItemId || !warehouseId) return
    try {
      const s = await startCount.mutateAsync({ item_id: selectedItemId, warehouse_id: warehouseId, bin_id: binId })
      setSession(s)
      setStep(2)
    } catch {
      toast.error('Failed to start count session.')
    }
  }

  // ── Step 2: Submit count ───────────────────────────────────────────────────
  async function handleSubmitCount(e: React.FormEvent) {
    e.preventDefault()
    if (!session || !countedQty) return
    try {
      const result = await submitCount.mutateAsync({ id: session.id, counted_qty: countedQty })
      setSession(result.session)
      if (result.variance_confirmation_required) {
        setStep(3)
      } else {
        setStep(4)
      }
    } catch {
      toast.error('Failed to submit count.')
    }
  }

  // ── Step 3: Supervisor confirmation ───────────────────────────────────────
  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault()
    if (!session || !reasonCode) return
    try {
      const s = await confirmCount.mutateAsync({ id: session.id, reason_code: reasonCode, supervisor_note: supervisorNote })
      setSession(s)
      setStep(4)
    } catch {
      toast.error('Confirmation failed.')
    }
  }

  function reset() {
    setStep(1); setSession(null)
    setItemSearch(''); setSelectedItemId(null)
    setWarehouseId(null); setBinId(null)
    setCountedQty('')
    setReasonCode(''); setSupervisorNote('')
  }

  const warehouseOptions = [
    { value: '', label: 'Select warehouse…' },
    ...(warehousesData?.results ?? []).map(w => ({ value: String(w.id), label: `${w.code} — ${w.name}` })),
  ]
  const binOptions = [
    { value: '', label: 'No specific bin' },
    ...(binsData?.results ?? []).map(b => ({ value: String(b.id), label: b.code })),
  ]

  const variance = session?.variance_qty ? Number(session.variance_qty) : null
  const varianceColor = variance === null ? '' : variance === 0 ? 'text-success-400' : Math.abs(variance) < 5 ? 'text-warning-400' : 'text-danger-400'

  return (
    <PageWrapper title="Cycle Count" subtitle="Step-by-step inventory count and variance posting.">
      <BarcodeScanner
        isOpen={cameraOpen}
        onDetected={handleCameraDetected}
        onClose={() => setCameraOpen(false)}
      />
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8 max-w-2xl">
        {([1, 2, 3, 4] as Step[]).map(s => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
              ${step === s ? 'bg-primary-600 text-white' : step > s ? 'bg-success-600 text-white' : 'bg-surface-600 text-text-muted'}`}>
              {step > s ? '✓' : s}
            </div>
            {s < 4 && <div className={`h-px w-12 ${step > s ? 'bg-success-600' : 'bg-surface-600'}`} />}
          </div>
        ))}
        <div className="ml-2 text-sm text-text-muted">
          {step === 1 && 'Select item & location'}
          {step === 2 && 'Enter actual count'}
          {step === 3 && 'Supervisor confirmation required'}
          {step === 4 && 'Count complete'}
        </div>
      </div>

      <div className="max-w-2xl">
        {/* Step 1 */}
        {step === 1 && (
          <form onSubmit={handleStart}>
            <Card className="space-y-4">
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <Input
                    ref={scanRef}
                    label="Search SKU or name"
                    value={itemSearch}
                    onChange={v => { setItemSearch(v); setSelectedItemId(null) }}
                    onKeyDown={e => { if (e.key === 'Enter') {
                      const match = _resolveScanned(itemSearch)
                      if (match) { setSelectedItemId(match.id); setItemSearch(match.sku) }
                    }}}
                    placeholder="Scan or type item…"
                  />
                </div>
                <button type="button" onClick={() => setCameraOpen(true)}
                  className="mb-0.5 p-2.5 min-h-touch rounded-xl border border-surface-600 bg-surface-800 text-text-muted hover:text-primary-400 hover:border-primary-500 transition-colors"
                  aria-label="Open camera scanner">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
                  </svg>
                </button>
              </div>
              {itemSearch && !selectedItemId && (itemsData?.results ?? []).length > 0 && (
                <ul className="border border-surface-600 rounded-lg overflow-hidden">
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
              {selectedItem && (
                <div className="p-3 bg-surface-700 rounded-lg text-sm">
                  <p className="font-semibold">{selectedItem.name}</p>
                  <p className="text-text-muted font-mono">{selectedItem.sku}</p>
                </div>
              )}
              <Select label="Warehouse" value={warehouseId ? String(warehouseId) : ''}
                onChange={v => { setWarehouseId(v ? Number(v) : null); setBinId(null) }}
                options={warehouseOptions} />
              {warehouseId && <Select label="Bin (optional)" value={binId ? String(binId) : ''}
                onChange={v => setBinId(v ? Number(v) : null)} options={binOptions} />}
              <Button type="submit" variant="primary" size="lg" className="w-full"
                loading={startCount.isPending} disabled={!selectedItemId || !warehouseId}>
                Start Count
              </Button>
            </Card>
          </form>
        )}

        {/* Step 2 — enter count (expected qty hidden until submitted to avoid bias) */}
        {step === 2 && session && (
          <form onSubmit={handleSubmitCount}>
            <Card className="space-y-4">
              <div className="p-3 bg-surface-700 rounded-lg text-sm">
                <p className="text-text-muted">Counting: <span className="font-semibold text-text-primary">{session.item_sku}</span></p>
                <p className="text-text-muted">Location: <span className="font-semibold text-text-primary">{session.warehouse_code}{session.bin_code ? ` / ${session.bin_code}` : ''}</span></p>
              </div>
              <p className="text-sm text-text-muted">
                Count the physical items at this location. Do not look at the expected quantity first.
              </p>
              <Input label="Actual Count" value={countedQty} onChange={setCountedQty}
                placeholder="0.0000" type="number" />
              <Button type="submit" variant="primary" size="lg" className="w-full"
                loading={submitCount.isPending} disabled={!countedQty}>
                Submit Count
              </Button>
            </Card>
          </form>
        )}

        {/* Step 3 — supervisor confirmation for high-value variance */}
        {step === 3 && session && (
          <form onSubmit={handleConfirm}>
            <Card className="space-y-4">
              <div className="p-4 bg-danger-950 border border-danger-700 rounded-lg">
                <p className="font-semibold text-danger-300 mb-2">Variance Requires Confirmation</p>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <p className="text-text-muted">Expected</p>
                    <p className="text-xl font-bold">{session.expected_qty}</p>
                  </div>
                  <div>
                    <p className="text-text-muted">Counted</p>
                    <p className="text-xl font-bold">{session.counted_qty}</p>
                  </div>
                  <div>
                    <p className="text-text-muted">Variance</p>
                    <p className={`text-xl font-bold ${varianceColor}`}>
                      {variance !== null && variance > 0 ? '+' : ''}{session.variance_qty}
                    </p>
                  </div>
                </div>
                {session.variance_value && (
                  <p className="mt-2 text-sm text-danger-300">
                    Estimated variance value: <strong>${session.variance_value}</strong>
                  </p>
                )}
              </div>
              <Select label="Reason Code" value={reasonCode} onChange={setReasonCode}
                options={[{ value: '', label: 'Select reason…' }, ...REASON_CODES]} />
              <Input label="Supervisor Notes" value={supervisorNote} onChange={setSupervisorNote}
                placeholder="Additional notes…" />
              <Button type="submit" variant="danger" size="lg" className="w-full"
                loading={confirmCount.isPending} disabled={!reasonCode}>
                Confirm & Post Adjustment
              </Button>
            </Card>
          </form>
        )}

        {/* Step 4 — complete */}
        {step === 4 && session && (
          <Card className="text-center space-y-4 py-8">
            <div className="w-16 h-16 rounded-full bg-success-900 flex items-center justify-center mx-auto">
              <span className="text-success-400 text-2xl">✓</span>
            </div>
            <h2 className="text-lg font-semibold text-text-primary">Count Complete</h2>
            {session.variance_qty !== null && Number(session.variance_qty) !== 0 ? (
              <div className="space-y-1 text-sm">
                <p className="text-text-muted">Variance posted to ledger:</p>
                <p className={`text-xl font-bold ${varianceColor}`}>
                  {Number(session.variance_qty) > 0 ? '+' : ''}{session.variance_qty} units
                </p>
                {session.variance_value && (
                  <p className="text-text-muted">Value: ${session.variance_value}</p>
                )}
              </div>
            ) : (
              <p className="text-text-muted text-sm">No variance — count matches system quantity.</p>
            )}
            <Button variant="primary" onClick={reset} className="mx-auto">
              Count Another Item
            </Button>
          </Card>
        )}
      </div>
    </PageWrapper>
  )
}
