import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { InventoryDashboard } from '../InventoryDashboard'

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('@/hooks/useInventory', () => ({
  useItems:    vi.fn(),
  useBalances: vi.fn(),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

import { useItems, useBalances } from '@/hooks/useInventory'

const mockUseItems    = vi.mocked(useItems)
const mockUseBalances = vi.mocked(useBalances)

function renderPage() {
  return render(
    <MemoryRouter>
      <InventoryDashboard />
    </MemoryRouter>,
  )
}

// ── Loading state ─────────────────────────────────────────────────────────────

describe('InventoryDashboard — loading state', () => {
  beforeEach(() => {
    mockUseItems.mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useItems>)
    mockUseBalances.mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useBalances>)
  })

  it('renders page title', () => {
    renderPage()
    expect(screen.getByText('Inventory Dashboard')).toBeInTheDocument()
  })

  it('shows stat labels while loading', () => {
    renderPage()
    expect(screen.getByText('Total SKUs')).toBeInTheDocument()
    expect(screen.getByText('Low Stock Alerts')).toBeInTheDocument()
    // All numeric values fall back to 0 when data is undefined
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
  })

  it('does not crash when data is undefined', () => {
    expect(() => renderPage()).not.toThrow()
  })
})

// ── Empty data ────────────────────────────────────────────────────────────────

describe('InventoryDashboard — empty data', () => {
  beforeEach(() => {
    mockUseItems.mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useItems>)
    mockUseBalances.mockReturnValue({
      data: { count: 0, results: [] },
      isLoading: false,
    } as ReturnType<typeof useBalances>)
  })

  it('shows 0 SKUs when no items', () => {
    renderPage()
    expect(screen.getByText('Total SKUs')).toBeInTheDocument()
    // Multiple stat cards all show 0 — verify at least one is present
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(1)
  })

  it('does not render safety stock alert section when no alerts', () => {
    renderPage()
    expect(screen.queryByText(/Safety Stock Alerts/)).not.toBeInTheDocument()
  })

  it('renders the Recent Balances table with empty message', () => {
    renderPage()
    expect(screen.getByText('No stock balances yet. Use Receive Stock to add inventory.')).toBeInTheDocument()
  })
})

// ── Populated data ────────────────────────────────────────────────────────────

describe('InventoryDashboard — with data', () => {
  const mockBalance = {
    id: 1, item: 1, item_sku: 'SKU-001', item_name: 'Widget A',
    warehouse: 1, warehouse_code: 'WH-A', bin: null, bin_code: null,
    quantity_on_hand: '15', quantity_reserved: '0', avg_cost: '9.99',
    safety_stock_qty: '5', below_safety_stock: false, updated_at: '2026-01-01T00:00:00Z',
  }

  beforeEach(() => {
    mockUseItems.mockReturnValue({
      data: { count: 3, results: [] },
      isLoading: false,
    } as ReturnType<typeof useItems>)
    mockUseBalances.mockImplementation((params?: { below_safety?: boolean }) => {
      if (params?.below_safety) {
        return { data: { count: 0, results: [] }, isLoading: false } as ReturnType<typeof useBalances>
      }
      return {
        data: { count: 1, results: [mockBalance] },
        isLoading: false,
      } as ReturnType<typeof useBalances>
    })
  })

  it('shows correct total SKU count', () => {
    renderPage()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows item SKU in the balances table', () => {
    renderPage()
    expect(screen.getByText('SKU-001')).toBeInTheDocument()
  })

  it('shows item name in the balances table', () => {
    renderPage()
    expect(screen.getByText('Widget A')).toBeInTheDocument()
  })
})

// ── Safety stock alerts ───────────────────────────────────────────────────────

describe('InventoryDashboard — safety stock alerts', () => {
  const alertBalance = {
    id: 2, item: 2, item_sku: 'SKU-002', item_name: 'Low Stock Item',
    warehouse: 1, warehouse_code: 'WH-A', bin: null, bin_code: null,
    quantity_on_hand: '1', quantity_reserved: '0', avg_cost: '5.00',
    safety_stock_qty: '10', below_safety_stock: true, updated_at: '2026-01-01T00:00:00Z',
  }

  beforeEach(() => {
    mockUseItems.mockReturnValue({
      data: { count: 5, results: [] },
      isLoading: false,
    } as ReturnType<typeof useItems>)
    mockUseBalances.mockImplementation((params?: { below_safety?: boolean }) => {
      if (params?.below_safety) {
        return { data: { count: 1, results: [alertBalance] }, isLoading: false } as ReturnType<typeof useBalances>
      }
      return { data: { count: 1, results: [alertBalance] }, isLoading: false } as ReturnType<typeof useBalances>
    })
  })

  it('renders the Safety Stock Alerts section when count > 0', () => {
    renderPage()
    expect(screen.getByText(/Safety Stock Alerts \(1\)/)).toBeInTheDocument()
  })

  it('shows the alert item SKU in the alert table', () => {
    renderPage()
    expect(screen.getAllByText('SKU-002').length).toBeGreaterThan(0)
  })
})

// ── Error / undefined results ──────────────────────────────────────────────────

describe('InventoryDashboard — graceful error handling', () => {
  it('does not crash when results array is missing from response', () => {
    // Simulates a backend returning unexpected shape
    mockUseItems.mockReturnValue({
      data: { count: 0 } as never,
      isLoading: false,
    } as ReturnType<typeof useItems>)
    mockUseBalances.mockReturnValue({
      data: { count: 0 } as never,
      isLoading: false,
    } as ReturnType<typeof useBalances>)

    expect(() => renderPage()).not.toThrow()
  })

  it('does not crash when the entire data object is null', () => {
    mockUseItems.mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useItems>)
    mockUseBalances.mockReturnValue({ data: null as never, isLoading: false } as ReturnType<typeof useBalances>)

    expect(() => renderPage()).not.toThrow()
  })
})
