import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { API_BASE } from './api'
import { useApiInfo } from './ApiGate'
import { ChartCard, DataTable, StatTile } from './components'
import { money, moneyCompact } from './format'

interface Breach {
  work_order_id: number; property: string; unit: string | null; category: string
  priority: string; vendor: string | null; days_open: number
}
interface Facts {
  as_of: string; window_days: number
  delinquency: { current_residents_this_week: number; current_residents_last_week: number; change: number }
  expirations: { leases: number; monthly_rent: number }
  sla: { open_breaches: number; open_breaches_last_week: number; completed_late_last_7_days: number; oldest: Breach[] }
}
export interface DigestRun {
  id: number; created_at: string; as_of: string; trigger: string; facts: Facts; text: string
  narrative_ok: boolean; ungrounded: string[]; cost_usd: number | null
  sent_at: string | null; delivery_status: string | null
}
type RunSummary = Pick<DigestRun, 'id' | 'created_at' | 'trigger' | 'narrative_ok' | 'sent_at' | 'delivery_status'>

/** Render one line of Slack mrkdwn (*bold*, _italic_) as React nodes. Text only: no HTML. */
export function mrkdwn(line: string): ReactNode[] {
  return line.split(/(\*[^*\n]+\*|_[^_\n]+_)/g).filter(Boolean).map((part, i) => {
    if (part.length > 2 && part.startsWith('*') && part.endsWith('*')) return <strong key={i}>{part.slice(1, -1)}</strong>
    if (part.length > 2 && part.startsWith('_') && part.endsWith('_')) return <em key={i} className="text-muted">{part.slice(1, -1)}</em>
    return <span key={i}>{part}</span>
  })
}

async function call<T>(path: string, method = 'GET'): Promise<{ status: number; body: T | { detail: string } }> {
  const res = await fetch(`${API_BASE}${path}`, { method })
  return { status: res.status, body: (await res.json()) as T }
}

