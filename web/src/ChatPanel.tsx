import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { splitCitations, streamChat, type AgentEvent, type Passage, type Report, type SqlResult } from './agent'
import { DataTable, Legend, tooltip } from './components'
import { useApi } from './useApi'

interface Step { name: string; label: string }
interface UserMsg { role: 'user'; text: string }
export interface AssistantMsg {
  role: 'assistant'; text: string; steps: Step[]; sql: SqlResult[]; passages: Passage[]
  reports: Report[]; status: 'streaming' | 'done' | 'error'; error?: string; cost?: number
  notice?: string
}
type Msg = UserMsg | AssistantMsg

const SERIES = ['var(--color-series-1)', 'var(--color-series-2)', 'var(--color-series-3)']
const AXIS = { stroke: 'var(--color-muted)', fontSize: 11, tickLine: false, axisLine: false } as const
/** Captions already show "Source: S1", so inline [S1] markers are dropped there. */
export const stripCites = (s: string) => s.replace(/\s*\[[SD]\d+\]/g, "")
const num = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : String(v))

function stepLabel(name: string, input: Record<string, unknown>): string {
  if (name === 'query_kpis') return `Queried data: ${String(input.purpose ?? '')}`
  if (name === 'search_documents') return `Searched documents: "${String(input.query ?? '')}"`
  if (name === 'generate_report') return `Built chart: ${String(input.title ?? '')}`
  return name
}

/** Apply one stream event to the in-progress assistant message (pure, so it's unit-testable). */
export function reduce(msg: AssistantMsg, e: AgentEvent): AssistantMsg {
  switch (e.type) {
    case 'text': return { ...msg, text: msg.text + e.delta }
    case 'tool_start': return { ...msg, steps: [...msg.steps, { name: e.name, label: stepLabel(e.name, e.input) }] }
    case 'sql_result': return { ...msg, sql: [...msg.sql, e] }
    case 'doc_results': return { ...msg, passages: [...msg.passages, ...e.passages] }
    case 'report': return { ...msg, reports: [...msg.reports, e] }
    case 'notice': return { ...msg, notice: e.message }
    case 'refusal':
    case 'error': return { ...msg, status: 'error', error: e.message }
    case 'done': return { ...msg, status: msg.status === 'error' ? 'error' : 'done', cost: e.cost_usd }
    default: return msg
  }
}

function ReportView({ r }: { r: Report }) {
  const fmtTick = (v: unknown) => (typeof v === 'number' ? num(v) : String(v))
  return (
    <figure className="mt-2 rounded-md border border-border p-2" aria-label={`${r.title}. ${stripCites(r.summary)}`}>
      <figcaption className="mb-1 text-sm font-medium">{r.title}</figcaption>
      {r.chart === 'table' ? (
        <DataTable<Record<string, unknown>> rows={r.rows} rowKey={(row) => String(row[r.x])}
                   columns={[r.x, ...r.y].map((c) => ({ key: c, header: c, render: (row) => fmtTick(row[c]) }))} />
      ) : (
        <>
          {r.y.length > 1 && <Legend items={r.y.map((c, i) => ({ label: c, color: SERIES[i] }))} />}
          <ResponsiveContainer width="100%" height={200}>
            {r.chart === 'bar' ? (
              <BarChart data={r.rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--color-grid)" vertical={false} />
                <XAxis dataKey={r.x} {...AXIS} interval="preserveStartEnd" />
                <YAxis tickFormatter={fmtTick} width={52} {...AXIS} />
                <Tooltip content={tooltip(num)} cursor={{ fill: 'var(--color-grid)', opacity: 0.5 }} />
                {r.y.map((c, i) => <Bar key={c} dataKey={c} fill={SERIES[i]} radius={[4, 4, 0, 0]} isAnimationActive={false} />)}
              </BarChart>
            ) : (
              <LineChart data={r.rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--color-grid)" vertical={false} />
                <XAxis dataKey={r.x} {...AXIS} interval="preserveStartEnd" />
                <YAxis tickFormatter={fmtTick} width={52} {...AXIS} />
                <Tooltip content={tooltip(num)} />
                {r.y.map((c, i) => <Line key={c} dataKey={c} stroke={SERIES[i]} strokeWidth={2} dot={false} isAnimationActive={false} />)}
              </LineChart>
            )}
          </ResponsiveContainer>
        </>
      )}
      <p className="mt-1 text-xs text-ink-2">{stripCites(r.summary)} <span className="text-muted">Source: {r.source}</span></p>
    </figure>
  )
}

