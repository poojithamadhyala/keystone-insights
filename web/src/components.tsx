import { useState, type ReactNode } from 'react'

export function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div role="group" aria-label={label} className="rounded-lg border border-border bg-surface px-4 py-3">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  )
}

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  align?: 'left' | 'right'
}

export function DataTable<T>({ rows, columns, rowKey }: {
  rows: T[]; columns: Column<T>[]; rowKey: (row: T) => string | number
}) {
  return (
    <div className="overflow-x-auto">
      <table className="tabular w-full text-sm">
        <thead>
          <tr className="border-b border-grid text-left text-ink-2">
            {columns.map((c) => (
              <th key={c.key} className={`px-2 py-1.5 font-medium ${c.align === 'right' ? 'text-right' : ''}`}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className="border-b border-grid last:border-0">
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-1.5 ${c.align === 'right' ? 'text-right' : ''}`}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Card with title, optional legend, and a chart <-> table toggle (accessibility: every value
 *  is reachable without hovering). Holds the previous render at reduced opacity while loading. */
export function ChartCard({ title, subtitle, legend, chart, table, loading, error }: {
  title: string; subtitle?: string; legend?: ReactNode; chart: ReactNode; table?: ReactNode
  loading?: boolean; error?: string
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <header className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="font-medium text-ink">{title}</h2>
          {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        </div>
        {table && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            className="rounded border border-border px-2 py-0.5 text-xs text-ink-2 hover:bg-grid"
            aria-pressed={showTable}
          >
            {showTable ? 'Chart' : 'Table'}
          </button>
        )}
      </header>
      {legend && !showTable && <div className="mb-2">{legend}</div>}
      {error ? (
        <p className="text-sm text-critical">Failed to load: {error}</p>
      ) : (
        <div className={`transition-opacity ${loading ? 'opacity-50' : ''}`}>
          {showTable ? table : chart}
        </div>
      )}
    </section>
  )
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex gap-4 text-xs text-ink-2">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  )
}

interface TipEntry { name?: string | number; value?: unknown; color?: string; dataKey?: unknown }

/** Recharts tooltip body: values lead (strong), series names follow; line keys, not boxes. */
export function tooltip(fmt: (v: number) => string, labelFmt: (l: string) => string = (l) => l) {
  return function Tip({ active, payload, label }: {
    active?: boolean; payload?: readonly TipEntry[]; label?: string | number
  }) {
    if (!active || !payload?.length) return null
    return (
      <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-sm">
        <div className="mb-1 text-muted">{labelFmt(String(label ?? ''))}</div>
        {payload.map((p) => (
          <div key={String(p.dataKey ?? p.name)} className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-3" style={{ background: p.color }} />
            <span className="tabular font-semibold text-ink">{fmt(Number(p.value))}</span>
            <span className="text-ink-2">{p.name}</span>
          </div>
        ))}
      </div>
    )
  }
}
