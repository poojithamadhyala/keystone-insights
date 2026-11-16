import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type {
  AgingRow, ExpirationRow, Meta, NoiRow, Occupancy, Property, RentRoll, Scope, SlaRow,
} from './api'
import { scopeQuery } from './api'
import {
  AgingChart, AgingTable, agingByBucket, ExpirationsChart, ExpirationsTable, expirationsByMonth,
  NOI_SERIES, NoiByPropertyChart, NoiMonthlyChart, noiByMonth, noiByProperty,
  OccupancyTrendChart, OccupancyTrendTable,
} from './charts'
import { ChartCard, DataTable, Legend, StatTile } from './components'
import { money, moneyCompact, monthLabel, pct } from './format'
import { filtersToParams, parseFilters, RANGE_PRESETS, rangeFor, type UrlFilters } from './scope'
import { useApi } from './useApi'

function FilterBar({ filters, properties, onChange, lockProperty }: {
  filters: UrlFilters; properties: Property[]; onChange: (f: UrlFilters) => void
  lockProperty?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-3" role="group" aria-label="Filters">
      <div className="inline-flex rounded-md border border-border bg-surface p-0.5" role="radiogroup"
           aria-label="Date range">
        {RANGE_PRESETS.map((m) => (
          <button key={m} type="button" role="radio" aria-checked={filters.months === m}
                  onClick={() => onChange({ ...filters, months: m })}
                  className={`rounded px-2.5 py-1 text-sm ${filters.months === m
                    ? 'bg-ink text-surface' : 'text-ink-2 hover:bg-grid'}`}>
            {m}m
          </button>
        ))}
      </div>
      {!lockProperty && (
        <details className="relative">
          <summary className="flex h-8 cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-ink">
            {filters.propertyIds.length === 0
              ? 'All properties'
              : `${filters.propertyIds.length} propert${filters.propertyIds.length === 1 ? 'y' : 'ies'}`}
            <span aria-hidden className="text-muted">▾</span>
          </summary>
          <fieldset className="absolute right-0 z-10 mt-1 max-h-80 w-60 overflow-y-auto rounded-md border border-border bg-surface p-2 shadow-md">
            <legend className="sr-only">Properties</legend>
            <button type="button" className="mb-1 w-full rounded px-2 py-1 text-left text-sm text-ink-2 hover:bg-grid"
                    onClick={() => onChange({ ...filters, propertyIds: [] })}>
              All properties
            </button>
            {properties.map((p) => (
              <label key={p.id} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-grid">
                <input type="checkbox" checked={filters.propertyIds.includes(p.id)}
                       onChange={(e) => onChange({
                         ...filters,
                         propertyIds: e.target.checked
                           ? [...filters.propertyIds, p.id].sort((a, b) => a - b)
                           : filters.propertyIds.filter((id) => id !== p.id),
                       })} />
                {p.name}
              </label>
            ))}
          </fieldset>
        </details>
      )}
    </div>
  )
}

