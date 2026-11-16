import { fireEvent, render, screen } from '@testing-library/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { DigestPage, mrkdwn, type DigestRun } from './DigestPage'

test('mrkdwn renders bold and italic as elements, never as HTML', () => {
  expect(renderToStaticMarkup(<p>{mrkdwn('*Down $21.5K* this week _verified_')}</p>))
    .toBe('<p><strong>Down $21.5K</strong><span> this week </span><em class="text-muted">verified</em></p>')
  expect(renderToStaticMarkup(<p>{mrkdwn('<img src=x onerror=alert(1)>')}</p>))
    .toBe('<p><span>&lt;img src=x onerror=alert(1)&gt;</span></p>')
})

const run: DigestRun = {
  id: 7, created_at: '2026-11-16T12:00:00Z', as_of: '2026-10-31', trigger: 'preview',
  text: '*Weekly portfolio digest*\n• Delinquency down $21.5K\n_Facts-only version: the written summary failed the number check and was withheld. Synthetic data._',
  narrative_ok: false, ungrounded: ['$9,999'], cost_usd: 0.013, sent_at: null, delivery_status: null,
  facts: {
    as_of: '2026-10-31', window_days: 90,
    delinquency: { current_residents_this_week: 104673.08, current_residents_last_week: 126192.62, change: -21519.54 },
    expirations: { leases: 720, monthly_rent: 1382872.16 },
    sla: { open_breaches: 8, open_breaches_last_week: 4, completed_late_last_7_days: 2,
           oldest: [{ work_order_id: 7594, property: 'Birch Terrace', unit: '102', category: 'plumbing',
                      priority: 'low', vendor: 'V', days_open: 18 }] },
  },
}

test('shows the stored text, the fallback flag, and sends that run', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`)
    if (url.endsWith('/digest/runs')) return new Response('[]')
    if (url.endsWith('/send')) return new Response(JSON.stringify({ ...run, delivery_status: 'sent' }))
    return new Response(JSON.stringify(run))
  }))
  render(<DigestPage />)
  expect(await screen.findByText('⚠ Facts-only fallback')).toBeInTheDocument()
  expect(screen.getByText(/Operator note \(not sent\).*\$9,999/)).toBeInTheDocument()
  expect(screen.getByText('down $21,520 vs last week')).toBeInTheDocument()
  expect(screen.getByText('#7594')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Send now' }))
  expect(await screen.findByText('Sent to Slack.')).toBeInTheDocument()
  expect(calls).toContain('POST /api/digest/7/send')
  vi.unstubAllGlobals()
})

test('empty state when nothing has been built', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) =>
    url.endsWith('/runs') ? new Response('[]') : new Response('{"detail":"no digest"}', { status: 404 })))
  render(<DigestPage />)
  expect(await screen.findByText(/No digest has been built yet/)).toBeInTheDocument()
  vi.unstubAllGlobals()
})