export function DigestPage() {
  const { send_enabled } = useApiInfo()
  const [run, setRun] = useState<DigestRun | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [state, setState] = useState<'loading' | 'empty' | 'ready' | 'error'>('loading')
  const [busy, setBusy] = useState<'build' | 'send' | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [latest, history] = await Promise.all([call<DigestRun>('/digest/latest'), call<RunSummary[]>('/digest/runs')])
      if (Array.isArray(history.body)) setRuns(history.body)
      if (latest.status === 404) { setState('empty'); return }
      if (latest.status !== 200) throw new Error((latest.body as { detail: string }).detail)
      setRun(latest.body as DigestRun)
      setState('ready')
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e))
      setState('error')
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial load from the API
    void refresh()
  }, [refresh])

  async function build() {
    setBusy('build'); setNotice(null)
    const r = await call<DigestRun>('/digest/build', 'POST')
    setBusy(null)
    if (r.status !== 200) { setNotice(`Build failed: ${(r.body as { detail: string }).detail}`); return }
    await refresh()
  }

  async function send() {
    if (!run) return
    setBusy('send'); setNotice(null)
    const r = await call<DigestRun>(`/digest/${run.id}/send`, 'POST')
    setBusy(null)
    if (r.status !== 200) { setNotice((r.body as { detail: string }).detail); return }
    const status = (r.body as DigestRun).delivery_status
    setNotice(status === 'sent' ? 'Sent to Slack.' : `Not sent: ${status}`)
    await refresh()
  }

  const f = run?.facts
  return (
    <div className="space-y-12">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="label text-brand">Every Monday, in Slack</p>
          <h1 className="mt-4 text-[clamp(36px,4vw,64px)] leading-[1.05] text-ink">Weekly summary</h1>
          <p className="text-sm text-muted">
            The short update the team gets in Slack every Monday. Every number comes from the database; the AI only writes the sentences, and a checker withholds them if any number doesn't match.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void build()} disabled={busy !== null}
                  className="link-line disabled:opacity-40">
            {busy === 'build' ? 'Building…' : 'Rebuild preview'}
          </button>
          <button type="button" onClick={() => void send()} disabled={busy !== null || !run || !send_enabled}
                  title={send_enabled ? undefined : 'Sending is disabled on the public demo (preview only)'}
                  className="btn">
            {busy === 'send' ? 'Sending…' : 'Send now'}
          </button>
        </div>
      </div>
      {!send_enabled && (
        <p className="text-sm text-muted">Public demo: Send now is turned off. The preview is exactly what the weekly Slack post would contain.</p>
      )}
      {notice && <p role="status" className="border-l border-brand pl-4 text-ink-2">{notice}</p>}

      {state === 'loading' && <p className="text-sm text-muted">Loading…</p>}
      {state === 'error' && <p className="text-sm text-critical">Couldn't load the digest. Is the API running?</p>}
      {state === 'empty' && (
        <p className="border-t border-line pt-6 text-ink-2">
          No digest has been built yet. Click <b>Rebuild preview</b> to build this week's.
        </p>
      )}

      {run && f && (
        <>
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-3">
            <StatTile label="Unpaid rent" term="Delinquency" value={moneyCompact(f.delinquency.current_residents_this_week)}
                      sub={`${f.delinquency.change <= 0 ? 'down' : 'up'} ${money(Math.abs(f.delinquency.change))} vs last week`} />
            <StatTile label={`Leases ending, next ${f.window_days} days`} term="Lease expirations" value={String(f.expirations.leases)}
                      sub={`${moneyCompact(f.expirations.monthly_rent)} of monthly rent`} />
            <StatTile label="Repairs overdue right now" term="SLA breaches" value={String(f.sla.open_breaches)}
                      sub={`${f.sla.open_breaches_last_week} last week`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-5">
            <section className="border border-line bg-surface p-6 md:p-8 lg:col-span-3" aria-label="Digest preview">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-2xl text-ink">Preview (exactly what Slack receives)</h2>
                {run.narrative_ok
                  ? <span className="label text-good">✓ Numbers verified</span>
                  : <span className="label text-critical">⚠ Facts-only fallback</span>}
              </div>
              <div className="space-y-3 text-base leading-relaxed text-ink-2">
                {run.text.split('\n').map((line, i) => <p key={i}>{mrkdwn(line)}</p>)}
              </div>
              {!run.narrative_ok && run.ungrounded.length > 0 && (
                <p className="mt-4 text-sm text-ink-2">
                  Operator note (not sent): the written summary used numbers not in the data: {run.ungrounded.join(', ')}.
                </p>
              )}
              <p className="mt-4 text-sm text-muted">
                Digest #{run.id} · built {new Date(run.created_at).toLocaleString()} ({run.trigger})
                {run.cost_usd != null && ` · cost $${run.cost_usd.toFixed(3)}`}
                {run.delivery_status && ` · ${run.delivery_status}`}
              </p>
            </section>
            <div className="min-w-0 lg:col-span-2">
              <ChartCard title="Oldest overdue repairs" subtitle="Still open past their deadline, as of the data date" chart={
                f.sla.oldest.length === 0 ? <p className="text-sm text-muted">No open breaches.</p> : (
                  <DataTable<Breach> rows={f.sla.oldest} rowKey={(b) => b.work_order_id} columns={[
                    { key: 'w', header: 'WO', render: (b) => `#${b.work_order_id}` },
                    { key: 'p', header: 'Where', render: (b) => `${b.property}${b.unit ? ` ${b.unit}` : ''}` },
                    { key: 'c', header: 'What', render: (b) => `${b.category} · ${b.priority}` },
                    { key: 'd', header: 'Days', align: 'right', render: (b) => b.days_open },
                  ]} />
                )} />
            </div>
          </div>
        </>
      )}

      {runs.length > 0 && (
        <ChartCard title="Recent runs" chart={
          <DataTable<RunSummary> rows={runs} rowKey={(r) => r.id} columns={[
            { key: 'i', header: '#', render: (r) => r.id },
            { key: 'c', header: 'Built', render: (r) => new Date(r.created_at).toLocaleString() },
            { key: 't', header: 'Trigger', render: (r) => r.trigger },
            { key: 'n', header: 'Summary', render: (r) => (r.narrative_ok ? 'verified' : 'facts-only') },
            { key: 's', header: 'Delivery', render: (r) => r.delivery_status ?? 'not sent' },
          ]} />
        } />
      )}
    </div>
  )
}
