import { fireEvent, render, screen, within } from '@testing-library/react'
import { parseSse, splitCitations } from './agent'
import { ChatPanel, reduce, type AssistantMsg } from './ChatPanel'

test('parseSse handles CRLF, partial blocks and named events', () => {
  const chunk = 'event: text\r\ndata: {"type":"text","delta":"Hi"}\r\n\r\nevent: done\r\ndata: {"type":"do'
  const { events, rest } = parseSse(chunk)
  expect(events).toEqual([{ type: 'text', delta: 'Hi' }])
  expect(rest).toContain('"type":"do')
})

test('splitCitations finds S and D markers', () => {
  expect(splitCitations('Total $5 [S1] per lease [D2].')).toEqual([
    { kind: 'text', value: 'Total $5 ' }, { kind: 'cite', id: 'S1' },
    { kind: 'text', value: ' per lease ' }, { kind: 'cite', id: 'D2' }, { kind: 'text', value: '.' },
  ])
})

test('reduce accumulates text, steps, sources and errors', () => {
  let m: AssistantMsg = { role: 'assistant', text: '', steps: [], sql: [], passages: [], reports: [], status: 'streaming' }
  m = reduce(m, { type: 'tool_start', name: 'query_kpis', input: { purpose: 'units' } })
  m = reduce(m, { type: 'text', delta: 'A' })
  m = reduce(m, { type: 'text', delta: 'B' })
  expect(m.text).toBe('AB')
  expect(m.steps[0].label).toBe('Queried data: units')
  m = reduce(m, { type: 'done', cost_usd: 0.05, model: 'm', prompt_version: 'v1' })
  expect(m.status).toBe('done')
  expect(reduce(m, { type: 'error', message: 'boom' }).status).toBe('error')
})

// End to end in the browser: a canned SSE response flows into the panel.
function sse(events: object[]): string {
  return events.map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`).join('')
}

test('a streamed answer renders with citation chips, SQL toggle and a chart', async () => {
  const body = sse([
    { type: 'conversation', id: 'c1' },
    { type: 'tool_start', name: 'query_kpis', input: { purpose: 'units by property' } },
    { type: 'sql_result', id: 'S1', purpose: 'units by property', sql: 'SELECT name, count(*) FROM reporting.units',
      columns: ['name', 'units'], rows: [['Maple Court', 93]], truncated: false },
    { type: 'report', title: 'Units', chart: 'table', x: 'name', y: ['units'],
      rows: [{ name: 'Maple Court', units: 93 }], summary: 'Unit counts by property [S1]', source: 'S1' },
    { type: 'text', delta: 'Maple Court has 93 units [S1].' },
    { type: 'done', cost_usd: 0.04, model: 'm', prompt_version: 'v1' },
  ])
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.includes('suggestions')
    ? new Response('[]') : new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })))
  render(<ChatPanel onClose={() => {}} />)
  fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'How many units?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('✓ Queried data: units by property')).toBeInTheDocument()
  expect(await screen.findByText(/Cost \$0\.040/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Show source S1' }))
  const toggle = screen.getByRole('button', { name: 'Show SQL' })
  fireEvent.click(toggle)
  expect(screen.getByText(/SELECT name, count\(\*\)/)).toBeInTheDocument()
  const fig = screen.getByRole('figure')
  expect(within(fig).getByText('Units')).toBeInTheDocument()
  expect(within(fig).getByText(/^Unit counts by property$/)).toBeInTheDocument() // marker stripped
  vi.unstubAllGlobals()
})

test('chart captions drop inline citation markers', async () => {
  const { stripCites } = await import('./ChatPanel')
  expect(stripCites('Pine Lofts leads at $12,820 [S1].')).toBe('Pine Lofts leads at $12,820.')
})