export function Dashboard() {
  const { propertyId } = useParams()
  const lockedId = propertyId ? Number(propertyId) : undefined
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const filters = parseFilters(params)

  const meta = useApi<Meta>('/kpis/meta')
  const properties = useApi<Property[]>('/kpis/properties')

  // No memo needed: useApi keys on the query *string*, so a new scope object never refetches.
  const scope: Scope | null = meta.data
    ? { propertyIds: lockedId ? [lockedId] : filters.propertyIds, ...rangeFor(meta.data.as_of, filters.months) }
    : null

  const q = (path: string, extra?: Record<string, string | number>) =>
    scope ? `${path}?${scopeQuery(scope, extra)}` : null
  const occ = useApi<Occupancy>(q('/kpis/occupancy'))
  const noi = useApi<NoiRow[]>(q('/kpis/noi'))
  const aging = useApi<AgingRow[]>(q('/kpis/delinquency'))
  const exp = useApi<ExpirationRow[]>(q('/kpis/lease-expirations', { months: 12 }))
  const sla = useApi<SlaRow[]>(q('/kpis/work-order-sla', { group_by: 'priority' }))

  const property = properties.data?.find((p) => p.id === lockedId)
  const occRows = occ.data?.by_property ?? []
  const units = occRows.reduce((s, r) => s + r.units, 0)
  const occupied = occRows.reduce((s, r) => s + r.occupied, 0)
  const noiTotal = (noi.data ?? []).reduce((s, r) => s + r.noi, 0)
  const agingRows = agingByBucket(aging.data ?? [])
  const delinquentCurrent = agingRows.reduce((s, r) => s + r.current, 0)
  const expRows = expirationsByMonth(exp.data ?? [])
  const next90 = expRows.slice(0, 3).reduce((s, r) => s + r.leases, 0)
  const slaMet = (sla.data ?? []).reduce((s, r) => s + r.met, 0)
  const slaJudged = (sla.data ?? []).reduce((s, r) => s + r.judged, 0)
  const noiProps = noiByProperty(noi.data ?? [])
  const noiMonths = noiByMonth(noi.data ?? [])
  const rangeLabel = scope ? `${monthLabel(scope.start)} – ${monthLabel(scope.end)}` : ''

  const setFilters = (f: UrlFilters) => setParams(filtersToParams(f))
  const keep = filtersToParams({ ...filters, propertyIds: [] }).toString()

  if (meta.error) {
    return <p className="p-6 text-critical">API unavailable: {meta.error}. Is `make up` running?</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          {lockedId && (
            <Link to={`/?${keep}`} className="text-sm text-ink-2 underline">← Portfolio</Link>
          )}
          <h1 className="text-xl font-semibold">
            {lockedId ? property?.name ?? 'Property' : 'Portfolio overview'}
          </h1>
          <p className="text-sm text-muted">
            {property ? `${property.city}, ${property.state} · ${property.units} units · ` : ''}
            As of {meta.data?.as_of ?? '…'} · {rangeLabel}
          </p>
        </div>
        <FilterBar filters={filters} properties={properties.data ?? []} onChange={setFilters}
                   lockProperty={!!lockedId} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Occupancy" value={units ? pct(occupied / units) : '—'}
                  sub={`${occupied.toLocaleString()} of ${units.toLocaleString()} units`} />
        <StatTile label="NOI" value={moneyCompact(noiTotal)} sub={rangeLabel} />
        <StatTile label="Delinquent (current residents)" value={moneyCompact(delinquentCurrent)}
                  sub="all aging buckets" />
        <StatTile label="Leases expiring" value={String(next90)} sub="next 3 months" />
        <StatTile label="Work-order SLA" value={slaJudged ? pct(slaMet / slaJudged) : '—'}
                  sub={`${slaMet.toLocaleString()} of ${slaJudged.toLocaleString()} on time`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Occupancy" subtitle="Share of units leased on the 1st of each month"
                   loading={occ.loading} error={occ.error}
                   chart={<OccupancyTrendChart data={occ.data?.trend ?? []} />}
                   table={<OccupancyTrendTable data={occ.data?.trend ?? []} />} />
        <ChartCard title="Net operating income" subtitle="Cash basis, by month"
                   loading={noi.loading} error={noi.error}
                   legend={<Legend items={NOI_SERIES.map((s) => ({ label: s.label, color: s.color }))} />}
                   chart={<NoiMonthlyChart rows={noiMonths} />}
                   table={<DataTable rows={noiMonths} rowKey={(r) => r.month} columns={[
                     { key: 'm', header: 'Month', render: (r) => monthLabel(r.month) },
                     { key: 'r', header: 'Collected', align: 'right', render: (r) => money(r.revenue) },
                     { key: 'e', header: 'Expenses', align: 'right', render: (r) => money(r.expenses) },
                     { key: 'n', header: 'NOI', align: 'right', render: (r) => money(r.noi) },
                   ]} />} />
        <ChartCard title="Delinquency aging" subtitle={`Outstanding balance by charge month, as of ${meta.data?.as_of ?? ''}`}
                   loading={aging.loading} error={aging.error}
                   chart={<AgingChart rows={agingRows} />} table={<AgingTable rows={agingRows} />} />
        <ChartCard title="Lease expirations" subtitle="Active leases by month of last day, next 12 months"
                   loading={exp.loading} error={exp.error}
                   chart={<ExpirationsChart rows={expRows} />} table={<ExpirationsTable rows={expRows} />} />
        {!lockedId && (
          <ChartCard title="NOI by property" subtitle={`${rangeLabel} · click a bar to drill down`}
                     loading={noi.loading} error={noi.error}
                     chart={<NoiByPropertyChart rows={noiProps}
                                                onSelect={(id) => navigate(`/properties/${id}?${keep}`)} />}
                     table={<DataTable rows={noiProps} rowKey={(r) => r.property_id} columns={[
                       { key: 'p', header: 'Property', render: (r) => r.property },
                       { key: 'n', header: 'NOI', align: 'right', render: (r) => money(r.noi) },
                     ]} />} />
        )}
        <ChartCard title="Work-order SLA by priority" subtitle="Completed within target; open tickets past target count as misses"
                   loading={sla.loading} error={sla.error}
                   chart={<SlaTable rows={sla.data ?? []} />} />
      </div>

      {lockedId ? (
        <PropertyExtras scope={scope} />
      ) : (
        <ChartCard title="Properties" loading={occ.loading} error={occ.error} chart={
          <DataTable rows={occRows} rowKey={(r) => r.property_id} columns={[
            { key: 'p', header: 'Property', render: (r) => (
              <Link className="underline" to={`/properties/${r.property_id}?${keep}`}>{r.property}</Link>
            ) },
            { key: 'u', header: 'Units', align: 'right', render: (r) => r.units },
            { key: 'o', header: 'Occupancy', align: 'right', render: (r) => pct(r.occupancy) },
            { key: 'n', header: 'NOI', align: 'right', render: (r) =>
              money(noiProps.find((x) => x.property_id === r.property_id)?.noi ?? 0) },
          ]} />
        } />
      )}
    </div>
  )
}

const SLA_TARGET: Record<string, string> = { emergency: '24h', high: '72h', normal: '7d', low: '14d' }

const SEVERITY = Object.keys(SLA_TARGET)

function SlaTable({ rows }: { rows: SlaRow[] }) {
  // priorities in severity order; other groupings (category) stay alphabetical
  const sorted = [...rows].sort((a, b) =>
    SEVERITY.includes(a.grp) && SEVERITY.includes(b.grp)
      ? SEVERITY.indexOf(a.grp) - SEVERITY.indexOf(b.grp)
      : a.grp.localeCompare(b.grp))
  return (
    <DataTable rows={sorted} rowKey={(r) => r.grp} columns={[
      { key: 'g', header: 'Group', render: (r) => r.grp + (SLA_TARGET[r.grp] ? ` (${SLA_TARGET[r.grp]})` : '') },
      { key: 't', header: 'Tickets', align: 'right', render: (r) => r.tickets.toLocaleString() },
      { key: 's', header: 'On time', align: 'right', render: (r) => pct(r.sla_rate) },
      { key: 'm', header: 'Median hours', align: 'right', render: (r) => r.median_hours ?? '—' },
    ]} />
  )
}

const PAGE = 25

function PropertyExtras({ scope }: { scope: Scope | null }) {
  const [page, setPage] = useState(0)
  const roll = useApi<RentRoll>(
    scope ? `/kpis/rent-roll?${scopeQuery(scope, { limit: PAGE, offset: page * PAGE })}` : null,
  )
  const byCat = useApi<SlaRow[]>(scope ? `/kpis/work-order-sla?${scopeQuery(scope, { group_by: 'category' })}` : null)
  const total = roll.data?.total ?? 0
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <ChartCard title="Work-order SLA by category" loading={byCat.loading} error={byCat.error}
                 chart={<SlaTable rows={byCat.data ?? []} />} />
      <div className="lg:col-span-2">
        <ChartCard title="Rent roll" subtitle={`As of ${roll.data?.as_of ?? ''} · ${total} units`}
                   loading={roll.loading} error={roll.error} chart={
          <>
            <DataTable rows={roll.data?.rows ?? []} rowKey={(r) => r.unit_id} columns={[
              { key: 'u', header: 'Unit', render: (r) => `${r.unit_number} · ${r.unit_type}` },
              { key: 't', header: 'Tenant', render: (r) => r.tenant ?? <span className="text-muted">Vacant</span> },
              { key: 'e', header: 'Lease ends', render: (r) => r.end_date ?? '—' },
              { key: 'r', header: 'Rent', align: 'right', render: (r) => (r.monthly_rent ? money(r.monthly_rent) : '—') },
              { key: 'm', header: 'Market', align: 'right', render: (r) => money(r.market_rent) },
              { key: 'b', header: 'Balance', align: 'right', render: (r) => (
                <span className={r.balance > 0 ? 'font-semibold text-critical' : ''}>{money(r.balance)}</span>
              ) },
            ]} />
            <div className="mt-2 flex items-center justify-end gap-2 text-sm">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                      className="rounded border border-border px-2 py-0.5 disabled:opacity-40">Prev</button>
              <span className="text-muted">{page + 1} / {Math.max(1, Math.ceil(total / PAGE))}</span>
              <button type="button" disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}
                      className="rounded border border-border px-2 py-0.5 disabled:opacity-40">Next</button>
            </div>
          </>
        } />
      </div>
    </div>
  )
}