function SqlCard({ s }: { s: SqlResult }) {
  const [showSql, setShowSql] = useState(false)
  return (
    <div className="rounded-md border border-border p-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span><b>{s.id}</b> · {s.purpose} · {s.rows.length}{s.truncated ? '+' : ''} rows</span>
        <button type="button" className="underline" aria-expanded={showSql} onClick={() => setShowSql((v) => !v)}>
          {showSql ? 'Hide SQL' : 'Show SQL'}
        </button>
      </div>
      {showSql && <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded bg-grid p-2 font-mono">{s.sql}</pre>}
      <div className="mt-1 max-h-48 overflow-auto">
        <DataTable<{ i: number; r: unknown[] }> rows={s.rows.slice(0, 10).map((r, i) => ({ i, r }))} rowKey={(x) => x.i}
                   columns={s.columns.map((c, ci) => ({ key: c, header: c, render: (x) => String(x.r[ci] ?? '') }))} />
      </div>
    </div>
  )
}

function DocCard({ p }: { p: Passage }) {
  return (
    <div className="rounded-md border border-border p-2 text-xs">
      <div><b>{p.id}</b> · {p.title} › {p.section}</div>
      <p className="mt-1 whitespace-pre-line text-ink-2">{p.text.length > 600 ? `${p.text.slice(0, 600)}…` : p.text}</p>
    </div>
  )
}

function AnswerText({ text, onCite }: { text: string; onCite: (id: string) => void }) {
  const lines = text.split('\n').filter((l) => l.trim())
  const render = (line: string) => splitCitations(line).map((part, i) =>
    part.kind === 'text' ? <span key={i}>{part.value}</span> : (
      <button key={i} type="button" onClick={() => onCite(part.id)}
              className="mx-0.5 rounded bg-grid px-1 text-[11px] font-semibold text-ink-2 hover:bg-axis"
              aria-label={`Show source ${part.id}`}>{part.id}</button>
    ))
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((l, i) => l.trimStart().startsWith('- ')
        ? <p key={i} className="pl-3 -indent-3">• {render(l.trimStart().slice(2))}</p>
        : <p key={i}>{render(l)}</p>)}
    </div>
  )
}

function AssistantView({ m }: { m: AssistantMsg }) {
  const [open, setOpen] = useState<string | null>(null)
  const used = new Set([...m.text.matchAll(/\[([SD]\d+)\]/g)].map((x) => x[1]))
  const sources = [...m.sql.filter((s) => used.has(s.id)), ...m.passages.filter((p) => used.has(p.id))]
  const openSql = m.sql.find((s) => s.id === open)
  const openDoc = m.passages.find((p) => p.id === open)
  return (
    <div className="space-y-2">
      {m.notice && (
        <p className="rounded border border-border bg-grid px-2 py-1 text-xs text-ink-2" role="note">{m.notice}</p>
      )}
      {m.steps.length > 0 && (
        <ul className="space-y-0.5 text-xs text-muted">
          {m.steps.map((s, i) => <li key={i}>✓ {s.label}</li>)}
        </ul>
      )}
      {m.text ? <AnswerText text={m.text} onCite={(id) => setOpen(open === id ? null : id)} />
        : m.status === 'streaming' && <p className="text-sm text-muted">Thinking…</p>}
      {m.reports.map((r, i) => <ReportView key={i} r={r} />)}
      {openSql && <SqlCard s={openSql} />}
      {openDoc && <DocCard p={openDoc} />}
      {m.status !== 'streaming' && sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 text-xs text-muted">
          Sources:
          {sources.map((s) => (
            <button key={s.id} type="button" onClick={() => setOpen(open === s.id ? null : s.id)}
                    className={`rounded border border-border px-1.5 ${open === s.id ? 'bg-grid text-ink' : ''}`}>
              {s.id} {'purpose' in s ? 'query' : s.title.split(':')[0]}
            </button>
          ))}
        </div>
      )}
      {m.error && <p className="text-sm text-critical" role="alert">{m.error}</p>}
      {m.cost != null && m.cost > 0 && <p className="text-[11px] text-muted">Cost ${m.cost.toFixed(3)}</p>}
    </div>
  )
}

