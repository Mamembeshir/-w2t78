/**
 * useInventory.ts — React Query hooks for Inventory API (Phase 5).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Warehouse {
  id: number
  name: string
  code: string
  address: string
  is_active: boolean
  bin_count: number
}

export interface Bin {
  id: number
  warehouse: number
  warehouse_code: string
  code: string
  description: string
  is_active: boolean
}

export interface Item {
  id: number
  sku: string
  barcode: string
  rfid_tag: string
  name: string
  description: string
  unit_of_measure: string
  costing_method: 'FIFO' | 'MOVING_AVG'
  safety_stock_qty: string
  is_active: boolean
  slow_moving_flagged_at: string | null
  total_on_hand?: string
  total_reserved?: string
}

export interface ItemLot {
  id: number
  item: number
  lot_number: string
  expiry_date: string | null
  received_date: string
}

export interface StockBalance {
  id: number
  item: number
  item_sku: string
  item_name: string
  warehouse: number
  warehouse_code: string
  bin: number | null
  bin_code: string | null
  quantity_on_hand: string
  quantity_reserved: string
  avg_cost: string
  safety_stock_qty: string
  below_safety_stock: boolean
  updated_at: string
}

export interface LedgerEntry {
  id: number
  item: number
  item_sku: string
  warehouse: number
  warehouse_code: string
  bin: number | null
  bin_code: string | null
  lot: number | null
  lot_number: string | null
  quantity: string
  unit_cost: string
  costing_method: string
  transaction_type: string
  reference: string
  posted_by: number | null
  posted_by_username: string | null
  timestamp: string
}

export interface CycleCountSession {
  id: number
  item: number
  item_sku: string
  warehouse: number
  warehouse_code: string
  bin: number | null
  bin_code: string | null
  expected_qty: string
  counted_qty: string | null
  variance_qty: string | null
  variance_value: string | null
  status: 'OPEN' | 'PENDING_CONFIRM' | 'CONFIRMED' | 'CANCELLED'
  reason_code: string
  supervisor_note: string
  started_by: number | null
  started_by_username: string | null
  confirmed_by: number | null
  confirmed_by_username: string | null
  ledger_entry: number | null
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── Warehouses ────────────────────────────────────────────────────────────────

export function useWarehouses() {
  return useQuery<PaginatedResponse<Warehouse>>({
    queryKey: ['warehouses'],
    queryFn: () => api.get('/api/warehouses/?page_size=200').then(r => r.data),
  })
}

export function useBins(warehouseId: number | null) {
  return useQuery<PaginatedResponse<Bin>>({
    queryKey: ['bins', warehouseId],
    queryFn: () =>
      api.get(`/api/warehouses/${warehouseId}/bins/?page_size=200`).then(r => r.data),
    enabled: warehouseId != null,
  })
}

// ── Items ─────────────────────────────────────────────────────────────────────

export function useItems(query?: string) {
  return useQuery<PaginatedResponse<Item>>({
    queryKey: ['items', query],
    queryFn: () => {
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      return api.get(`/api/items/?${params}`).then(r => r.data)
    },
  })
}

/**
 * Exact-match scan resolution: resolves a barcode, RFID tag, or SKU scanned
 * by hardware to a single Item record.  The server searches sku, barcode, and
 * rfid_tag with a case-insensitive exact match.
 */
export function useScanItem(scanCode: string | null) {
  return useQuery<PaginatedResponse<Item>>({
    queryKey: ['items-scan', scanCode],
    queryFn: () => {
      const params = new URLSearchParams({ scan: scanCode! })
      return api.get(`/api/items/?${params}`).then(r => r.data)
    },
    enabled: !!scanCode,
  })
}

export function useItem(id: number | null) {
  return useQuery<Item>({
    queryKey: ['item', id],
    queryFn: () => api.get(`/api/items/${id}/`).then(r => r.data),
    enabled: id != null,
  })
}

export function useItemLots(itemId: number | null) {
  return useQuery<PaginatedResponse<ItemLot>>({
    queryKey: ['item-lots', itemId],
    queryFn: () => api.get(`/api/items/${itemId}/lots/`).then(r => r.data),
    enabled: itemId != null,
  })
}

export function useItemLedger(itemId: number | null) {
  return useQuery<PaginatedResponse<LedgerEntry>>({
    queryKey: ['item-ledger', itemId],
    queryFn: () => api.get(`/api/items/${itemId}/ledger/`).then(r => r.data),
    enabled: itemId != null,
  })
}

// ── Balances ──────────────────────────────────────────────────────────────────

export function useBalances(params?: {
  warehouse_id?: number
  item_id?: number
  below_safety?: boolean
}) {
  return useQuery<PaginatedResponse<StockBalance>>({
    queryKey: ['balances', params],
    queryFn: () => {
      const p = new URLSearchParams()
      if (params?.warehouse_id) p.set('warehouse_id', String(params.warehouse_id))
      if (params?.item_id) p.set('item_id', String(params.item_id))
      if (params?.below_safety) p.set('below_safety', 'true')
      return api.get(`/api/inventory/balances/?${p}`).then(r => r.data)
    },
  })
}

// ── Transaction mutations ─────────────────────────────────────────────────────

export function useReceiveStock() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      item_id: number
      warehouse_id: number
      bin_id?: number | null
      lot_id?: number | null
      quantity: string
      unit_cost: string
      reference?: string
    }) => api.post('/api/inventory/receive/', payload).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['balances'] })
      qc.invalidateQueries({ queryKey: ['item'] })
    },
  })
}

export function useIssueStock() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      item_id: number
      warehouse_id: number
      bin_id?: number | null
      lot_id?: number | null
      quantity: string
      reference?: string
    }) => api.post('/api/inventory/issue/', payload).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['balances'] })
      qc.invalidateQueries({ queryKey: ['item'] })
    },
  })
}

export function useTransferStock() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      item_id: number
      from_warehouse_id: number
      from_bin_id?: number | null
      to_warehouse_id: number
      to_bin_id?: number | null
      lot_id?: number | null
      quantity: string
      reference?: string
    }) => api.post('/api/inventory/transfer/', payload).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['balances'] })
    },
  })
}

// ── Cycle Count ───────────────────────────────────────────────────────────────

export function useCycleCountStart() {
  return useMutation({
    mutationFn: (payload: { item_id: number; warehouse_id: number; bin_id?: number | null }) =>
      api.post('/api/inventory/cycle-count/start/', payload).then(r => r.data as CycleCountSession),
  })
}

export function useCycleCountSubmit() {
  return useMutation({
    mutationFn: ({ id, counted_qty }: { id: number; counted_qty: string }) =>
      api
        .post(`/api/inventory/cycle-count/${id}/submit/`, { counted_qty })
        .then(r => r.data as { variance_confirmation_required: boolean; session: CycleCountSession }),
  })
}

export function useCycleCountConfirm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      reason_code,
      supervisor_note,
    }: {
      id: number
      reason_code: string
      supervisor_note?: string
    }) =>
      api
        .post(`/api/inventory/cycle-count/${id}/confirm/`, { reason_code, supervisor_note })
        .then(r => r.data as CycleCountSession),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['balances'] }),
  })
}
