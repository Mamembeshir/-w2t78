import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DataTable } from '@/components/ui/DataTable'
import type { Column } from '@/types'

interface Row extends Record<string, unknown> {
  id: string
  name: string
  qty: number
}

const COLUMNS: Column<Row>[] = [
  { key: 'name', header: 'Name', sortable: true },
  { key: 'qty',  header: 'Qty',  sortable: true },
]

const ROWS: Row[] = [
  { id: '1', name: 'Widget A', qty: 10 },
  { id: '2', name: 'Gadget B', qty: 3 },
  { id: '3', name: 'Part C',   qty: 7 },
]

// ── Rendering ─────────────────────────────────────────────────────────────────

describe('DataTable — rendering', () => {
  it('renders column headers', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Qty')).toBeInTheDocument()
  })

  it('renders all row values', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />)
    expect(screen.getByText('Widget A')).toBeInTheDocument()
    expect(screen.getByText('Gadget B')).toBeInTheDocument()
    expect(screen.getByText('Part C')).toBeInTheDocument()
  })

  it('renders custom cell via render prop', () => {
    const cols: Column<Row>[] = [
      { key: 'name', header: 'Name', sortable: false },
      { key: 'qty',  header: 'Qty',  sortable: false, render: (v) => <span data-testid="custom">{String(v)} units</span> },
    ]
    render(<DataTable columns={cols} data={ROWS} />)
    const cells = screen.getAllByTestId('custom')
    expect(cells).toHaveLength(3)
    expect(cells[0]).toHaveTextContent('10 units')
  })
})

// ── Empty and loading states ───────────────────────────────────────────────────

describe('DataTable — empty and loading states', () => {
  it('renders empty message when data is empty array', () => {
    render(<DataTable columns={COLUMNS} data={[]} emptyMessage="Nothing here." />)
    expect(screen.getByText('Nothing here.')).toBeInTheDocument()
  })

  it('renders default empty message when data is empty and no message prop', () => {
    render(<DataTable columns={COLUMNS} data={[]} />)
    expect(screen.getByText('No data found.')).toBeInTheDocument()
  })

  it('does NOT crash when data prop is undefined (uses default [])', () => {
    // This is the key regression test — pages sometimes pass undefined
    // @ts-expect-error intentionally passing undefined to test runtime safety
    expect(() => render(<DataTable columns={COLUMNS} data={undefined} />)).not.toThrow()
    expect(screen.getByText('No data found.')).toBeInTheDocument()
  })

  it('renders skeleton rows when isLoading is true', () => {
    const { container } = render(<DataTable columns={COLUMNS} data={[]} isLoading />)
    // Skeleton rows have animate-pulse divs inside cells
    const pulses = container.querySelectorAll('.animate-pulse')
    expect(pulses.length).toBeGreaterThan(0)
  })

  it('does not render data rows while loading', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} isLoading />)
    expect(screen.queryByText('Widget A')).not.toBeInTheDocument()
  })
})

// ── Sorting ───────────────────────────────────────────────────────────────────

describe('DataTable — sorting', () => {
  it('sorts ascending on first click', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />)
    fireEvent.click(screen.getByText('Name'))
    const cells = screen.getAllByRole('cell')
    // First data cell should be "Gadget B" (alphabetically first)
    expect(cells[0]).toHaveTextContent('Gadget B')
  })

  it('sorts descending on second click', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />)
    fireEvent.click(screen.getByText('Name'))
    fireEvent.click(screen.getByText('Name'))
    const cells = screen.getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('Widget A')
  })

  it('clears sort on third click', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} />)
    fireEvent.click(screen.getByText('Name'))
    fireEvent.click(screen.getByText('Name'))
    fireEvent.click(screen.getByText('Name'))
    const cells = screen.getAllByRole('cell')
    // Back to original order — first row is Widget A
    expect(cells[0]).toHaveTextContent('Widget A')
  })

  it('does not sort non-sortable columns', () => {
    const cols: Column<Row>[] = [{ key: 'name', header: 'Name', sortable: false }]
    render(<DataTable columns={cols} data={ROWS} />)
    fireEvent.click(screen.getByText('Name'))
    // Order should not change
    const cells = screen.getAllByRole('cell')
    expect(cells[0]).toHaveTextContent('Widget A')
  })
})

// ── Pagination ────────────────────────────────────────────────────────────────

describe('DataTable — pagination', () => {
  const manyRows: Row[] = Array.from({ length: 25 }, (_, i) => ({
    id: String(i + 1),
    name: `Item ${String(i + 1).padStart(2, '0')}`,
    qty: i,
  }))

  it('shows only pageSize rows on first page', () => {
    render(<DataTable columns={COLUMNS} data={manyRows} pageSize={10} />)
    expect(screen.getByText('Item 01')).toBeInTheDocument()
    expect(screen.queryByText('Item 11')).not.toBeInTheDocument()
  })

  it('shows Next button when data exceeds pageSize', () => {
    render(<DataTable columns={COLUMNS} data={manyRows} pageSize={10} />)
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
  })

  it('navigates to next page on Next click', () => {
    render(<DataTable columns={COLUMNS} data={manyRows} pageSize={10} />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Item 11')).toBeInTheDocument()
    expect(screen.queryByText('Item 01')).not.toBeInTheDocument()
  })

  it('disables Prev button on first page', () => {
    render(<DataTable columns={COLUMNS} data={manyRows} pageSize={10} />)
    expect(screen.getByRole('button', { name: /prev/i })).toBeDisabled()
  })

  it('hides pagination when all rows fit on one page', () => {
    render(<DataTable columns={COLUMNS} data={ROWS} pageSize={10} />)
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument()
  })
})

// ── Row click ─────────────────────────────────────────────────────────────────

describe('DataTable — row click', () => {
  it('calls onRowClick with the row data when clicked', () => {
    const onClick = vi.fn()
    render(<DataTable columns={COLUMNS} data={ROWS} onRowClick={onClick} rowKey="id" />)
    fireEvent.click(screen.getByText('Widget A'))
    expect(onClick).toHaveBeenCalledWith(ROWS[0])
  })
})