export function ChatPanel({ onClose }: { onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [convId, setConvId] = useState<string | null>(null)
  const suggestions = useApi<string[]>('/agent/suggestions')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView?.({ block: 'end' }) }, [msgs])

  async function send(text: string) {
    const q = text.trim()
    if (!q || busy) return
    setInput('')
    setBusy(true)
    const blank: AssistantMsg = { role: 'assistant', text: '', steps: [], sql: [], passages: [], reports: [], status: 'streaming' }
    setMsgs((m) => [...m, { role: 'user', text: q }, blank])
    const update = (e: AgentEvent) => {
      if (e.type === 'conversation') { setConvId(e.id); return }
      setMsgs((m) => {
        const last = m[m.length - 1] as AssistantMsg
        return [...m.slice(0, -1), reduce(last, e)]
      })
    }
    try {
      await streamChat(q, convId, update)
    } catch (err) {
      update({ type: 'error', message: err instanceof Error ? err.message : String(err) })
    } finally {
      setMsgs((m) => {
        const last = m[m.length - 1] as AssistantMsg
        return last.status === 'streaming' ? [...m.slice(0, -1), { ...last, status: 'done' }] : m
      })
      setBusy(false)
    }
  }

  const onSubmit = (e: FormEvent) => { e.preventDefault(); void send(input) }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(input) }
  }

  return (
    <aside aria-label="LeaseLens assistant"
           className="fixed inset-y-0 right-0 z-20 flex w-full flex-col border-l border-border bg-surface shadow-xl sm:w-[440px]">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="font-semibold">Ask LeaseLens</h2>
          <p className="text-xs text-muted">Answers cite query results [S] and documents [D]</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="rounded border border-border px-2 py-0.5 text-xs"
                  onClick={() => { setMsgs([]); setConvId(null) }} disabled={busy}>New chat</button>
          <button type="button" className="rounded border border-border px-2 py-0.5 text-xs" onClick={onClose}
                  aria-label="Close assistant">Close</button>
        </div>
      </header>
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3" aria-live="polite">
        {msgs.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-ink-2">Try a question about the portfolio's data or documents:</p>
            {(suggestions.data ?? []).map((s) => (
              <button key={s} type="button" onClick={() => void send(s)}
                      className="block w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-grid">
                {s}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => m.role === 'user'
          ? <p key={i} className="ml-8 rounded-lg bg-grid px-3 py-2 text-sm">{m.text}</p>
          : <AssistantView key={i} m={m} />)}
        <div ref={endRef} />
      </div>
      <form onSubmit={onSubmit} className="border-t border-border p-3">
        <label htmlFor="chat-input" className="sr-only">Message</label>
        <textarea id="chat-input" rows={2} value={input} maxLength={1000}
                  onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
                  placeholder="e.g. Which units at Maple Court owe more than one month's rent?"
                  className="w-full resize-none rounded-md border border-border bg-surface p-2 text-sm" />
        <div className="mt-1 flex justify-between text-xs text-muted">
          <span>Read-only · synthetic data</span>
          <button type="submit" disabled={busy || !input.trim()}
                  className="rounded bg-ink px-3 py-1 text-sm text-surface disabled:opacity-40">
            {busy ? 'Answering…' : 'Send'}
          </button>
        </div>
      </form>
    </aside>
  )
}
