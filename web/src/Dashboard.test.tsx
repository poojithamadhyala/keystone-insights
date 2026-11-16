import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Dashboard } from './Dashboard'

// Minimal fake API keyed by path prefix.
const responses: Record<string, unknown> = {
  '/api/kpis/meta': { as_of: '2026-10-31', seed: 42, first_month: '2024-11-01' },
  '/api/kpis/properties': [
    { id: 1, name: 'Maple Court', city: 'X', state: 'TX', property_type: 'garden', year_built: 2000, units: 4 },
  ],
  '/api/kpis/occupancy': {
    as_of: '2026-10-31',
    by_property: [{ property_id: 1, property: 'Maple Court', units: 4, occupied: 3, occupancy: 0.75 }],
    trend: [{ month: '2026-10-01', occupancy: 0.75 }],
  },
  '/api/kpis/noi': [
    { property_id: 1, property: 'Maple Court', month: '2026-10-01', revenue: 5000,
      operating_expenses: 1000, maintenance: 500, noi: 3500 },
  ],
  '/api/kpis/delinquency': [{ bucket: '0-30', current_resident: true, amount: 1200, tenants: 1 }],
  '/api/kpis/lease-expirations': [
    { month: '2026-11-01', property_id: 1, property: 'Maple Court', leases: 2, monthly_rent: 3000 },
  ],
  '/api/kpis/work-order-sla': [
    { grp: 'high', tickets: 10, judged: 10, met: 8, sla_rate: 0.8, median_hours: 30 },
  ],
}

const fetchMock = vi.fn(async (url: string) => {
  const key = Object.keys(responses).find((k) => url.split('?')[0] === k)
  return new Response(JSON.stringify(key ? responses[key] : {}), { status: key ? 200 : 404 })
})

beforeEach(() => {
  fetchMock.mockClear()
  vi.stubGlobal('fetch', fetchMock)
  // Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
})
afterEach(() => vi.unstubAllGlobals())

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/properties/:propertyId" element={<Dashboard />} />
      </Routes>
    </MemoryRouter>,
  )
}

function tile(label: string) {
  return screen.getByRole('group', { name: label })
}

test('portfolio overview shows KPI tiles from the API', async () => {
  renderAt('/')
  expect(await screen.findByText('Portfolio overview')).toBeInTheDocument()
  expect(await within(tile('Occupancy')).findByText('75.0%')).toBeInTheDocument()
  expect(within(tile('NOI')).getByText('$3.5K')).toBeInTheDocument()
  expect(within(tile('Work-order SLA')).getByText('80.0%')).toBeInTheDocument()
  expect(within(tile('Leases expiring')).getByText('2')).toBeInTheDocument()
})

test('filters are passed to the API as query params', async () => {
  renderAt('/?months=3&p=1')
  await screen.findByText('Portfolio overview')
  await within(tile('Occupancy')).findByText('75.0%')
  const occCall = fetchMock.mock.calls.map((c) => c[0]).find((u) => u.startsWith('/api/kpis/occupancy'))
  expect(occCall).toBe('/api/kpis/occupancy?property_id=1&start=2026-08-01&end=2026-10-01')
})

test('property drill-down is scoped to that property', async () => {
  renderAt('/properties/1')
  expect(await screen.findByRole('heading', { name: 'Maple Court' })).toBeInTheDocument()
  const calls = fetchMock.mock.calls.map((c) => c[0])
  expect(calls.some((u) => u.startsWith('/api/kpis/rent-roll?property_id=1'))).toBe(true)
})
