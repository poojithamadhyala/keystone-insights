import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { AgingRow, ExpirationRow, NoiRow, Occupancy } from './api'
import { DataTable, Legend, tooltip } from './components'
import { money, moneyCompact, monthLabel, pct } from './format'

// Recessive chrome: hairline grid, muted ticks, no axis lines.
const AXIS = { stroke: 'var(--color-muted)', fontSize: 11, tickLine: false, axisLine: false } as const
const GRID = <CartesianGrid stroke="var(--color-grid)" vertical={false} />
const CURSOR_LINE = { stroke: 'var(--color-axis)', strokeWidth: 1 }
const CURSOR_BAR = { fill: 'var(--color-grid)', opacity: 0.5 }
const S1 = 'var(--color-series-1)'
const S2 = 'var(--color-series-2)'
const S3 = 'var(--color-series-3)'

// ------------------------------------------------------------------ occupancy trend
export function OccupancyTrendChart({ data }: { data: Occupancy['trend'] }) {
  const vals = data.map((d) => d.occupancy ?? 1)
  // even 2-point steps from just below the minimum up to 100%
  const lo = Math.max(0, Math.floor((Math.min(...vals) * 100 - 1) / 2) * 2) / 100
  const ticks = Array.from({ length: Math.round((1 - lo) * 50) + 1 }, (_, i) => Math.round((lo + i * 0.02) * 100) / 100)
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m, true)} {...AXIS} />
        <YAxis domain={[lo, 1]} ticks={ticks} tickFormatter={(v: number) => pct(v, 0)} width={44} {...AXIS} />
        <Tooltip cursor={CURSOR_LINE} content={tooltip((v) => pct(v), monthLabel)} />
        <Line isAnimationActive={false} dataKey="occupancy" name="Occupancy" stroke={S1} strokeWidth={2} dot={false}
              activeDot={{ r: 4, stroke: 'var(--color-surface)', strokeWidth: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function OccupancyTrendTable({ data }: { data: Occupancy['trend'] }) {
  return (
    <DataTable rows={data} rowKey={(r) => r.month} columns={[
      { key: 'm', header: 'Month', render: (r) => monthLabel(r.month) },
      { key: 'o', header: 'Occupancy', align: 'right', render: (r) => pct(r.occupancy) },
    ]} />
  )
}

// ------------------------------------------------------------------ NOI by property
export function noiByProperty(rows: NoiRow[]) {
  const by = new Map<number, { property_id: number; property: string; revenue: number; noi: number }>()
  for (const r of rows) {
    const cur = by.get(r.property_id) ?? { property_id: r.property_id, property: r.property, revenue: 0, noi: 0 }
    cur.revenue += r.revenue
    cur.noi += r.noi
    by.set(r.property_id, cur)
  }
  return [...by.values()].sort((a, b) => b.noi - a.noi)
}

export function NoiByPropertyChart({ rows, onSelect }: {
  rows: ReturnType<typeof noiByProperty>; onSelect?: (propertyId: number) => void
}) {
  return (
    <ResponsiveContainer width="100%" height={rows.length * 26 + 30}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
                barCategoryGap={2}>
        <CartesianGrid stroke="var(--color-grid)" horizontal={false} />
        <XAxis type="number" tickFormatter={moneyCompact} {...AXIS} />
        <YAxis type="category" dataKey="property" width={128} {...AXIS} interval={0} />
        <Tooltip cursor={CURSOR_BAR} content={tooltip(money)} />
        <Bar isAnimationActive={false} dataKey="noi" name="NOI" fill={S1} radius={[0, 4, 4, 0]}
             cursor={onSelect ? 'pointer' : undefined}
             onClick={(d: { payload?: { property_id?: number } }) => {
               const id = d.payload?.property_id
               if (onSelect && id) onSelect(id)
             }} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ------------------------------------------------------------------ NOI over time
export function noiByMonth(rows: NoiRow[]) {
  const by = new Map<string, { month: string; revenue: number; expenses: number; noi: number }>()
  for (const r of rows) {
    const cur = by.get(r.month) ?? { month: r.month, revenue: 0, expenses: 0, noi: 0 }
    cur.revenue += r.revenue
    cur.expenses += r.operating_expenses + r.maintenance
    cur.noi += r.noi
    by.set(r.month, cur)
  }
  return [...by.values()].sort((a, b) => a.month.localeCompare(b.month))
}

export const NOI_SERIES = [
  { key: 'revenue', label: 'Collected rent', color: S1 },
  { key: 'expenses', label: 'Expenses', color: S2 },
  { key: 'noi', label: 'NOI', color: S3 },
] as const

export function NoiMonthlyChart({ rows }: { rows: ReturnType<typeof noiByMonth> }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m, true)} {...AXIS} />
        <YAxis tickFormatter={moneyCompact} width={56} {...AXIS} />
        <Tooltip cursor={CURSOR_LINE} content={tooltip(money, monthLabel)} />
        {NOI_SERIES.map((s) => (
          <Line isAnimationActive={false} key={s.key} dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2}
                dot={false} activeDot={{ r: 4, stroke: 'var(--color-surface)', strokeWidth: 2 }} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

// ------------------------------------------------------------------ delinquency aging
export const BUCKETS = ['0-30', '31-60', '61-90', '90+'] as const

export function agingByBucket(rows: AgingRow[]) {
  return BUCKETS.map((bucket) => {
    const cur = rows.find((r) => r.bucket === bucket && r.current_resident)
    const former = rows.find((r) => r.bucket === bucket && !r.current_resident)
    return {
      bucket,
      current: cur?.amount ?? 0, currentTenants: cur?.tenants ?? 0,
      former: former?.amount ?? 0, formerTenants: former?.tenants ?? 0,
    }
  })
}

export const AGING_LEGEND = [
  { label: 'Current residents', color: S1 },
  { label: 'Former residents', color: S2 },
]

export function AgingChart({ rows }: { rows: ReturnType<typeof agingByBucket> }) {
  return (
    <>
      <Legend items={AGING_LEGEND} />
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap="30%">
          {GRID}
          <XAxis dataKey="bucket" tickFormatter={(b: string) => `${b} days`} {...AXIS} />
          <YAxis tickFormatter={moneyCompact} width={56} {...AXIS} />
          <Tooltip cursor={CURSOR_BAR} content={tooltip(money, (b) => `${b} days past due`)} />
          {/* 2px surface stroke = the spacer between stacked segments */}
          <Bar isAnimationActive={false} dataKey="current" name="Current residents" stackId="a" fill={S1}
               stroke="var(--color-surface)" strokeWidth={2} />
          <Bar isAnimationActive={false} dataKey="former" name="Former residents" stackId="a" fill={S2}
               stroke="var(--color-surface)" strokeWidth={2} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </>
  )
}

export function AgingTable({ rows }: { rows: ReturnType<typeof agingByBucket> }) {
  return (
    <DataTable rows={rows} rowKey={(r) => r.bucket} columns={[
      { key: 'b', header: 'Days past due', render: (r) => r.bucket },
      { key: 'c', header: 'Current residents', align: 'right', render: (r) => `${money(r.current)} (${r.currentTenants})` },
      { key: 'f', header: 'Former residents', align: 'right', render: (r) => `${money(r.former)} (${r.formerTenants})` },
    ]} />
  )
}

// ------------------------------------------------------------------ lease expirations
export function expirationsByMonth(rows: ExpirationRow[]) {
  const by = new Map<string, { month: string; leases: number; monthly_rent: number }>()
  for (const r of rows) {
    const cur = by.get(r.month) ?? { month: r.month, leases: 0, monthly_rent: 0 }
    cur.leases += r.leases
    cur.monthly_rent += r.monthly_rent
    by.set(r.month, cur)
  }
  return [...by.values()].sort((a, b) => a.month.localeCompare(b.month))
}

export function ExpirationsChart({ rows }: { rows: ReturnType<typeof expirationsByMonth> }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap={2}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={(m: string) => monthLabel(m, true)} {...AXIS} />
        <YAxis allowDecimals={false} width={40} {...AXIS} />
        <Tooltip cursor={CURSOR_BAR} content={tooltip((v) => `${v} leases`, monthLabel)} />
        <Bar isAnimationActive={false} dataKey="leases" name="Expiring" fill={S1} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ExpirationsTable({ rows }: { rows: ReturnType<typeof expirationsByMonth> }) {
  return (
    <DataTable rows={rows} rowKey={(r) => r.month} columns={[
      { key: 'm', header: 'Month', render: (r) => monthLabel(r.month) },
      { key: 'l', header: 'Leases', align: 'right', render: (r) => r.leases },
      { key: 'r', header: 'Rent at stake / mo', align: 'right', render: (r) => money(r.monthly_rent) },
    ]} />
  )
}
