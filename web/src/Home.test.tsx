import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ChatContext } from './chat'
import { Home } from './Home'

const responses: Record<string, unknown> = {
  '/api/kpis/meta': { as_of: '2026-10-31', seed: 42, first_month: '2024-11-01' },
  '/api/kpis/occupancy': {
    as_of: '2026-10-31',
    by_property: [{ property_id: 1, property: 'Maple Court', units: 100, occupied: 96, occupancy: 0.96 }],
    trend: [],
  },
  '/api/kpis/delinquency': [{ bucket: '0-30', current_resident: true, amount: 104673.08, tenants: 40 }],
  '/api/kpis/lease-expirations': [
    { month: '2026-11-01', property_id: 1, property: 'Maple Court', leases: 7, monthly_rent: 12000 },
  ],
  '/api/kpis/work-order-sla': [{ grp: 'high', tickets: 10, judged: 10, met: 7, sla_rate: 0.7, median_hours: 30 }],
  '/api/digest/latest': { facts: { as_of: '2026-10-31', delinquency: { change: -21519.54 }, sla: { open_breaches: 8 } } },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const body = responses[url.split('?')[0]]
    return new Response(JSON.stringify(body ?? {}), { status: body ? 200 : 404 })
  }))
})
afterEach(() => vi.unstubAllGlobals())

function renderHome(openChat = vi.fn()) {
  render(
    <ChatContext.Provider value={{ openChat }}>
      <MemoryRouter><Home /></MemoryRouter>
    </ChatContext.Provider>,
  )
  return openChat
}

test('explains the app in plain words and says the data is made up', async () => {
  renderHome()
  expect(screen.getByRole('heading', { name: 'Your apartment portfolio, explained.' })).toBeInTheDocument()
  expect(screen.getByText('all data is made up for this demo')).toBeInTheDocument()
})

test('health cards show live numbers with plain verdicts and this week\'s change', async () => {
  renderHome()
  const rented = screen.getByRole('group', { name: 'Apartments rented' })
  expect(await within(rented).findByText('96.0%')).toBeInTheDocument()
  expect(within(rented).getByText('Healthy')).toBeInTheDocument()
  const owed = screen.getByRole('group', { name: 'Unpaid rent' })
  expect(await within(owed).findByText('↓ down $21,520 from last week')).toBeInTheDocument()
  const repairs = screen.getByRole('group', { name: 'Repairs done on time' })
  expect(await within(repairs).findByText('Needs attention')).toBeInTheDocument() // 70% < 80%
  expect(within(repairs).getByText('8 repairs overdue right now')).toBeInTheDocument()
  expect(within(screen.getByRole('group', { name: 'Leases ending soon' })).getByText('7')).toBeInTheDocument()
})

test('rules of thumb are visible on request, and "Ask a question" opens the assistant', async () => {
  const openChat = renderHome()
  fireEvent.click(screen.getByRole('button', { name: 'How we judge "healthy"' }))
  expect(screen.getByText(/Healthy at 95% or more rented/)).toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: /Ask a question/ })[0])
  expect(openChat).toHaveBeenCalled()
})
