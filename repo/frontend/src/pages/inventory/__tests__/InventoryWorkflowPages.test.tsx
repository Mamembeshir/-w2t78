/**
 * Smoke tests for inventory workflow pages:
 * ReceiveStockPage, IssueStockPage, TransferPage, CycleCountPage, InventorySearchPage.
 *
 * Each page is verified to render without crashing across loading, empty, and
 * populated data states. Mutations and hardware APIs (camera) are mocked.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Shared mocks ──────────────────────────────────────────────────────────────

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

// BarcodeScanner accesses navigator.mediaDevices — mock it for JSDOM
vi.mock('@/components/ui/BarcodeScanner', () => ({
  BarcodeScanner: () => <div data-testid="barcode-scanner" />,
}))

// useDebounce: return the value immediately (no real timer in unit tests)
vi.mock('@/hooks/useDebounce', () => ({
  useDebounce: <T,>(v: T) => v,
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

// ── useInventory mocks ────────────────────────────────────────────────────────

vi.mock('@/hooks/useInventory', () => ({
  useItems:            vi.fn(),
  useWarehouses:       vi.fn(),
  useBins:             vi.fn(),
  useItemLots:         vi.fn(),
  useBalances:         vi.fn(),
  useReceiveStock:     vi.fn(),
  useIssueStock:       vi.fn(),
  useTransferStock:    vi.fn(),
  useCycleCountStart:  vi.fn(),
  useCycleCountSubmit: vi.fn(),
  useCycleCountConfirm: vi.fn(),
  useItemLedger:       vi.fn(),
}))

import {
  useItems, useWarehouses, useBins, useItemLots, useBalances,
  useReceiveStock, useIssueStock, useTransferStock,
  useCycleCountStart, useCycleCountSubmit, useCycleCountConfirm,
  useItemLedger,
} from '@/hooks/useInventory'

const NOOP = { isPending: false, mutateAsync: vi.fn() }

const MOCK_WAREHOUSE = {
  id: 1, name: 'Main WH', code: 'WH-A',
  address: '1 Main St', is_active: true, bin_count: 5,
}

const MOCK_BIN = {
  id: 10, warehouse: 1, warehouse_code: 'WH-A',
  code: 'BIN-01', description: 'Rack 1', is_active: true,
}

const MOCK_ITEM = {
  id: 1, sku: 'SKU-001', barcode: null, rfid_tag: null,
  name: 'Widget A', unit_of_measure: 'EA',
  costing_method: 'FIFO' as const,
  safety_stock_qty: '5',
  slow_moving_flagged_at: null,
  total_on_hand: '15',
  total_reserved: '0',
}

const EMPTY_PAGED = { count: 0, results: [] }
const LOADING = { data: undefined, isLoading: true }

// ── ReceiveStockPage ──────────────────────────────────────────────────────────

import { ReceiveStockPage } from '../ReceiveStockPage'

function setupReceive(opts: { loading?: boolean; withData?: boolean } = {}) {
  const q = opts.loading ? LOADING : { data: opts.withData ? { count: 1, results: [MOCK_ITEM] } : EMPTY_PAGED, isLoading: false }
  const wh = opts.loading ? LOADING : { data: opts.withData ? { count: 1, results: [MOCK_WAREHOUSE] } : EMPTY_PAGED, isLoading: false }
  vi.mocked(useItems).mockReturnValue(q as ReturnType<typeof useItems>)
  vi.mocked(useWarehouses).mockReturnValue(wh as ReturnType<typeof useWarehouses>)
  vi.mocked(useBins).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBins>)
  vi.mocked(useItemLots).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItemLots>)
  vi.mocked(useReceiveStock).mockReturnValue(NOOP as ReturnType<typeof useReceiveStock>)
}

describe('ReceiveStockPage — loading', () => {
  beforeEach(() => setupReceive({ loading: true }))
  it('renders page title', () => {
    render(<MemoryRouter><ReceiveStockPage /></MemoryRouter>)
    expect(screen.getByText('Receive Stock')).toBeInTheDocument()
  })
  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><ReceiveStockPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('ReceiveStockPage — empty state', () => {
  beforeEach(() => setupReceive())
  it('renders scan/lookup field label', () => {
    render(<MemoryRouter><ReceiveStockPage /></MemoryRouter>)
    expect(screen.getByText('Item Lookup')).toBeInTheDocument()
  })
  it('shows warehouse select placeholder', () => {
    render(<MemoryRouter><ReceiveStockPage /></MemoryRouter>)
    expect(screen.getByText('Select warehouse…')).toBeInTheDocument()
  })
})

describe('ReceiveStockPage — null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useItems).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useWarehouses).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useWarehouses>)
    vi.mocked(useBins).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBins>)
    vi.mocked(useItemLots).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItemLots>)
    vi.mocked(useReceiveStock).mockReturnValue(NOOP as ReturnType<typeof useReceiveStock>)
    expect(() => render(<MemoryRouter><ReceiveStockPage /></MemoryRouter>)).not.toThrow()
  })
})

// ── IssueStockPage ────────────────────────────────────────────────────────────

import { IssueStockPage } from '../IssueStockPage'

function setupIssue(opts: { loading?: boolean } = {}) {
  const q = opts.loading ? LOADING : { data: EMPTY_PAGED, isLoading: false }
  vi.mocked(useItems).mockReturnValue(q as ReturnType<typeof useItems>)
  vi.mocked(useWarehouses).mockReturnValue(q as ReturnType<typeof useWarehouses>)
  vi.mocked(useBins).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBins>)
  vi.mocked(useItemLots).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItemLots>)
  vi.mocked(useBalances).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBalances>)
  vi.mocked(useIssueStock).mockReturnValue(NOOP as ReturnType<typeof useIssueStock>)
}

describe('IssueStockPage — loading', () => {
  beforeEach(() => setupIssue({ loading: true }))
  it('renders page title', () => {
    render(<MemoryRouter><IssueStockPage /></MemoryRouter>)
    expect(screen.getByText('Issue Stock')).toBeInTheDocument()
  })
  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><IssueStockPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('IssueStockPage — empty state', () => {
  beforeEach(() => setupIssue())
  it('renders scan/lookup field', () => {
    render(<MemoryRouter><IssueStockPage /></MemoryRouter>)
    expect(screen.getByText('Item Lookup')).toBeInTheDocument()
  })
  it('shows warehouse select', () => {
    render(<MemoryRouter><IssueStockPage /></MemoryRouter>)
    expect(screen.getByText('Select warehouse…')).toBeInTheDocument()
  })
})

describe('IssueStockPage — null handling', () => {
  it('does not crash when all data is null', () => {
    vi.mocked(useItems).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useWarehouses).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useWarehouses>)
    vi.mocked(useBins).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBins>)
    vi.mocked(useItemLots).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItemLots>)
    vi.mocked(useBalances).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBalances>)
    vi.mocked(useIssueStock).mockReturnValue(NOOP as ReturnType<typeof useIssueStock>)
    expect(() => render(<MemoryRouter><IssueStockPage /></MemoryRouter>)).not.toThrow()
  })
})

// ── TransferPage ──────────────────────────────────────────────────────────────

import { TransferPage } from '../TransferPage'

function setupTransfer(opts: { loading?: boolean; withWarehouses?: boolean } = {}) {
  const q = opts.loading ? LOADING : { data: EMPTY_PAGED, isLoading: false }
  const wh = opts.withWarehouses
    ? { data: { count: 2, results: [MOCK_WAREHOUSE, { ...MOCK_WAREHOUSE, id: 2, name: 'Warehouse B', code: 'WH-B' }] }, isLoading: false }
    : q
  vi.mocked(useItems).mockReturnValue(q as ReturnType<typeof useItems>)
  vi.mocked(useWarehouses).mockReturnValue(wh as ReturnType<typeof useWarehouses>)
  vi.mocked(useBins).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBins>)
  vi.mocked(useBalances).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBalances>)
  vi.mocked(useTransferStock).mockReturnValue(NOOP as ReturnType<typeof useTransferStock>)
}

describe('TransferPage — loading', () => {
  beforeEach(() => setupTransfer({ loading: true }))
  it('renders page title', () => {
    render(<MemoryRouter><TransferPage /></MemoryRouter>)
    expect(screen.getByText('Transfer Stock')).toBeInTheDocument()
  })
  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><TransferPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('TransferPage — with warehouse data', () => {
  beforeEach(() => setupTransfer({ withWarehouses: true }))
  it('renders From and To warehouse selectors', () => {
    render(<MemoryRouter><TransferPage /></MemoryRouter>)
    // At least one "Select warehouse…" placeholder visible
    expect(screen.getAllByText('Select warehouse…').length).toBeGreaterThanOrEqual(1)
  })
})

describe('TransferPage — null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useItems).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useWarehouses).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useWarehouses>)
    vi.mocked(useBins).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBins>)
    vi.mocked(useBalances).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBalances>)
    vi.mocked(useTransferStock).mockReturnValue(NOOP as ReturnType<typeof useTransferStock>)
    expect(() => render(<MemoryRouter><TransferPage /></MemoryRouter>)).not.toThrow()
  })
})

// ── CycleCountPage ────────────────────────────────────────────────────────────

import { CycleCountPage } from '../CycleCountPage'

function setupCycleCount() {
  vi.mocked(useItems).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItems>)
  vi.mocked(useWarehouses).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useWarehouses>)
  vi.mocked(useBins).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useBins>)
  vi.mocked(useCycleCountStart).mockReturnValue(NOOP as ReturnType<typeof useCycleCountStart>)
  vi.mocked(useCycleCountSubmit).mockReturnValue(NOOP as ReturnType<typeof useCycleCountSubmit>)
  vi.mocked(useCycleCountConfirm).mockReturnValue(NOOP as ReturnType<typeof useCycleCountConfirm>)
}

describe('CycleCountPage — step 1', () => {
  beforeEach(() => setupCycleCount())

  it('renders page title', () => {
    render(<MemoryRouter><CycleCountPage /></MemoryRouter>)
    expect(screen.getByText('Cycle Count')).toBeInTheDocument()
  })

  it('shows step 1 prompt', () => {
    render(<MemoryRouter><CycleCountPage /></MemoryRouter>)
    // Step 1 asks to find the item
    expect(screen.getByText('Select item & location')).toBeInTheDocument()
  })

  it('shows step indicators', () => {
    render(<MemoryRouter><CycleCountPage /></MemoryRouter>)
    // Should render step numbers
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('does not crash on initial render', () => {
    expect(() => render(<MemoryRouter><CycleCountPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('CycleCountPage — null handling', () => {
  it('does not crash when warehouse data is null', () => {
    vi.mocked(useItems).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useWarehouses).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useWarehouses>)
    vi.mocked(useBins).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBins>)
    vi.mocked(useCycleCountStart).mockReturnValue(NOOP as ReturnType<typeof useCycleCountStart>)
    vi.mocked(useCycleCountSubmit).mockReturnValue(NOOP as ReturnType<typeof useCycleCountSubmit>)
    vi.mocked(useCycleCountConfirm).mockReturnValue(NOOP as ReturnType<typeof useCycleCountConfirm>)
    expect(() => render(<MemoryRouter><CycleCountPage /></MemoryRouter>)).not.toThrow()
  })
})

// ── InventorySearchPage ───────────────────────────────────────────────────────

import { InventorySearchPage } from '../InventorySearchPage'

describe('InventorySearchPage — loading', () => {
  beforeEach(() => {
    vi.mocked(useItems).mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useItems>)
    vi.mocked(useItemLedger).mockReturnValue({ data: undefined, isLoading: false } as ReturnType<typeof useItemLedger>)
  })

  it('renders page title', () => {
    render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)
    expect(screen.getByText('Inventory Search')).toBeInTheDocument()
  })

  it('does not crash while loading', () => {
    expect(() => render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)).not.toThrow()
  })
})

describe('InventorySearchPage — empty results', () => {
  beforeEach(() => {
    vi.mocked(useItems).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useItemLedger).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItemLedger>)
  })

  it('shows empty-state message', () => {
    render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)
    expect(screen.getByText('No items found.')).toBeInTheDocument()
  })

  it('renders search input', () => {
    render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)
    expect(screen.getByPlaceholderText('SKU, item name…')).toBeInTheDocument()
  })
})

describe('InventorySearchPage — with items', () => {
  beforeEach(() => {
    vi.mocked(useItems).mockReturnValue({
      data: { count: 1, results: [MOCK_ITEM] },
      isLoading: false,
    } as ReturnType<typeof useItems>)
    vi.mocked(useItemLedger).mockReturnValue({ data: EMPTY_PAGED, isLoading: false } as ReturnType<typeof useItemLedger>)
  })

  it('renders item SKU in results table', () => {
    render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)
    expect(screen.getByText('SKU-001')).toBeInTheDocument()
  })

  it('renders item name in results table', () => {
    render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)
    expect(screen.getByText('Widget A')).toBeInTheDocument()
  })
})

describe('InventorySearchPage — null handling', () => {
  it('does not crash when data is null', () => {
    vi.mocked(useItems).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    vi.mocked(useItemLedger).mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItemLedger>)
    expect(() => render(<MemoryRouter><InventorySearchPage /></MemoryRouter>)).not.toThrow()
  })
})
