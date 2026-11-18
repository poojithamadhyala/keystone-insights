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
// No text under 14px (brief); tick labels in muted ink (6.3:1 on the card surface).
const AXIS = { stroke: 'var(--color-axis)', tick: { fill: 'var(--color-muted)', fontSize: 14 }, tickLine: false, axisLine: false } as const
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
    <figure className="mt-3 border border-line p-4" aria-label={`${r.title}. ${stripCites(r.summary)}`}>
      <figcaption className="display mb-2 text-xl text-ink">{r.title}</figcaption>
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
                {r.y.map((c, i) => <Bar key={c} dataKey={c} fill={SERIES[i]} radius={[2, 2, 0, 0]} isAnimationActive={false} />)}
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
      <p className="mt-2 text-sm text-ink-2">{stripCites(r.summary)} <span className="text-muted">Source: {r.source}</span></p>
    </figure>
  )
}

function SqlCard({ s }: { s: SqlResult }) {
  const [showSql, setShowSql] = useState(false)
  return (
    <div className="border border-line p-4 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span><b>{s.id}</b> · {s.purpose} · {s.rows.length}{s.truncated ? '+' : ''} rows</span>
        <button type="button" className="label shrink-0 text-brand hover:underline" aria-expanded={showSql} onClick={() => setShowSql((v) => !v)}>
          {showSql ? 'Hide SQL' : 'Show SQL'}
        </button>
      </div>
      {showSql && <pre className="mt-3 overflow-x-auto whitespace-pre-wrap border-l border-brand bg-page p-3 font-mono text-sm text-ink-2">{s.sql}</pre>}
      <div className="mt-3 max-h-56 overflow-auto">
        <DataTable<{ i: number; r: unknown[] }> rows={s.rows.slice(0, 10).map((r, i) => ({ i, r }))} rowKey={(x) => x.i}
                   columns={s.columns.map((c, ci) => ({ key: c, header: c, render: (x) => String(x.r[ci] ?? '') }))} />
      </div>
    </div>
  )
}

function DocCard({ p }: { p: Passage }) {
  return (
    <div className="border border-line p-4 text-sm">
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
              className="mx-0.5 align-baseline text-sm font-medium text-brand underline decoration-dotted underline-offset-2 hover:decoration-solid"
              aria-label={`Show source ${part.id}`}>{part.id}</button>
    ))
  return (
    <div className="space-y-2 text-base leading-relaxed text-ink">
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
    <div className="space-y-3">
      {m.notice && (
        <p className="border-l border-brand pl-3 text-sm text-ink-2" role="note">{m.notice}</p>
      )}
      {m.steps.length > 0 && (
        <ul className="space-y-1 text-sm text-muted">
          {m.steps.map((s, i) => <li key={i}>✓ {s.label}</li>)}
        </ul>
      )}
      {m.text ? <AnswerText text={m.text} onCite={(id) => setOpen(open === id ? null : id)} />
        : m.status === 'streaming' && <p className="text-sm text-muted">Thinking…</p>}
      {m.reports.map((r, i) => <ReportView key={i} r={r} />)}
      {openSql && <SqlCard s={openSql} />}
      {openDoc && <DocCard p={openDoc} />}
      {m.status !== 'streaming' && sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
          Sources:
          {sources.map((s) => (
            <button key={s.id} type="button" onClick={() => setOpen(open === s.id ? null : s.id)}
                    className={`border-b ${open === s.id ? 'border-brand text-brand' : 'border-line text-ink-2 hover:text-brand'}`}>
              {s.id} {'purpose' in s ? 'query' : s.title.split(':')[0]}
            </button>
          ))}
        </div>
      )}
      {m.error && <p className="text-sm text-critical" role="alert">{m.error}</p>}
      {m.cost != null && m.cost > 0 && <p className="text-sm text-muted">Cost ${m.cost.toFixed(3)}</p>}
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
           className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-line bg-surface sm:w-[480px]">
      <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-6">
        <div>
          <h2 className="text-2xl text-ink">Ask LeaseLens</h2>
          <p className="mt-1 text-sm text-muted">Answers cite query results [S] and documents [D]</p>
        </div>
        <div className="flex shrink-0 gap-5 pt-1">
          <button type="button" className="label text-ink-2 hover:text-brand disabled:opacity-40"
                  onClick={() => { setMsgs([]); setConvId(null) }} disabled={busy}>New chat</button>
          <button type="button" className="label text-ink-2 hover:text-brand" onClick={onClose}
                  aria-label="Close assistant">Close</button>
        </div>
      </header>
      <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6" aria-live="polite">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <p className="label text-brand">Try a question about the data or documents</p>
            {(suggestions.data ?? []).map((s) => (
              <button key={s} type="button" onClick={() => void send(s)}
                      className="block w-full border-b border-line py-3 text-left text-base text-ink-2 transition-colors duration-300 hover:text-brand">
                {s}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => m.role === 'user'
          ? <p key={i} className="display ml-10 border-r border-brand pr-4 text-right text-lg text-ink">{m.text}</p>
          : <AssistantView key={i} m={m} />)}
        <div ref={endRef} />
      </div>
      <form onSubmit={onSubmit} className="border-t border-line px-6 py-5">
        <label htmlFor="chat-input" className="sr-only">Message</label>
        <textarea id="chat-input" rows={2} value={input} maxLength={1000}
                  onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
                  placeholder="e.g. Which units at Maple Court owe more than one month's rent?"
                  className="field w-full resize-none" />
        <div className="mt-4 flex items-center justify-between gap-4 text-sm text-muted">
          <span>Read only · synthetic data</span>
          <button type="submit" disabled={busy || !input.trim()}
                  className="btn btn-sm">
            {busy ? 'Answering…' : 'Send'}
          </button>
        </div>
      </form>
    </aside>
  )
}
