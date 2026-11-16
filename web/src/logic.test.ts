import { agingByBucket, expirationsByMonth, noiByMonth, noiByProperty } from './charts'
import { addMonths, monthLabel, pct } from './format'
import { filtersToParams, parseFilters, rangeFor } from './scope'
import type { NoiRow } from './api'

test('addMonths crosses year boundaries', () => {
  expect(addMonths('2026-10-01', 3)).toBe('2027-01-01')
  expect(addMonths('2026-01-01', -1)).toBe('2025-12-01')
})

test('monthLabel never shifts month by timezone', () => {
  expect(monthLabel('2026-03-01')).toBe('Mar 2026')
})

test('pct handles null', () => {
  expect(pct(0.9441)).toBe('94.4%')
  expect(pct(null)).toBe('—')
})

test('rangeFor returns N months ending at the as-of month', () => {
  expect(rangeFor('2026-10-31', 12)).toEqual({ start: '2025-11-01', end: '2026-10-01' })
  expect(rangeFor('2026-10-31', 3)).toEqual({ start: '2026-08-01', end: '2026-10-01' })
})

test('URL filters round-trip and reject junk', () => {
  const f = { months: 6 as const, propertyIds: [3, 7] }
  expect(parseFilters(filtersToParams(f))).toEqual(f)
  expect(parseFilters(new URLSearchParams('months=5&p=x&p=-1&p=2'))).toEqual({ months: 12, propertyIds: [2] })
})

const noi = (property_id: number, month: string, noiV: number): NoiRow => ({
  property_id, property: `P${property_id}`, month, revenue: noiV + 10,
  operating_expenses: 6, maintenance: 4, noi: noiV,
})

test('NOI aggregations', () => {
  const rows = [noi(1, '2026-01-01', 100), noi(1, '2026-02-01', 50), noi(2, '2026-01-01', 200)]
  expect(noiByProperty(rows).map((r) => [r.property_id, r.noi])).toEqual([[2, 200], [1, 150]])
  expect(noiByMonth(rows)).toEqual([
    { month: '2026-01-01', revenue: 320, expenses: 20, noi: 300 },
    { month: '2026-02-01', revenue: 60, expenses: 10, noi: 50 },
  ])
})

test('aging fills missing buckets with zero', () => {
  const rows = agingByBucket([{ bucket: '90+', current_resident: false, amount: 1200, tenants: 1 }])
  expect(rows.map((r) => r.bucket)).toEqual(['0-30', '31-60', '61-90', '90+'])
  expect(rows[3]).toMatchObject({ current: 0, former: 1200, formerTenants: 1 })
})

test('expirations sum across properties per month', () => {
  const rows = expirationsByMonth([
    { month: '2026-11-01', property_id: 1, property: 'A', leases: 2, monthly_rent: 3000 },
    { month: '2026-11-01', property_id: 2, property: 'B', leases: 1, monthly_rent: 1000 },
  ])
  expect(rows).toEqual([{ month: '2026-11-01', leases: 3, monthly_rent: 4000 }])
})
