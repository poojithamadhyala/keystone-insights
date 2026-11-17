import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts'
import type { AgingRow, ExpirationRow, Meta, Occupancy, Scope, SlaRow } from './api'
import { scopeQuery } from './api'
import { agingByBucket, expirationsByMonth } from './charts'
import { useChat } from './chat'
import { StatusBadge } from './components'
import { money, moneyCompact, monthLabel, pct } from './format'
import { judge, PLAIN, RULES } from './health'
import { rangeFor } from './scope'
import { useApi } from './useApi'

interface DigestFacts {
  as_of: string
  delinquency: { change: number }
  sla: { open_breaches: number }
}

const REPO = 'https://github.com/poojithamadhyala/keystone-insights'

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={1.8}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
  )
}
const ICONS = {
  chart: 'M4 19V5M4 19h16M8 15v-4M12 15V8M16 15v-6',
  chat: 'M5 5h14v10H9l-4 4V5z',
  mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
  check: 'M5 12.5l4.5 4.5L19 7',
}

function HealthCard({ title, term, value, detail, help, status, rule, loading }: {
  title: string; term: string; value: string; detail?: ReactNode; help: string
  status?: ReturnType<typeof judge>; rule?: string; loading: boolean
}) {
  return (
    <div role="group" aria-label={title}
         className="flex flex-col rounded-xl border border-border bg-surface p-4 shadow-sm">
      <h3 className="text-sm text-ink-2">{title} <span className="text-muted">({term})</span></h3>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className={`text-3xl font-semibold tabular ${loading ? 'text-muted' : 'text-ink'}`}>{loading ? '…' : value}</p>
        {status && !loading && <span className="whitespace-nowrap"><StatusBadge status={status} title={rule} /></span>}
      </div>
      {detail && <p className="mt-0.5 text-sm text-ink-2">{detail}</p>}
      <p className="mt-3 border-t border-border pt-2 text-xs leading-snug text-ink-2">{help}</p>
    </div>
  )
}

/** Live mini-chart for the hero: apartments rented over the last 12 months (same data as the
 *  dashboard's occupancy chart), so the first thing a visitor sees is real and moving. */
function TrendCard({ trend }: { trend: Occupancy['trend'] }) {
  const pts = trend.filter((t) => t.occupancy != null)
  const first = pts[0]
  const last = pts[pts.length - 1]
  return (
    <div className="hidden rounded-xl border border-border bg-surface p-4 shadow-sm md:block">
      <p className="text-sm text-ink-2">Apartments rented, last 12 months</p>
      <p className="mt-1 text-3xl font-semibold tabular text-ink">{last ? pct(last.occupancy) : '…'}</p>
      <div role="img" className="mt-2 h-24"
           aria-label={first && last ? `Apartments rented went from ${pct(first.occupancy)} in ${monthLabel(first.month)} to ${pct(last.occupancy)} in ${monthLabel(last.month)}` : 'Loading trend'}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={pts} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
            <YAxis hide domain={['dataMin - 0.005', 'dataMax + 0.005']} />
            <Line dataKey="occupancy" stroke="var(--color-brand)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-xs text-ink-2">
        {first && last ? `${monthLabel(first.month, true)} → ${monthLabel(last.month, true)} · live from the demo database` : ' '}
      </p>
    </div>
  )
}

