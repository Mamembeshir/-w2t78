import { useState, useMemo } from 'react'
import type { Column } from '@/types'
import { ChevronDownIcon, ChevronUpDownIcon, ChevronUpIcon } from './icons'

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[]
  data: T[]
  isLoading?: boolean
  emptyMessage?: string
  pageSize?: number
  onRowClick?: (row: T) => void
  rowKey?: keyof T
  className?: string
}

type SortDir = 'asc' | 'desc' | null

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  isLoading = false,
  emptyMessage = 'No data found.',
  pageSize = 10,
  onRowClick,
  rowKey,
  className = '',
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)
  const [page, setPage] = useState(1)

  function handleSort(key: string) {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortKey(null); setSortDir(null) }
    setPage(1)
  }

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return data
    return [...data].sort((a, b) => {
      const av = a[sortKey] ?? ''
      const bv = b[sortKey] ?? ''
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const paginated = sorted.slice((safePage - 1) * pageSize, safePage * pageSize)

  function SortIcon({ col }: { col: Column<T> }) {
    if (!col.sortable) return null
    if (sortKey !== col.key) return <ChevronUpDownIcon className="w-3.5 h-3.5 text-text-muted" />
    if (sortDir === 'asc')  return <ChevronUpIcon className="w-3.5 h-3.5 text-primary-400" />
    return <ChevronDownIcon className="w-3.5 h-3.5 text-primary-400" />
  }

  const skeletonRows = Array.from({ length: Math.min(pageSize, 5) })

  return (
    <div className={`flex flex-col gap-0 ${className}`}>
      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-surface-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-700 bg-surface-800">
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  className={`
                    px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted
                    ${col.sortable ? 'cursor-pointer select-none hover:text-text-secondary' : ''}
                    ${col.className ?? ''}
                  `.trim()}
                  onClick={() => col.sortable && handleSort(String(col.key))}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    <SortIcon col={col} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-700 bg-surface-900">
            {isLoading
              ? skeletonRows.map((_, i) => (
                  <tr key={i}>
                    {columns.map((col) => (
                      <td key={String(col.key)} className="px-4 py-3.5">
                        <div className="h-4 bg-surface-700 rounded animate-pulse" style={{ width: `${60 + (i * 13) % 30}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              : paginated.length === 0
                ? (
                  <tr>
                    <td colSpan={columns.length} className="px-4 py-12 text-center text-text-muted">
                      {emptyMessage}
                    </td>
                  </tr>
                )
                : paginated.map((row, i) => (
                  <tr
                    key={rowKey ? String(row[rowKey]) : i}
                    className={`transition-colors duration-100 ${onRowClick ? 'cursor-pointer hover:bg-surface-800' : 'hover:bg-surface-800/50'}`}
                    onClick={() => onRowClick?.(row)}
                  >
                    {columns.map((col) => (
                      <td key={String(col.key)} className={`px-4 py-3.5 text-text-secondary ${col.className ?? ''}`}>
                        {col.render
                          ? col.render(row[col.key as keyof T], row)
                          : String(row[col.key as keyof T] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {!isLoading && sorted.length > pageSize && (
        <div className="flex items-center justify-between px-1 pt-3">
          <p className="text-text-muted text-xs">
            {sorted.length} total · page {safePage} of {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <button
              disabled={safePage <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-2.5 py-1.5 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-surface-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - safePage) <= 1)
              .reduce<(number | '…')[]>((acc, p, i, arr) => {
                if (i > 0 && (p as number) - (arr[i - 1] as number) > 1) acc.push('…')
                acc.push(p)
                return acc
              }, [])
              .map((p, i) =>
                p === '…'
                  ? <span key={`e${i}`} className="px-2 text-text-muted text-xs">…</span>
                  : (
                    <button
                      key={p}
                      onClick={() => setPage(p as number)}
                      className={`min-w-[2rem] px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                        p === safePage
                          ? 'bg-primary-500/20 text-primary-400 font-medium'
                          : 'text-text-secondary hover:text-text-primary hover:bg-surface-700'
                      }`}
                    >
                      {p}
                    </button>
                  )
              )}
            <button
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1.5 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-surface-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
