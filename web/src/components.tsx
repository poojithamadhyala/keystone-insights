import { useState, type ReactNode } from 'react'
import { STATUS_LABEL, type Status } from './health'

const STATUS_STYLE: Record<Status, { icon: string; className: string }> = {
  good: { icon: '✓', className: 'text-status-good' },
  warn: { icon: '!', className: 'text-status-warn' },
  crit: { icon: '✕', className: 'text-status-crit' },
}

/** Status is never colour alone: an icon and a word go with it. A quiet uppercase label with a
 *  thin rule, not a pill. */
export function StatusBadge({ status, title }: { status: Status; title?: string }) {
  const s = STATUS_STYLE[status]
  return (
    <span title={title} className={`label inline-flex items-center gap-2 ${s.className}`}>
      <span aria-hidden className="font-sans">{s.icon}</span>
      {STATUS_LABEL[status]}
    </span>
  )
}

/** A headline number in the display serif, with a thin bronze rule above it. `term` keeps the
 *  industry word next to the plain label; `help` says what it means in everyday language;
 *  `status` is a rule-of-thumb verdict (see health.ts). */
export function StatTile({ label, value, sub, term, help, status, statusRule }: {
  label: string; value: string; sub?: string; term?: string; help?: string
  status?: Status | null; statusRule?: string
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-col border-t border-brand pt-4">
      <div className="min-h-10 text-sm text-ink-2">{/* two lines: values align across tiles */}
        {label}{term && <span className="text-muted"> ({term})</span>}
      </div>
      <div className="display mt-2 text-4xl text-ink">{value}</div>
      {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
      {status && <div className="mt-3"><StatusBadge status={status} title={statusRule} /></div>}
      {help && <p className="mt-3 text-sm leading-relaxed text-ink-2">{help}</p>}
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
          <tr className="border-b border-line text-left text-muted">
            {columns.map((c) => (
              <th key={c.key} className={`px-2 py-2 font-medium ${c.align === 'right' ? 'text-right' : ''}`}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className="border-b border-line last:border-0">
              {columns.map((c) => (
                <td key={c.key} className={`px-2 py-2 ${c.align === 'right' ? 'text-right' : ''}`}>
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
 *  is reachable without hovering). States:
 *  - first load: a fixed-height placeholder (no layout jump)
 *  - refetch: holds the previous render at reduced opacity
 *  - error: message + Retry
 *  - empty: the `empty` message instead of blank axes
 *  `about` explains why this chart type was chosen; `summary` is the screen-reader description
 *  of what the chart shows. */
export function ChartCard({
  title, subtitle, legend, chart, table, loading, ready, error, onRetry, empty, about, summary,
}: {
  title: string; subtitle?: string; legend?: ReactNode; chart: ReactNode; table?: ReactNode
  loading?: boolean; ready?: boolean; error?: string; onRetry?: () => void
  empty?: string | false; about?: string; summary?: string
}) {
  const [showTable, setShowTable] = useState(false)
  const [showAbout, setShowAbout] = useState(false)
  const firstLoad = ready === false && !error // no data has arrived yet
  let body: ReactNode
  if (error) {
    body = (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-critical">Couldn't load this: {error}</span>
        {onRetry && <button type="button" onClick={onRetry} className="btn btn-sm">Retry</button>}
      </div>
    )
  } else if (firstLoad) {
    body = <div className="flex h-40 items-center justify-center text-sm text-muted">Loading…</div>
  } else if (empty) {
    body = <p className="py-6 text-center text-sm text-muted">{empty}</p>
  } else {
    body = (
      <div className={`transition-opacity duration-300 ${loading ? 'opacity-50' : ''}`} aria-busy={loading}>
        {showTable ? table : (
          <div role="img" aria-label={summary ? `${title}: ${summary}` : title}>{chart}</div>
        )}
      </div>
    )
  }
  return (
    <section className="min-w-0 border border-line bg-surface p-6" aria-label={title}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-2xl leading-tight text-ink">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {about && (
            <button type="button" onClick={() => setShowAbout((v) => !v)} aria-expanded={showAbout}
                    aria-label={`Why this chart type: ${title}`} className="btn btn-sm">Why</button>
          )}
          {table && !error && !empty && (
            <button type="button" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}
                    className="btn btn-sm">
              {showTable ? 'Chart' : 'Table'}
            </button>
          )}
        </div>
      </header>
      {showAbout && about && <p className="mb-4 border-l border-brand pl-3 text-sm text-ink-2">{about}</p>}
      {legend && !showTable && !error && !empty && <div className="mb-3">{legend}</div>}
      {body}
    </section>
  )
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-4" style={{ background: i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  )
}

interface TipEntry { name?: string | number; value?: unknown; color?: string; dataKey?: unknown }

/** Recharts tooltip body: values lead, series names follow; line keys, not boxes. */
export function tooltip(fmt: (v: number) => string, labelFmt: (l: string) => string = (l) => l) {
  return function Tip({ active, payload, label }: {
    active?: boolean; payload?: readonly TipEntry[]; label?: string | number
  }) {
    if (!active || !payload?.length) return null
    return (
      <div className="border border-line bg-page px-3 py-2 text-sm">
        <div className="mb-1 text-muted">{labelFmt(String(label ?? ''))}</div>
        {payload.map((p) => (
          <div key={String(p.dataKey ?? p.name)} className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-3" style={{ background: p.color }} />
            <span className="tabular font-medium text-ink">{fmt(Number(p.value))}</span>
            <span className="text-ink-2">{p.name}</span>
          </div>
        ))}
      </div>
    )
  }
}
