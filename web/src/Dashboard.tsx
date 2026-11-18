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
import { CHART_NOTES } from './chartNotes'
import { judge, PLAIN, RULES } from './health'
import { ChartCard, DataTable, Legend, StatTile } from './components'
import { money, moneyCompact, monthLabel, pct } from './format'
import { filtersToParams, parseFilters, RANGE_PRESETS, rangeFor, type UrlFilters } from './scope'
import { useApi } from './useApi'

function FilterBar({ filters, properties, onChange, lockProperty }: {
  filters: UrlFilters; properties: Property[]; onChange: (f: UrlFilters) => void
  lockProperty?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-10 gap-y-4" role="group" aria-label="Filters">
      <div className="flex items-center gap-5" role="radiogroup" aria-label="Date range">
        {RANGE_PRESETS.map((m) => (
          <button key={m} type="button" role="radio" aria-checked={filters.months === m}
                  onClick={() => onChange({ ...filters, months: m })}
                  className={`label border-b py-1 transition-colors duration-300 ${filters.months === m
                    ? 'border-brand text-brand' : 'border-transparent text-ink-2 hover:text-brand'}`}>
            {m}m
          </button>
        ))}
      </div>
      {!lockProperty && (
        <details className="relative">
          <summary className="label flex cursor-pointer list-none items-center gap-3 border-b border-line py-1 text-ink hover:text-brand">
            {filters.propertyIds.length === 0
              ? 'All properties'
              : `${filters.propertyIds.length} propert${filters.propertyIds.length === 1 ? 'y' : 'ies'}`}
            <span aria-hidden className="text-muted">▾</span>
          </summary>
          <fieldset className="absolute right-0 z-10 mt-2 max-h-80 w-64 overflow-y-auto border border-line bg-page p-3">
            <legend className="sr-only">Properties</legend>
            <button type="button" className="mb-2 w-full py-1 text-left text-sm text-brand hover:underline"
                    onClick={() => onChange({ ...filters, propertyIds: [] })}>
              All properties
            </button>
            {properties.map((p) => (
              <label key={p.id} className="flex items-center gap-3 py-1 text-sm text-ink-2 hover:text-ink">
                <input type="checkbox" className="accent-brand" checked={filters.propertyIds.includes(p.id)}
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
  const rangeLabel = scope ? `${monthLabel(scope.start)} to ${monthLabel(scope.end)}` : ''

  // One-sentence screen-reader summaries of what each chart shows.
  const trend = (occ.data?.trend ?? []).filter((t) => t.occupancy != null)
  const occSummary = trend.length
    ? `from ${pct(trend[0].occupancy)} in ${monthLabel(trend[0].month)} to ${pct(trend[trend.length - 1].occupancy)} in ${monthLabel(trend[trend.length - 1].month)}`
    : undefined
  const bestMonth = [...noiMonths].sort((a, b) => b.noi - a.noi)[0]
  const noiSummary = bestMonth ? `total ${moneyCompact(noiTotal)}; highest month ${monthLabel(bestMonth.month)} at ${moneyCompact(bestMonth.noi)}` : undefined
  const biggestBucket = [...agingRows].sort((a, b) => b.current + b.former - (a.current + a.former))[0]
  const agingSummary = biggestBucket ? `current residents owe ${moneyCompact(delinquentCurrent)}; largest bucket ${biggestBucket.bucket} days` : undefined
  const peak = [...expRows].sort((a, b) => b.leases - a.leases)[0]
  const expSummary = peak ? `busiest month ${monthLabel(peak.month)} with ${peak.leases} leases` : undefined
  const noiPropSummary = noiProps.length
    ? `highest ${noiProps[0].property} at ${moneyCompact(noiProps[0].noi)}, lowest ${noiProps[noiProps.length - 1].property} at ${moneyCompact(noiProps[noiProps.length - 1].noi)}`
    : undefined

  const setFilters = (f: UrlFilters) => setParams(filtersToParams(f))
  const keep = filtersToParams({ ...filters, propertyIds: [] }).toString()

  if (meta.error) {
    return (
      <div role="alert" className="space-y-2 p-6">
        <p className="text-critical">Couldn't reach the API: {meta.error}</p>
        <button type="button" onClick={meta.reload} className="btn btn-sm">Retry</button>
      </div>
    )
  }

  return (
    <div className="space-y-12">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          {lockedId && (
            <Link to={`/dashboard?${keep}`} className="link-line text-brand">All buildings</Link>
          )}
          <h1 className="mt-4 text-[clamp(36px,4vw,64px)] leading-[1.05] text-ink">
            {lockedId ? property?.name ?? 'Building' : 'Portfolio dashboard'}
          </h1>
          <p className="mt-3 text-muted">
            {property ? `${property.city}, ${property.state} · ${property.units} apartments · ` : ''}
            As of {meta.data?.as_of ?? '…'} · {rangeLabel}
          </p>
        </div>
        <FilterBar filters={filters} properties={properties.data ?? []} onChange={setFilters}
                   lockProperty={!!lockedId} />
      </div>

      <div className="grid grid-cols-1 gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label={PLAIN.occupancy.label} term={PLAIN.occupancy.term} help={PLAIN.occupancy.help}
                  value={units ? pct(occupied / units) : 'n/a'}
                  sub={`${occupied.toLocaleString()} of ${units.toLocaleString()} apartments`}
                  status={judge(units ? occupied / units : null, RULES.occupancy)} statusRule={RULES.occupancy.explain} />
        <StatTile label={PLAIN.noi.label} term={PLAIN.noi.term} help={PLAIN.noi.help}
                  value={moneyCompact(noiTotal)} sub={rangeLabel} />
        <StatTile label={PLAIN.delinquent.label} term={PLAIN.delinquent.term} help={PLAIN.delinquent.help}
                  value={moneyCompact(delinquentCurrent)} sub="owed by current tenants" />
        <StatTile label={PLAIN.expiring.label} term={PLAIN.expiring.term} help={PLAIN.expiring.help}
                  value={String(next90)} sub="in the next 3 months" />
        <StatTile label={PLAIN.repairs.label} term={PLAIN.repairs.term} help={PLAIN.repairs.help}
                  value={slaJudged ? pct(slaMet / slaJudged) : 'n/a'}
                  sub={`${slaMet.toLocaleString()} of ${slaJudged.toLocaleString()} on time`}
                  status={judge(slaJudged ? slaMet / slaJudged : null, RULES.repairsOnTime)} statusRule={RULES.repairsOnTime.explain} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Apartments rented over time" subtitle="Share of apartments with a tenant on the 1st of each month"
                   loading={occ.loading} ready={!!occ.data} error={occ.error} onRetry={occ.reload}
                   about={CHART_NOTES.occupancy} summary={occSummary}
                   chart={<OccupancyTrendChart data={occ.data?.trend ?? []} />}
                   table={<OccupancyTrendTable data={occ.data?.trend ?? []} />} />
        <ChartCard title="Profit from operations (NOI)" subtitle="Rent collected minus running costs, by month (cash basis)"
                   loading={noi.loading} ready={!!noi.data} error={noi.error} onRetry={noi.reload}
                   empty={noi.data && noiMonths.length === 0 && 'No income or expenses in this range.'}
                   about={CHART_NOTES.noi} summary={noiSummary}
                   legend={<Legend items={NOI_SERIES.map((s) => ({ label: s.label, color: s.color }))} />}
                   chart={<NoiMonthlyChart rows={noiMonths} />}
                   table={<DataTable rows={noiMonths} rowKey={(r) => r.month} columns={[
                     { key: 'm', header: 'Month', render: (r) => monthLabel(r.month) },
                     { key: 'r', header: 'Collected', align: 'right', render: (r) => money(r.revenue) },
                     { key: 'e', header: 'Expenses', align: 'right', render: (r) => money(r.expenses) },
                     { key: 'n', header: 'NOI', align: 'right', render: (r) => money(r.noi) },
                   ]} />} />
        <ChartCard title="Unpaid rent, by how overdue" subtitle={`Current and former tenants, grouped by the month the rent was due · as of ${meta.data?.as_of ?? ''}`}
                   loading={aging.loading} ready={!!aging.data} error={aging.error} onRetry={aging.reload}
                   empty={aging.data && aging.data.length === 0 && 'No outstanding balances as of this date.'}
                   about={CHART_NOTES.aging} summary={agingSummary}
                   chart={<AgingChart rows={agingRows} />} table={<AgingTable rows={agingRows} />} />
        <ChartCard title="Leases ending in the next 12 months" subtitle="Active leases, by the month of their last day"
                   loading={exp.loading} ready={!!exp.data} error={exp.error} onRetry={exp.reload}
                   empty={exp.data && expRows.length === 0 && 'No active leases end in the next 12 months.'}
                   about={CHART_NOTES.expirations} summary={expSummary}
                   chart={<ExpirationsChart rows={expRows} />} table={<ExpirationsTable rows={expRows} />} />
        {!lockedId && (
          <ChartCard title="Profit by building" subtitle={`${rangeLabel} · click a bar to open that building`}
                     loading={noi.loading} ready={!!noi.data} error={noi.error} onRetry={noi.reload}
                     about={CHART_NOTES.noiByProperty} summary={noiPropSummary}
                     chart={<NoiByPropertyChart rows={noiProps}
                                                onSelect={(id) => navigate(`/properties/${id}?${keep}`)} />}
                     table={<DataTable rows={noiProps} rowKey={(r) => r.property_id} columns={[
                       { key: 'p', header: 'Property', render: (r) => r.property },
                       { key: 'n', header: 'NOI', align: 'right', render: (r) => money(r.noi) },
                     ]} />} />
        )}
        <ChartCard title="Repairs done on time, by urgency" subtitle="Deadlines: emergency 24 h, high 3 days, normal 7 days, low 14 days. Still-open repairs past their deadline count as late."
                   loading={sla.loading} ready={!!sla.data} error={sla.error} onRetry={sla.reload}
                   empty={sla.data && sla.data.length === 0 && 'No work orders opened in this range.'}
                   about={CHART_NOTES.sla}
                   chart={<SlaTable rows={sla.data ?? []} />} />
      </div>

      {lockedId ? (
        <PropertyExtras scope={scope} />
      ) : (
        <ChartCard title="Buildings" loading={occ.loading} ready={!!occ.data} error={occ.error}
                   onRetry={occ.reload}
                   empty={occ.data && occRows.length === 0 && 'No properties match the filter.'} chart={
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
      { key: 'm', header: 'Median hours', align: 'right', render: (r) => r.median_hours ?? 'n/a' },
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
    <div className="grid gap-6 lg:grid-cols-3">
      <ChartCard title="Work-order SLA by category" loading={byCat.loading} ready={!!byCat.data}
                 error={byCat.error} onRetry={byCat.reload} about={CHART_NOTES.sla}
                 empty={byCat.data && byCat.data.length === 0 && 'No work orders opened in this range.'}
                 chart={<SlaTable rows={byCat.data ?? []} />} />
      <div className="min-w-0 lg:col-span-2">
        <ChartCard title="Rent roll" subtitle={`As of ${roll.data?.as_of ?? ''} · ${total} units`}
                   loading={roll.loading} ready={!!roll.data} error={roll.error} onRetry={roll.reload}
                   chart={
          <>
            <DataTable rows={roll.data?.rows ?? []} rowKey={(r) => r.unit_id} columns={[
              { key: 'u', header: 'Unit', render: (r) => `${r.unit_number} · ${r.unit_type}` },
              { key: 't', header: 'Tenant', render: (r) => r.tenant ?? <span className="text-muted">Vacant</span> },
              { key: 'e', header: 'Lease ends', render: (r) => r.end_date ?? 'n/a' },
              { key: 'r', header: 'Rent', align: 'right', render: (r) => (r.monthly_rent ? money(r.monthly_rent) : 'n/a') },
              { key: 'm', header: 'Market', align: 'right', render: (r) => money(r.market_rent) },
              { key: 'b', header: 'Balance', align: 'right', render: (r) => (
                <span className={r.balance > 0 ? 'font-medium text-critical' : ''}>{money(r.balance)}</span>
              ) },
            ]} />
            <div className="mt-2 flex items-center justify-end gap-2 text-sm">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                      className="btn btn-sm">Prev</button>
              <span className="text-muted">{page + 1} / {Math.max(1, Math.ceil(total / PAGE))}</span>
              <button type="button" disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}
                      className="btn btn-sm">Next</button>
            </div>
          </>
        } />
      </div>
    </div>
  )
}
