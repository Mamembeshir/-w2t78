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
  data = [],
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
      <div className="overflow-x-auto rounded-2xl border border-surface-700/80 -mx-0">
        <table className="w-full text-sm min-w-[480px]">
          <thead>
            <tr className="bg-surface-900 border-b border-surface-700/80">
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  className={`
                    px-3 sm:px-5 py-2.5 sm:py-3.5 text-left text-xs font-semibold uppercase tracking-wider
                    ${sortKey === String(col.key) ? 'text-primary-400' : 'text-text-disabled'}
                    ${col.sortable ? 'cursor-pointer select-none hover:text-text-muted transition-colors duration-150' : ''}
                    ${col.className ?? ''}
                  `.trim()}
                  onClick={() => col.sortable && handleSort(String(col.key))}
                >
                  <span className="inline-flex items-center gap-1.5">
                    {col.header}
                    <SortIcon col={col} />
                  </span>
                  {/* Amber accent line on active sort column */}
                  {sortKey === String(col.key) && (
                    <div className="mt-1.5 h-px w-full bg-primary-500/40 rounded-full" />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-700/50 bg-surface-900">
            {isLoading
              ? skeletonRows.map((_, i) => (
                  <tr key={i}>
                    {columns.map((col) => (
                      <td key={String(col.key)} className="px-3 sm:px-5 py-3 sm:py-4">
                        <div className="h-3.5 bg-surface-700/60 rounded-full animate-pulse" style={{ width: `${55 + (i * 17) % 35}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              : paginated.length === 0
                ? (
                  <tr>
                    <td colSpan={columns.length} className="px-3 sm:px-5 py-16 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-surface-700/60 flex items-center justify-center">
                          <svg className="w-5 h-5 text-text-disabled" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                          </svg>
                        </div>
                        <p className="text-text-disabled text-sm">{emptyMessage}</p>
                      </div>
                    </td>
                  </tr>
                )
                : paginated.map((row, i) => (
                  <tr
                    key={rowKey ? String(row[rowKey]) : i}
                    className={`transition-colors duration-100 ${onRowClick ? 'cursor-pointer hover:bg-primary-500/4' : 'hover:bg-surface-800/60'}`}
                    onClick={() => onRowClick?.(row)}
                  >
                    {columns.map((col) => (
                      <td key={String(col.key)} className={`px-3 sm:px-5 py-3 sm:py-4 text-text-secondary ${col.className ?? ''}`}>
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
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-1 pt-3.5">
          <p className="text-text-disabled text-xs tabular-nums text-center sm:text-left">
            Showing {((safePage - 1) * pageSize) + 1}–{Math.min(safePage * pageSize, sorted.length)} of {sorted.length}
          </p>
          <div className="flex items-center justify-center gap-1 flex-wrap">
            <button
              disabled={safePage <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-700/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              ← Prev
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
                  ? <span key={`e${i}`} className="px-1.5 text-text-disabled text-xs">···</span>
                  : (
                    <button
                      key={p}
                      onClick={() => setPage(p as number)}
                      className={`min-w-[2rem] px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        p === safePage
                          ? 'bg-primary-500/15 text-primary-400 ring-1 ring-primary-500/30'
                          : 'text-text-muted hover:text-text-primary hover:bg-surface-700/80'
                      }`}
                    >
                      {p}
                    </button>
                  )
              )}
            <button
              disabled={safePage >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:text-text-primary hover:bg-surface-700/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
