// Client for POST /api/agent/chat (server-sent events over a fetch stream; EventSource can't POST).

export interface SqlResult {
  type: 'sql_result'; id: string; purpose: string; sql: string
  columns: string[]; rows: unknown[][]; truncated: boolean
}
export interface Passage { id: string; doc_id: string; title: string; section: string; text: string }
export interface Report {
  type: 'report'; title: string; chart: 'bar' | 'line' | 'table'; x: string; y: string[]
  rows: Record<string, unknown>[]; summary: string; source: string
}
export type AgentEvent =
  | { type: 'conversation'; id: string }
  | { type: 'text'; delta: string }
  | { type: 'tool_start'; name: string; input: Record<string, unknown> }
  | SqlResult
  | { type: 'doc_results'; query: string; passages: Passage[] }
  | Report
  | { type: 'refusal' | 'error'; message: string }
  | { type: 'done'; cost_usd: number; model: string; prompt_version: string }

/** Parse complete SSE blocks out of `buffer`; returns the events and the unconsumed remainder. */
export function parseSse(buffer: string): { events: AgentEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: AgentEvent[] = []
  for (const block of blocks) {
    let name = 'message'
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) continue
    const parsed = JSON.parse(data.join('\n')) as Record<string, unknown>
    events.push({ type: name, ...parsed } as AgentEvent)
  }
  return { events, rest }
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (e: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { events, rest } = parseSse(buffer)
    buffer = rest
    events.forEach(onEvent)
  }
}

/** Split answer text into plain runs and citation markers like [S1] / [D2]. */
export function splitCitations(text: string): ({ kind: 'text'; value: string } | { kind: 'cite'; id: string })[] {
  const out: ({ kind: 'text'; value: string } | { kind: 'cite'; id: string })[] = []
  let last = 0
  for (const m of text.matchAll(/\[([SD]\d+)\]/g)) {
    if (m.index > last) out.push({ kind: 'text', value: text.slice(last, m.index) })
    out.push({ kind: 'cite', id: m[1] })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ kind: 'text', value: text.slice(last) })
  return out
}