export function Home() {
  const { openChat } = useChat()
  const [showRules, setShowRules] = useState(false)
  const meta = useApi<Meta>('/kpis/meta')
  // Same 12-month window and endpoints as the dashboard, so the two pages always agree.
  const scope: Scope | null = meta.data ? { propertyIds: [], ...rangeFor(meta.data.as_of, 12) } : null
  const q = (path: string, extra?: Record<string, string | number>) => (scope ? `${path}?${scopeQuery(scope, extra)}` : null)
  const occ = useApi<Occupancy>(q('/kpis/occupancy'))
  const aging = useApi<AgingRow[]>(q('/kpis/delinquency'))
  const exp = useApi<ExpirationRow[]>(q('/kpis/lease-expirations', { months: 12 }))
  const sla = useApi<SlaRow[]>(q('/kpis/work-order-sla', { group_by: 'priority' }))
  const digest = useApi<{ facts: DigestFacts }>('/digest/latest') // optional: weekly change

  const rows = occ.data?.by_property ?? []
  const units = rows.reduce((s, r) => s + r.units, 0)
  const occupied = rows.reduce((s, r) => s + r.occupied, 0)
  const occRate = units ? occupied / units : null
  const owed = agingByBucket(aging.data ?? []).reduce((s, r) => s + r.current, 0)
  const next3 = expirationsByMonth(exp.data ?? []).slice(0, 3)
  const ending = next3.reduce((s, r) => s + r.leases, 0)
  const atStake = next3.reduce((s, r) => s + r.monthly_rent, 0)
  const met = (sla.data ?? []).reduce((s, r) => s + r.met, 0)
  const judged = (sla.data ?? []).reduce((s, r) => s + r.judged, 0)
  const onTime = judged ? met / judged : null
  const facts = digest.data?.facts.as_of === meta.data?.as_of ? digest.data?.facts : undefined

  if (meta.error) {
    return (
      <div role="alert" className="space-y-2 p-6">
        <p className="text-critical">Couldn't reach the API: {meta.error}</p>
        <button type="button" onClick={meta.reload} className="rounded border border-border px-3 py-1 text-sm">Retry</button>
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <section className="grid items-center gap-8 rounded-2xl bg-hero px-6 py-10 sm:px-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div>
        <p className="text-sm font-medium text-brand">Property-management reporting, with an AI analyst</p>
        <h1 className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Your apartment portfolio, explained.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-ink-2">
          LeaseLens turns a property company's everyday data into plain answers: how full the
          buildings are, who is behind on rent, which leases end soon and whether repairs happen on
          time. You can ask it questions in plain English, and every answer shows where its numbers
          came from.
        </p>
        <p className="mt-3 text-sm text-ink-2">
          {rows.length || 20} buildings · {units ? units.toLocaleString() : '3,000'} apartments ·
          data as of {meta.data?.as_of ?? '…'} · <strong className="font-medium">all data is made up for this demo</strong>
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/dashboard" className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg shadow-sm hover:opacity-90">
            Open the dashboard
          </Link>
          <button type="button" onClick={openChat}
                  className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-grid">
            Ask a question
          </button>
        </div>
        </div>
        <TrendCard trend={occ.data?.trend ?? []} />
      </section>

      <section aria-labelledby="health-h">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="health-h" className="text-xl font-semibold">How is the portfolio doing?</h2>
            <p className="text-sm text-ink-2">The four numbers a property manager checks first, as of {meta.data?.as_of ?? '…'}.</p>
          </div>
          <button type="button" onClick={() => setShowRules((v) => !v)} aria-expanded={showRules}
                  className="text-sm text-brand underline underline-offset-2">
            How we judge "healthy"
          </button>
        </div>
        {showRules && (
          <ul className="mt-3 space-y-1 rounded-lg border border-border bg-surface p-3 text-sm text-ink-2">
            <li><b>Apartments rented:</b> {RULES.occupancy.explain}</li>
            <li><b>Repairs done on time:</b> {RULES.repairsOnTime.explain}</li>
            <li>Unpaid rent and leases ending soon show their size and trend instead of a verdict, because a fair threshold depends on the size of the portfolio.</li>
          </ul>
        )}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HealthCard title={PLAIN.occupancy.label} term={PLAIN.occupancy.term} loading={!occ.data}
                      value={pct(occRate)} help={PLAIN.occupancy.help}
                      detail={`${occupied.toLocaleString()} of ${units.toLocaleString()} apartments`}
                      status={judge(occRate, RULES.occupancy)} rule={RULES.occupancy.explain} />
          <HealthCard title={PLAIN.delinquent.label} term={PLAIN.delinquent.term} loading={!aging.data}
                      value={moneyCompact(owed)} help={PLAIN.delinquent.help}
                      detail={facts ? `${facts.delinquency.change <= 0 ? '↓ down' : '↑ up'} ${money(Math.abs(facts.delinquency.change))} from last week` : 'owed by current tenants'} />
          <HealthCard title={PLAIN.expiring.label} term={PLAIN.expiring.term} loading={!exp.data}
                      value={ending.toLocaleString()} help={PLAIN.expiring.help}
                      detail={`${moneyCompact(atStake)} of monthly rent up for renewal`} />
          <HealthCard title={PLAIN.repairs.label} term={PLAIN.repairs.term} loading={!sla.data}
                      value={pct(onTime)} help={PLAIN.repairs.help}
                      detail={facts ? `${facts.sla.open_breaches} repairs overdue right now` : `${met.toLocaleString()} of ${judged.toLocaleString()} on time`}
                      status={judge(onTime, RULES.repairsOnTime)} rule={RULES.repairsOnTime.explain} />
        </div>
      </section>

      <section aria-labelledby="do-h">
        <h2 id="do-h" className="text-xl font-semibold">What you can do here</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Link to="/dashboard" className="group rounded-xl border border-border bg-surface p-5 shadow-sm hover:border-brand">
            <span className="block text-brand"><Icon d={ICONS.chart} /></span>
            <span className="mt-3 block font-semibold text-ink group-hover:text-brand">See the numbers →</span>
            <span className="mt-1 block text-sm text-ink-2">Charts for the whole portfolio or one building: rent, profit, unpaid rent, leases and repairs. Every chart can be shown as a table.</span>
          </Link>
          <button type="button" onClick={openChat}
                  className="group rounded-xl border border-border bg-surface p-5 text-left shadow-sm hover:border-brand">
            <span className="block text-brand"><Icon d={ICONS.chat} /></span>
            <span className="mt-3 block font-semibold text-ink group-hover:text-brand">Ask a question →</span>
            <span className="mt-1 block text-sm text-ink-2">Type a question like "Which buildings have the most unpaid rent?" The AI looks it up and shows its sources.</span>
          </button>
          <Link to="/digest" className="group rounded-xl border border-border bg-surface p-5 shadow-sm hover:border-brand">
            <span className="block text-brand"><Icon d={ICONS.mail} /></span>
            <span className="mt-3 block font-semibold text-ink group-hover:text-brand">Read the weekly summary →</span>
            <span className="mt-1 block text-sm text-ink-2">The short Monday update the team gets in Slack: what changed this week and what needs attention.</span>
          </Link>
        </div>
      </section>

      <section aria-labelledby="honest-h" className="rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <h2 id="honest-h" className="text-xl font-semibold">How the AI is kept honest</h2>
        <ul className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            ['Every number shows its source', 'Answers link each figure to the exact data or document it came from, and you can open the database query behind it.'],
            ['It can only read, never change', 'The AI has read-only access to a limited set of data, enforced by the database itself, and it never sees tenants’ contact details.'],
            ['Numbers are checked before sending', 'Before the weekly summary goes out, a program compares every number the AI wrote with the real data. One mismatch and the AI’s text is withheld.'],
          ].map(([title, body]) => (
            <li key={title} className="flex gap-3">
              <span className="mt-0.5 shrink-0 text-status-good"><Icon d={ICONS.check} /></span>
              <span><span className="block font-medium text-ink">{title}</span><span className="text-sm text-ink-2">{body}</span></span>
            </li>
          ))}
        </ul>
      </section>

      <footer className="border-t border-border pt-4 text-sm text-ink-2">
        A portfolio project · synthetic data, no real people or companies ·{' '}
        <a href={REPO} className="text-brand underline underline-offset-2">source on GitHub</a>
      </footer>
    </div>
  )
}
